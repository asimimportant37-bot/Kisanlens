"""Evaluate the installed model on YOUR OWN real-world leaf photos.

Folder layout (class folder names must match class_names.json keys, e.g. tomato_early_blight):

    data/realworld/
        tomato_early_blight/IMG_001.jpg
        tomato_healthy/IMG_002.jpg
        potato_late_blight/...

Run:  python -m model.evaluate_realworld --dir data/realworld

Prints accuracy, a per-class report, and how many images the uncertainty thresholds would have
flagged. PlantVillage images are taken on plain backgrounds, so expect lower numbers here.
Do not call the app "field ready" until these results justify it.
"""
import argparse
import json
import os
import sys

from PIL import Image

from model.predict import Predictor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/realworld")
    ap.add_argument("--model-dir", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--out", default=None, help="optional path to write JSON results")
    args = ap.parse_args()

    pred = Predictor(args.model_dir)
    if not pred.available:
        sys.exit(f"Model unavailable: {pred.error}")

    rows = []
    for cls in sorted(os.listdir(args.dir)):
        folder = os.path.join(args.dir, cls)
        if not os.path.isdir(folder):
            continue
        if cls not in pred.classes:
            print(f"skipping folder '{cls}': not in class_names.json")
            continue
        for fn in sorted(os.listdir(folder)):
            if os.path.splitext(fn)[1].lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            with Image.open(os.path.join(folder, fn)) as img:
                r = pred.predict(img.convert("RGB"))
            rows.append({"file": f"{cls}/{fn}", "true": cls, "pred": r["class_key"],
                         "confidence": r["confidence"], "flagged": bool(r["warnings"])})
    if not rows:
        sys.exit("No images found.")

    n = len(rows)
    correct = sum(r["true"] == r["pred"] for r in rows)
    accepted = [r for r in rows if not r["flagged"]]
    acc_ok = sum(r["true"] == r["pred"] for r in accepted)
    print(f"\nImages: {n}   accuracy: {correct / n:.1%}")
    print(f"Flagged as uncertain: {n - len(accepted)} ({(n - len(accepted)) / n:.1%})")
    if accepted:
        print(f"Accuracy on non-flagged images: {acc_ok / len(accepted):.1%} ({len(accepted)} images)")
    from collections import Counter
    wrong = Counter((r["true"], r["pred"]) for r in rows if r["true"] != r["pred"])
    for (t, p), c in wrong.most_common(10):
        print(f"  {t} -> {p}: {c}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)


if __name__ == "__main__":
    main()
