"""Train the KisanLens tomato/potato leaf classifier (MobileNetV2 transfer learning).

Usage (from the project root, e.g. in Google Colab or locally):

    python -m model.train_model --data-dir data/PlantVillage

Outputs (written to --out-dir, default ./model):
    saved_model.keras          trained network (augmentation + input scaling are INSIDE it)
    class_names.json           class index -> canonical class key
    thresholds.json            uncertainty thresholds chosen on the VALIDATION split
    artifacts/metrics.json     measured test accuracy, per-class precision/recall/F1
    artifacts/classification_report.txt, confusion_matrix.csv/.png
    artifacts/threshold_sweep.csv, splits.csv

Nothing here is hard-coded: every number reported comes from the held-out test split.
"""
import argparse
import hashlib
import json
import os
import re
import sys

import numpy as np
import pandas as pd

from model.common import IMG_SIZE, canonical_key, crop_of, load_image_array

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
_AUG_SUFFIX = re.compile(r"[_\-\s]*(flip[a-z]*|\d+\s?deg|rotation\w*|zoom\w*|shear\w*|bright\w*)$", re.I)


# ------------------------------------------------------------------ dataset
def group_id(path):
    """Group key so augmented copies of one photo stay in the same split."""
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    prev = None
    while prev != stem:
        prev, stem = stem, _AUG_SUFFIX.sub("", stem)
    return stem


def discover(data_dir, crops):
    """Find class folders for the chosen crops; returns DataFrame(path, class_key, group)."""
    rows, seen_hash = [], {}
    roots = [data_dir]
    # tolerate data/PlantVillage/PlantVillage/<class>/...
    for name in os.listdir(data_dir):
        sub = os.path.join(data_dir, name)
        if os.path.isdir(sub) and not name.lower().startswith(tuple(crops)):
            roots.append(sub)
    for root in roots:
        for folder in sorted(os.listdir(root)):
            full = os.path.join(root, folder)
            if not os.path.isdir(full) or not folder.lower().startswith(tuple(crops)):
                continue
            key = canonical_key(folder)
            for fn in sorted(os.listdir(full)):
                if os.path.splitext(fn)[1].lower() not in IMAGE_EXTS:
                    continue
                p = os.path.join(full, fn)
                with open(p, "rb") as f:
                    digest = hashlib.md5(f.read()).hexdigest()
                g = f"{key}:{group_id(p)}"
                g = seen_hash.setdefault(digest, g)      # byte-identical files share a group
                rows.append((p, key, g))
    df = pd.DataFrame(rows, columns=["path", "class_key", "group"])
    if df.empty:
        sys.exit(f"No images found for crops {crops} under {data_dir}. See data/README.md.")
    return df


def split_dataset(df, seed):
    """Group-aware, stratified 70/15/15 split (no photo group appears in two splits)."""
    from sklearn.model_selection import StratifiedGroupKFold

    groups_per_class = df.groupby("class_key")["group"].nunique()
    if groups_per_class.min() < 3:
        sys.exit(f"Class with too few distinct images to split:\n{groups_per_class.sort_values().head()}")
    n_test = int(min(7, groups_per_class.min()))
    sgkf = StratifiedGroupKFold(n_splits=n_test, shuffle=True, random_state=seed)
    labels = df["class_key"].values
    rest_idx, test_idx = next(sgkf.split(df, labels, df["group"]))
    rest = df.iloc[rest_idx].reset_index(drop=True)
    n_val = int(min(6, rest.groupby("class_key")["group"].nunique().min()))
    sgkf2 = StratifiedGroupKFold(n_splits=max(n_val, 2), shuffle=True, random_state=seed)
    tr_idx, val_idx = next(sgkf2.split(rest, rest["class_key"].values, rest["group"]))
    out = pd.concat([
        rest.iloc[tr_idx].assign(split="train"),
        rest.iloc[val_idx].assign(split="val"),
        df.iloc[test_idx].assign(split="test"),
    ], ignore_index=True)
    # Safety checks: no leakage across splits
    g = out.groupby("group")["split"].nunique()
    assert (g == 1).all(), "Group leakage between splits"
    return out


# -------------------------------------------------------------------- model
def build_model(num_classes, weights):
    import tensorflow as tf
    from tensorflow.keras import layers

    inputs = layers.Input((IMG_SIZE, IMG_SIZE, 3), name="image_0_255")
    # Training-only augmentation: these layers are no-ops when training=False (inference).
    x = layers.RandomFlip("horizontal_and_vertical")(inputs)
    x = layers.RandomRotation(0.1)(x)
    x = layers.RandomZoom(0.1)(x)
    x = layers.RandomContrast(0.1)(x)
    x = layers.RandomBrightness(0.1, value_range=(0, 255))(x)
    # MobileNetV2 expects [-1, 1]; same scaling at train and inference because it lives in the model.
    x = layers.Rescaling(1.0 / 127.5, offset=-1.0, name="mobilenet_v2_scaling")(x)
    base = tf.keras.applications.MobileNetV2(
        input_shape=(IMG_SIZE, IMG_SIZE, 3), include_top=False,
        weights=None if weights == "none" else weights)
    base.trainable = False
    x = base(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(num_classes, activation="softmax", name="probabilities")(x)
    return tf.keras.Model(inputs, outputs), base


def make_ds(paths, labels, batch_size, training, seed):
    import tensorflow as tf

    def _np_load(p):
        return load_image_array(p.decode("utf-8")).astype(np.uint8)   # lossless: PIL output is uint8

    def _load(p, y):
        img = tf.numpy_function(_np_load, [p], tf.uint8)
        img.set_shape((IMG_SIZE, IMG_SIZE, 3))
        return img, y

    ds = tf.data.Dataset.from_tensor_slices((paths, labels))
    ds = ds.map(_load, num_parallel_calls=tf.data.AUTOTUNE).cache()
    if training:
        ds = ds.shuffle(2048, seed=seed, reshuffle_each_iteration=True)
    ds = ds.batch(batch_size).map(lambda x, y: (tf.cast(x, tf.float32), y), num_parallel_calls=tf.data.AUTOTUNE)
    return ds.prefetch(tf.data.AUTOTUNE)


# --------------------------------------------------------------- evaluation
def choose_thresholds(probs, y_true, target_accuracy):
    """Sweep (min_confidence, min_margin) on the validation split.

    Pick the pair that keeps accuracy on ACCEPTED predictions >= target while
    accepting as many images as possible. Returns (best, sweep_dataframe).
    """
    order = np.argsort(-probs, axis=1)
    top1 = probs[np.arange(len(probs)), order[:, 0]]
    top2 = probs[np.arange(len(probs)), order[:, 1]] if probs.shape[1] > 1 else np.zeros(len(probs))
    margin, pred = top1 - top2, order[:, 0]
    correct = pred == y_true
    rows = []
    for c in np.round(np.arange(0.30, 0.995, 0.01), 2):
        for m in (0.0, 0.1, 0.2, 0.3):
            accepted = (top1 >= c) & (margin >= m)
            n = int(accepted.sum())
            rows.append({"min_confidence": float(c), "min_margin": m,
                         "coverage": n / len(probs),
                         "accepted_accuracy": float(correct[accepted].mean()) if n else float("nan"),
                         "n_accepted": n})
    sweep = pd.DataFrame(rows)
    ok = sweep[(sweep["accepted_accuracy"] >= target_accuracy) & (sweep["coverage"] >= 0.5)]
    if ok.empty:
        print(f"WARNING: no thresholds reach {target_accuracy:.0%} accepted accuracy with >=50% coverage; "
              "using the most accurate setting that keeps >=50% coverage.")
        pool = sweep[sweep["coverage"] >= 0.5]
        best = (pool if not pool.empty else sweep).sort_values(
            ["accepted_accuracy", "coverage"], ascending=False).iloc[0]
    else:
        best = ok.sort_values(["coverage", "min_confidence"], ascending=[False, True]).iloc[0]
    return {"min_confidence": float(best["min_confidence"]), "min_margin": float(best["min_margin"])}, sweep


def apply_thresholds(probs, y_true, thr):
    order = np.argsort(-probs, axis=1)
    top1 = probs[np.arange(len(probs)), order[:, 0]]
    top2 = probs[np.arange(len(probs)), order[:, 1]]
    accepted = (top1 >= thr["min_confidence"]) & ((top1 - top2) >= thr["min_margin"])
    correct = order[:, 0] == y_true
    n = int(accepted.sum())
    return {"coverage": n / len(probs), "n_accepted": n,
            "accepted_accuracy": float(correct[accepted].mean()) if n else None}


def save_confusion_png(cm, names, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(max(6, len(names) * 0.7), max(5, len(names) * 0.6)))
    ax.imshow(cm, cmap="Greens")
    ax.set_xticks(range(len(names)), names, rotation=60, ha="right", fontsize=7)
    ax.set_yticks(range(len(names)), names, fontsize=7)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            if cm[i, j]:
                ax.text(j, i, int(cm[i, j]), ha="center", va="center", fontsize=6,
                        color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default="data/PlantVillage")
    ap.add_argument("--out-dir", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--crops", nargs="+", default=["tomato", "potato"])
    ap.add_argument("--epochs", type=int, default=8, help="epochs with the base frozen")
    ap.add_argument("--fine-tune-epochs", type=int, default=6)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--weights", default="imagenet", choices=["imagenet", "none"],
                    help="'none' is for pipeline smoke tests only; it gives a meaningless model")
    ap.add_argument("--target-accuracy", type=float, default=0.95,
                    help="accuracy required on accepted predictions when choosing thresholds")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    import tensorflow as tf
    from sklearn.metrics import classification_report, confusion_matrix
    from sklearn.utils.class_weight import compute_class_weight

    tf.keras.utils.set_random_seed(args.seed)
    art = os.path.join(args.out_dir, "artifacts")
    os.makedirs(art, exist_ok=True)

    # 1-2. load, inspect, split
    df = discover(args.data_dir, tuple(c.lower() for c in args.crops))
    print("\nImages per class:\n", df["class_key"].value_counts().sort_index().to_string())
    classes = sorted(df["class_key"].unique())
    idx = {c: i for i, c in enumerate(classes)}
    df = split_dataset(df, args.seed)
    df["label"] = df["class_key"].map(idx)
    df[["path", "class_key", "group", "split"]].to_csv(os.path.join(art, "splits.csv"), index=False)
    print("\nSplit sizes:\n", df["split"].value_counts().to_string())
    parts = {s: df[df["split"] == s].reset_index(drop=True) for s in ("train", "val", "test")}

    # 3-6. datasets (resize/normalise via the shared preprocessing), augmentation is inside the model
    ds = {s: make_ds(p["path"].values, p["label"].values.astype("int32"), args.batch_size, s == "train", args.seed)
          for s, p in parts.items()}
    cw = compute_class_weight("balanced", classes=np.arange(len(classes)), y=parts["train"]["label"].values)
    class_weight = {i: float(w) for i, w in enumerate(cw)}

    # 7-8. transfer learning, then light fine-tuning
    model, base = build_model(len(classes), args.weights)
    cbs = [tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=3, restore_best_weights=True),
           tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=1)]
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3),
                  loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    model.fit(ds["train"], validation_data=ds["val"], epochs=args.epochs, class_weight=class_weight, callbacks=cbs)

    if args.fine_tune_epochs > 0:
        base.trainable = True
        for layer in base.layers[:-30]:
            layer.trainable = False
        for layer in base.layers:                       # keep BatchNorm statistics frozen
            if isinstance(layer, tf.keras.layers.BatchNormalization):
                layer.trainable = False
        model.compile(optimizer=tf.keras.optimizers.Adam(1e-5),
                      loss="sparse_categorical_crossentropy", metrics=["accuracy"])
        model.fit(ds["train"], validation_data=ds["val"], epochs=args.fine_tune_epochs,
                  class_weight=class_weight, callbacks=cbs)

    # 9-10. evaluate on the held-out test split
    y_test = parts["test"]["label"].values
    probs_test = model.predict(ds["test"], verbose=0)
    probs_val = model.predict(ds["val"], verbose=0)
    y_val = parts["val"]["label"].values
    pred = probs_test.argmax(1)
    report_txt = classification_report(y_test, pred, labels=range(len(classes)), target_names=classes, zero_division=0)
    report = classification_report(y_test, pred, labels=range(len(classes)), target_names=classes,
                                   zero_division=0, output_dict=True)
    cm = confusion_matrix(y_test, pred, labels=range(len(classes)))
    pd.DataFrame(cm, index=classes, columns=classes).to_csv(os.path.join(art, "confusion_matrix.csv"))
    save_confusion_png(cm, classes, os.path.join(art, "confusion_matrix.png"))
    with open(os.path.join(art, "classification_report.txt"), "w", encoding="utf-8") as f:
        f.write(report_txt)
    print("\nTEST SET RESULTS\n", report_txt)

    # thresholds: tuned on VALIDATION, then measured on TEST
    thr, sweep = choose_thresholds(probs_val, y_val, args.target_accuracy)
    sweep.to_csv(os.path.join(art, "threshold_sweep.csv"), index=False)
    thr_test = apply_thresholds(probs_test, y_test, thr)
    thr_val = apply_thresholds(probs_val, y_val, thr)
    print("Chosen thresholds:", thr, "| validation:", thr_val, "| test:", thr_test)

    # 11. save everything
    model.save(os.path.join(args.out_dir, "saved_model.keras"))
    with open(os.path.join(args.out_dir, "class_names.json"), "w", encoding="utf-8") as f:
        json.dump(classes, f, indent=2)
    with open(os.path.join(args.out_dir, "thresholds.json"), "w", encoding="utf-8") as f:
        json.dump(thr, f, indent=2)
    metrics = {
        "dataset": {"images": int(len(df)), "per_split": {k: int(len(v)) for k, v in parts.items()},
                    "classes": classes, "weights": args.weights,
                    "note": "Measured on PlantVillage-style images only; not evidence of field performance."},
        "test_accuracy": float(report["accuracy"]),
        "test_macro_f1": float(report["macro avg"]["f1-score"]),
        "per_class": {c: {k: float(report[c][k]) for k in ("precision", "recall", "f1-score", "support")} for c in classes},
        "thresholds": thr,
        "thresholds_on_validation": thr_val,
        "thresholds_on_test": thr_test,
    }
    with open(os.path.join(art, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nSaved model + artifacts to {args.out_dir}")
    if args.weights == "none":
        print("NOTE: --weights none was used. This model is for smoke-testing the pipeline only.")


if __name__ == "__main__":
    main()
