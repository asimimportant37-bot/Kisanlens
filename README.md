# KisanLens – AI-Powered Crop Health & Advisory

Upload a photo of a **tomato or potato leaf** and KisanLens shows the most likely disease (or "healthy"), the model's
confidence, the top three possibilities, and plain-language care guidance in **English and Hindi**. Built for SETU 2026.

> **Responsible use.** KisanLens is an automated estimate from a photo. It can be wrong, supports only tomato and potato,
> gives no pesticide names or doses, and does not replace an agricultural expert.

## What is implemented vs. what you still must do

| Area | Status |
|---|---|
| Responsive UI: Home, Detection, Results, Disease Library, Scan History, About | Implemented and tested |
| Flask API (`/api/health`, `/predict`, `/history`, `/history/<id>`, `/diseases`, plus `/image/<ref>`, `/model-metrics`) | Implemented and tested |
| Upload validation (decodes the image; never trusts filename/MIME), 8 MB limit, re-encoding, random file names, traversal guard | Implemented and tested |
| SQLite history, per-browser-session isolation, delete one / delete all | Implemented and tested |
| English + Hindi (`static/i18n/translations.json`, advisory text has both languages) | Implemented |
| Training pipeline (group-aware split, class weights, MobileNetV2, evaluation, threshold sweep) | Implemented; **smoke-tested on synthetic data only** |
| Inference module with uncertainty flags (low confidence, ambiguous, crop mismatch) | Implemented and unit-tested |
| **A trained model** (`model/saved_model.keras`) | **Not included. You must train it (Colab notebook provided).** Until then the app shows a "model not installed" error and never fabricates a prediction. |
| Measured accuracy / F1 | **None yet.** Appears on the About page only after you train. |
| Field (real-photo) validation | **Not done.** Use `model/evaluate_realworld.py` with your own photos. |
| Disease text review | Drafted from general agronomy knowledge; **have it checked** against the sources in the Disease Library before calling it "verified". |
| Hero/disease visuals | Original SVG illustrations. Replace with licensed photographs if you want photography. |

## Architecture

```
Browser (HTML/CSS/JS, i18n JSON)
   │  fetch + X-Requested-With header, session cookie
   ▼
Flask app.py ── validate_image() (Pillow decode, format/size/pixel checks)
   │            ├── model/predict.py  ── TensorFlow model (lazy-loaded; absent ⇒ 503 model_unavailable)
   │            │       uses model/common.py (same preprocessing as training)
   │            ├── services/disease_advisory.py (EN/HI guidance, kept separate from the prediction)
   │            └── database.py (SQLite, parameterised queries, rows scoped to session id)
   └── instance/ (kisanlens.db, uploads/, secret_key; not in Git)
```

Key design decisions:

- **No fake predictions.** `Predictor.available` is false unless both `saved_model.keras` and `class_names.json` load
  and agree on the class count. `/api/predict` then returns HTTP 503 and the UI shows an explicit error.
- **Identical preprocessing.** `model/common.py` (decode → EXIF-orient → RGB → 224×224 bilinear → float 0–255) is used by
  training and inference. MobileNetV2 scaling and the training-only augmentation are layers *inside* the saved model.
- **Honest uncertainty.** A result is flagged when confidence < `min_confidence`, the top-two margin < `min_margin`, or the
  predicted crop differs from the selected crop. Thresholds come from `model/thresholds.json`, chosen by a sweep on the
  *validation* split and then measured on the test split. Without that file, conservative defaults (0.70 / 0.20) are used and
  are marked uncalibrated.
- **Privacy.** Uploads are re-encoded to JPEG (metadata stripped), saved under random names, and served only to the session
  that owns them (`/api/image/<ref>`). History is tied to an anonymous signed-cookie session id; no accounts.

## Project structure

```
kisanlens/
├── app.py                    Flask app factory + API
├── database.py               SQLite access
├── requirements.txt, Procfile
├── model/
│   ├── common.py             shared constants + preprocessing + class-name normalisation
│   ├── train_model.py        training + evaluation + thresholds
│   ├── predict.py            inference used by Flask
│   ├── evaluate_realworld.py test on your own field photos
│   └── (created by training) saved_model.keras, class_names.json, thresholds.json, artifacts/
├── services/disease_advisory.py
├── templates/                index, detect, results, diseases, history, about, error, base
├── static/                   css/style.css, js/app.js, js/vendor/chart.umd.js, i18n/translations.json, images/
├── data/README.md            dataset setup guide
├── tests/                    pytest suite + jsdom UI smoke test
├── train_colab.ipynb         Google Colab training notebook
└── docs/PRESENTATION.md      hackathon pitch + demo script
```

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt                           # TensorFlow is large; allow a few minutes
python app.py                                             # http://127.0.0.1:5000
```

Without a model, everything works except analysis: the detect page shows a notice, and `/api/predict` returns a clear
`model_unavailable` error. Check status any time: `http://127.0.0.1:5000/api/health`.

Optional environment variables: `SECRET_KEY`, `KISANLENS_SECURE_COOKIES=1` (set behind HTTPS), `KISANLENS_CORS_ORIGINS`
(comma-separated; default is same-origin only), `KISANLENS_MODEL_DIR`, `KISANLENS_MIN_CONFIDENCE`, `KISANLENS_MIN_MARGIN`, `PORT`.

## Train the model

1. Read `data/README.md`, download PlantVillage (tomato + potato), **check the license**, and place it in `data/PlantVillage/`.
2. Easiest: open `train_colab.ipynb` in Google Colab (GPU runtime) and run the cells. Or locally:
   ```bash
   python -m model.train_model --data-dir data/PlantVillage
   ```
3. Training writes to `model/`: `saved_model.keras`, `class_names.json`, `thresholds.json`, and `model/artifacts/`
   (`metrics.json`, `classification_report.txt`, `confusion_matrix.csv/.png`, `threshold_sweep.csv`, `splits.csv`).
4. Copy those files into your project's `model/` folder (if trained in Colab) and restart the app. `/api/health` should
   report `"available": true`, and the About page will display the **measured** test accuracy and macro F1.
5. Test on real photos: `python -m model.evaluate_realworld --dir data/realworld` (layout in `data/README.md`).
   Do not describe the app as field-ready until those results support it.

What the training script does (all numbers are measured, none hard-coded): finds tomato/potato folders → canonical class
keys → group-aware stratified 70/15/15 split (augmented copies and byte-identical files stay together; leakage asserted
absent) → class weights → frozen-base MobileNetV2 head training, then light fine-tuning (BatchNorm frozen) → test-set
classification report and confusion matrix → threshold sweep on validation, evaluated on test → save.

## Testing

```bash
pytest -q                                   # 61 tests: API, validation, privacy, history, predictor logic, i18n, advisory
```

Covered: valid JPEG/PNG/WEBP; unsupported formats (including GIF/BMP/TIFF renamed `.jpg`); a text file disguised as an image;
truncated/corrupt images; oversized (>8 MB) and tiny images; model-unavailable (503, no result); low-confidence, ambiguous and
crop-mismatch flags; advisory present for every class and free of doses/named chemicals; history save/list/delete/persistence;
isolation between sessions; path traversal and SQL-injection attempts; missing CSRF header; invalid API requests; English/Hindi
translation parity and template coverage; training split leakage and threshold selection.

The API tests use a small stand-in predictor (`tests/conftest.py`) so they run without TensorFlow. The inference path itself
was also exercised with a real (untrained, synthetic-data) Keras model to confirm preprocessing parity and that augmentation
is inactive at inference.

UI smoke test (loads real pages with jsdom against a live server: language switch, upload, errors, results, save, history
search/delete, library filters, About metrics):

```bash
cd tests/ui && npm i jsdom@24 tough-cookie@4
python serve.py 5056 /nonexistent/dir &         # server WITHOUT a model
# for the with-model half, also run: python serve.py 5055 <dir containing a trained model> &
node ui_smoke.mjs                               # the script expects both servers; see its header
```

Manual checks still recommended before the demo: phone camera capture (`capture="environment"`), keyboard-only navigation,
and a visual pass at 360 px, 768 px and desktop widths in a real browser (the automated run used jsdom, which has no layout engine).

## Deployment

Any Python host works (Render, Railway, Fly.io, a VPS). Example start command: `gunicorn "app:create_app()"` (see `Procfile`).
Notes: set `SECRET_KEY` and `KISANLENS_SECURE_COOKIES=1`; the model file must be present on the server (upload it as a release
asset or use persistent storage, do not commit it); `instance/` (database + photos) needs persistent disk or history and
images vanish on redeploy; TensorFlow needs roughly 1 GB RAM; free tiers may be too small, in which case use `tensorflow-cpu`.

## Security summary

Decode-based image validation, size/pixel limits, re-encoding, random server-side names, traversal-checked paths, parameterised SQL,
signed HttpOnly SameSite=Lax session cookie, custom-header requirement on state-changing calls, same-origin CORS by default,
Content-Security-Policy with no inline scripts, `nosniff`, frame denial, and no public access to uploaded images.
Not implemented: rate limiting and user accounts (add Flask-Limiter and real auth before a public launch).

## Content review

`services/disease_advisory.py` holds the guidance text. It was drafted from general agronomy knowledge, intentionally names no
pesticides or doses, and lists reference sources (ICAR-CPRI, TNAU, UC IPM, Cornell, KVK). Have an agronomist or your local KVK
review it before presenting it as verified, and adapt wording to your region.

## Credits

PlantVillage dataset: Hughes, D. P. & Salathé, M. (2015), arXiv:1511.08060. Chart.js (MIT) is bundled in `static/js/vendor/`.
