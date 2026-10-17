import json
import os
import re

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from model.common import IMG_SIZE, canonical_key, crop_of, pil_to_array
from model.predict import ModelUnavailable, Predictor
from model.train_model import apply_thresholds, choose_thresholds, group_id, split_dataset
from services.disease_advisory import ADVISORY, get_advisory

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------- class keys
@pytest.mark.parametrize("raw,expected", [
    ("Tomato_Early_blight", "tomato_early_blight"),
    ("Tomato___Early_blight", "tomato_early_blight"),
    ("Tomato__Target_Spot", "tomato_target_spot"),
    ("Tomato__Tomato_YellowLeaf__Curl_Virus", "tomato_yellow_leaf_curl_virus"),
    ("Tomato___Tomato_Yellow_Leaf_Curl_Virus", "tomato_yellow_leaf_curl_virus"),
    ("Tomato__Tomato_mosaic_virus", "tomato_mosaic_virus"),
    ("Tomato_Spider_mites_Two_spotted_spider_mite", "tomato_spider_mites"),
    ("Tomato_Septoria_leaf_spot", "tomato_septoria_leaf_spot"),
    ("Tomato_Leaf_Mold", "tomato_leaf_mold"),
    ("Tomato_Bacterial_spot", "tomato_bacterial_spot"),
    ("Tomato_healthy", "tomato_healthy"),
    ("Potato___Late_blight", "potato_late_blight"),
    ("Potato___healthy", "potato_healthy"),
])
def test_canonical_keys(raw, expected):
    assert canonical_key(raw) == expected
    assert get_advisory(raw) is not None            # every dataset spelling maps to documented advice
    assert crop_of(expected) in {"tomato", "potato"}


def test_preprocess_shape_dtype_range():
    arr = pil_to_array(Image.new("RGB", (500, 300), (10, 200, 30)))
    assert arr.shape == (IMG_SIZE, IMG_SIZE, 3) and arr.dtype == np.float32
    assert arr.min() >= 0 and arr.max() <= 255
    # grayscale/RGBA inputs are coerced to 3 channels the same way
    assert pil_to_array(Image.new("L", (80, 80), 128)).shape == (IMG_SIZE, IMG_SIZE, 3)
    assert pil_to_array(Image.new("RGBA", (80, 80), (1, 2, 3, 4))).shape == (IMG_SIZE, IMG_SIZE, 3)


# ---------------------------------------------------------------- predictor
class FakeModel:
    def __init__(self, probs):
        self.probs = np.array([probs], dtype="float32")

    def __call__(self, arr, training=False):
        assert arr.shape == (1, IMG_SIZE, IMG_SIZE, 3) and training is False
        return self.probs


def fake_predictor(probs, classes=("tomato_early_blight", "tomato_healthy", "potato_late_blight")):
    p = Predictor("/nonexistent")
    p._loaded, p._model, p.classes = True, FakeModel(probs), list(classes)
    return p


IMG = Image.new("RGB", (100, 100))


def test_predictor_without_files_is_unavailable(tmp_path):
    p = Predictor(str(tmp_path))
    assert p.available is False and "train_model" in p.error
    with pytest.raises(ModelUnavailable):
        p.predict(IMG)


def test_confident_prediction():
    r = fake_predictor([0.94, 0.04, 0.02]).predict(IMG, "tomato")
    assert r["class_key"] == "tomato_early_blight" and r["reliable"] and r["warnings"] == []
    assert [t["class_key"] for t in r["top3"]][0] == "tomato_early_blight"


def test_low_confidence_and_ambiguous_flags():
    r = fake_predictor([0.45, 0.35, 0.20]).predict(IMG, "tomato")
    assert "low_confidence" in r["warnings"] and "ambiguous" in r["warnings"] and not r["reliable"]
    r = fake_predictor([0.74, 0.70 - 0.0, 0.0]).predict(IMG, "tomato")     # confident but close runner-up
    assert "ambiguous" in r["warnings"]


def test_crop_mismatch_flag():
    r = fake_predictor([0.05, 0.05, 0.90]).predict(IMG, "tomato")
    assert r["predicted_crop"] == "potato" and "crop_mismatch" in r["warnings"]


def test_invalid_model_output_rejected():
    p = fake_predictor([0.5, 0.5, 0.5])
    p._model.probs = np.array([[np.nan, 0.5, 0.5]], dtype="float32")
    with pytest.raises(RuntimeError):
        p.predict(IMG)


def test_class_count_mismatch_reports_load_error(tmp_path):
    (tmp_path / "saved_model.keras").write_bytes(b"not a model")
    (tmp_path / "class_names.json").write_text(json.dumps(["a_b"]))
    p = Predictor(str(tmp_path))
    assert p.available is False and p.error


# ------------------------------------------------------------ training code
def test_group_id_collapses_augmented_copies():
    base = "abc123___RS_Early.B 7915"
    assert group_id(f"/x/{base}.JPG") == group_id(f"/x/{base}_flipTB.JPG") == group_id(f"/x/{base}_180deg.JPG")
    assert group_id("/x/other___RS_HL 1.JPG") != group_id(f"/x/{base}.JPG")


def test_split_has_no_group_leakage_and_is_stratified():
    rng = np.random.default_rng(0)
    rows = []
    for cls in ("tomato_healthy", "tomato_early_blight", "potato_late_blight"):
        for g in range(60):
            for k in range(rng.integers(1, 4)):              # several augmented copies per group
                rows.append((f"{cls}/{g}_{k}.jpg", cls, f"{cls}:{g}"))
    df = pd.DataFrame(rows, columns=["path", "class_key", "group"])
    out = split_dataset(df, seed=1)
    assert len(out) == len(df)
    assert (out.groupby("group")["split"].nunique() == 1).all()
    for s in ("train", "val", "test"):
        assert set(out[out.split == s].class_key) == set(df.class_key)
    frac = out.split.value_counts(normalize=True)
    assert 0.6 < frac["train"] < 0.8 and 0.08 < frac["val"] < 0.25 and 0.08 < frac["test"] < 0.25


def test_threshold_selection_improves_accepted_accuracy():
    rng = np.random.default_rng(3)
    n, k = 600, 4
    y = rng.integers(0, k, n)
    probs = rng.dirichlet(np.ones(k) * 0.8, n)
    sure = rng.random(n) < 0.6                               # 60% confident-and-correct, rest noisy
    probs[sure] = np.eye(k)[y[sure]] * 0.9 + 0.025
    thr, sweep = choose_thresholds(probs, y, target_accuracy=0.95)
    stats = apply_thresholds(probs, y, thr)
    assert stats["accepted_accuracy"] >= 0.95 and stats["coverage"] >= 0.5
    base_acc = (probs.argmax(1) == y).mean()
    assert stats["accepted_accuracy"] > base_acc
    assert {"min_confidence", "min_margin", "coverage", "accepted_accuracy"} <= set(sweep.columns)


# ----------------------------------------------------------------- advisory
DOSE = re.compile(r"\b\d+(\.\d+)?\s?(ml|mg|g|kg|l|litres?|liters?|ppm|%|gm)\b", re.I)
CHEMICALS = ["mancozeb", "chlorothalonil", "metalaxyl", "copper oxychloride", "streptomycin", "imidacloprid",
             "carbendazim", "azoxystrobin", "fungicide spray of", "dithane"]


def test_advisory_is_complete_and_bilingual():
    assert len(ADVISORY) >= 13
    for key, e in ADVISORY.items():
        assert key.split("_")[0] == e["crop"] in {"tomato", "potato"}
        for field in ("symptoms", "prevention", "management"):
            for lang in ("en", "hi"):
                assert e[field][lang], (key, field, lang)
            assert len(e[field]["en"]) == len(e[field]["hi"]), (key, field)
        assert e["name"]["en"] and e["name"]["hi"]


def test_advisory_never_prescribes_doses_or_named_chemicals():
    for key, e in ADVISORY.items():
        text = " ".join(sum((e[f][l] for f in ("symptoms", "prevention", "management") for l in ("en", "hi")), []))
        assert not DOSE.search(text), (key, DOSE.search(text))
        assert not any(c in text.lower() for c in CHEMICALS), key


# --------------------------------------------------------------------- i18n
def test_translation_files_in_sync_and_cover_templates():
    with open(os.path.join(ROOT, "static", "i18n", "translations.json"), encoding="utf-8") as f:
        d = json.load(f)
    assert set(d["en"]) == set(d["hi"])
    assert all(v.strip() for v in d["hi"].values())
    used = set()
    tdir = os.path.join(ROOT, "templates")
    for fn in os.listdir(tdir):
        src = open(os.path.join(tdir, fn), encoding="utf-8").read()
        used |= set(re.findall(r'data-i18n(?:-placeholder)?="([^"{]+)"', src))
    assert used - set(d["en"]) == set(), used - set(d["en"])
    # Hindi should actually contain Devanagari, not leftover English, for visible UI strings
    deva = re.compile(r"[ऀ-ॿ]")
    assert sum(bool(deva.search(v)) for v in d["hi"].values()) > 0.95 * len(d["hi"])
