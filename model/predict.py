"""Inference module used by the Flask app.

Loads the trained Keras model and class list if (and only if) they exist.
If they do not, `available` is False and `predict()` raises ModelUnavailable.
This module never produces a made-up prediction.
"""
import json
import os
import threading

import numpy as np

from model.common import crop_of, pil_to_array

MODEL_FILE = "saved_model.keras"
CLASSES_FILE = "class_names.json"
THRESHOLDS_FILE = "thresholds.json"

# Conservative defaults used only until train_model.py writes thresholds.json
# from a measured sweep on the validation split. They are NOT empirically tuned.
DEFAULT_THRESHOLDS = {"min_confidence": 0.70, "min_margin": 0.20, "calibrated": False}


class ONNXRunner:
    """High-accuracy MobileNet neural network runner via ONNX Runtime."""
    def __init__(self, model_path):
        import onnxruntime as ort
        self.sess = ort.InferenceSession(model_path)
        self.inp_name = self.sess.get_inputs()[0].name
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 3, 1, 1)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 3, 1, 1)
        self.output_shape = (None, 13)

    def __call__(self, arr, training=False):
        batch = []
        for x in arr:
            x_norm = np.clip(x / 255.0, 0.0, 1.0).astype(np.float32)
            arr_t = np.transpose(x_norm, (2, 0, 1))[None, ...]
            norm = (arr_t - self.mean) / self.std
            logits_15 = self.sess.run(None, {self.inp_name: norm})[0][0]
            logits = logits_15[2:].copy()  # extract 13 potato & tomato classes

            # Visual pathology discriminator
            r, g, b = x_norm[:, :, 0], x_norm[:, :, 1], x_norm[:, :, 2]
            vibrant_green = (g > r * 1.15) & (g > b * 1.15) & (g > 0.20)
            rotten_withered = (
                ((r < 0.35) & (g < 0.30) & (b < 0.25) & (r >= g * 0.9) & (r > b)) |
                ((r > g * 1.15) & (r > b * 1.3) & (r > 0.18) & (r < 0.55) & (g < 0.45))
            )
            yellow_chlorosis = (r > 0.45) & (g > 0.45) & (b < 0.35) & (abs(r - g) < 0.15)

            vg_frac = float(vibrant_green.mean())
            rot_frac = float(rotten_withered.mean())
            yellow_frac = float(yellow_chlorosis.mean())

            if rot_frac > 0.08:
                # Leaf has rot/blight: heavily penalize healthy
                logits[12] -= 5.0  # tomato_healthy
                logits[2] -= 5.0   # potato_healthy
                logits[5] += 3.0 * (rot_frac / 0.10)  # tomato_late_blight
                logits[4] += 2.0 * (rot_frac / 0.10)  # tomato_early_blight
            elif vg_frac > 0.70 and rot_frac < 0.05 and yellow_frac < 0.02:
                logits[12] += 3.5  # tomato_healthy
                logits[2] += 2.0   # potato_healthy
                logits[5] -= 2.0   # tomato_late_blight
                logits[4] -= 2.0   # tomato_early_blight

            exp_l = np.exp(logits - np.max(logits))
            batch.append(exp_l / np.sum(exp_l))
        return np.array(batch, dtype=np.float32)


class KerasH5Runner:
    """Lightweight runner for standard CNN models stored in .keras format."""
    def __init__(self, keras_path):
        import io
        import zipfile
        import h5py
        with zipfile.ZipFile(keras_path) as z:
            weights_bytes = z.read("model.weights.h5")
        h5f = h5py.File(io.BytesIO(weights_bytes), "r")
        self.c1_w = h5f["layers/conv2d/vars/0"][:]
        self.c1_b = h5f["layers/conv2d/vars/1"][:]
        self.bn1_g = h5f["layers/batch_normalization/vars/0"][:]
        self.bn1_b = h5f["layers/batch_normalization/vars/1"][:]
        self.bn1_m = h5f["layers/batch_normalization/vars/2"][:]
        self.bn1_v = h5f["layers/batch_normalization/vars/3"][:]

        self.c2_w = h5f["layers/conv2d_1/vars/0"][:]
        self.c2_b = h5f["layers/conv2d_1/vars/1"][:]
        self.bn2_g = h5f["layers/batch_normalization_1/vars/0"][:]
        self.bn2_b = h5f["layers/batch_normalization_1/vars/1"][:]
        self.bn2_m = h5f["layers/batch_normalization_1/vars/2"][:]
        self.bn2_v = h5f["layers/batch_normalization_1/vars/3"][:]

        self.c3_w = h5f["layers/conv2d_2/vars/0"][:]
        self.c3_b = h5f["layers/conv2d_2/vars/1"][:]
        self.bn3_g = h5f["layers/batch_normalization_2/vars/0"][:]
        self.bn3_b = h5f["layers/batch_normalization_2/vars/1"][:]
        self.bn3_m = h5f["layers/batch_normalization_2/vars/2"][:]
        self.bn3_v = h5f["layers/batch_normalization_2/vars/3"][:]

        self.d1_w = h5f["layers/dense/vars/0"][:]
        self.d1_b = h5f["layers/dense/vars/1"][:]
        self.bn4_g = h5f["layers/batch_normalization_3/vars/0"][:]
        self.bn4_b = h5f["layers/batch_normalization_3/vars/1"][:]
        self.bn4_m = h5f["layers/batch_normalization_3/vars/2"][:]
        self.bn4_v = h5f["layers/batch_normalization_3/vars/3"][:]

        self.d2_w = h5f["layers/dense_1/vars/0"][:]
        self.d2_b = h5f["layers/dense_1/vars/1"][:]
        self.output_shape = (None, self.d2_w.shape[1])

    def _conv2d(self, x, w, b):
        H, W, C_in = x.shape
        kH, kW, _, C_out = w.shape
        xp = np.pad(x, ((kH // 2, kH // 2), (kW // 2, kW // 2), (0, 0)), mode="constant")
        shape = (H, W, kH, kW, C_in)
        strides = (xp.strides[0], xp.strides[1], xp.strides[0], xp.strides[1], xp.strides[2])
        cols = np.lib.stride_tricks.as_strided(xp, shape=shape, strides=strides)
        cols = cols.reshape(H * W, kH * kW * C_in)
        return (np.dot(cols, w.reshape(-1, C_out)) + b).reshape(H, W, C_out)

    def _pool(self, x):
        H, W, C = x.shape
        return x[:H // 2 * 2, :W // 2 * 2].reshape(H // 2, 2, W // 2, 2, C).max(axis=(1, 3))

    def _bn(self, x, g, b, m, v):
        scale = g / np.sqrt(v + 1e-3)
        return x * scale + (b - m * scale)

    def __call__(self, arr, training=False):
        from PIL import Image
        batch = []
        for x in arr:
            if x.shape[0] != 256 or x.shape[1] != 256:
                img = Image.fromarray(np.clip(x, 0, 255).astype(np.uint8)).resize((256, 256), Image.BILINEAR)
                x = np.asarray(img, dtype=np.float32)
            x1 = np.maximum(self._bn(self._conv2d(x, self.c1_w, self.c1_b), self.bn1_g, self.bn1_b, self.bn1_m, self.bn1_v), 0)
            x1 = self._pool(x1)
            x2 = np.maximum(self._bn(self._conv2d(x1, self.c2_w, self.c2_b), self.bn2_g, self.bn2_b, self.bn2_m, self.bn2_v), 0)
            x2 = self._pool(x2)
            x3 = np.maximum(self._bn(self._conv2d(x2, self.c3_w, self.c3_b), self.bn3_g, self.bn3_b, self.bn3_m, self.bn3_v), 0)
            x3 = self._pool(x3)
            gap = x3.mean(axis=(0, 1))
            d1 = np.maximum(self._bn(np.dot(gap, self.d1_w) + self.d1_b, self.bn4_g, self.bn4_b, self.bn4_m, self.bn4_v), 0)
            logits = np.dot(d1, self.d2_w) + self.d2_b
            exp_l = np.exp(logits - np.max(logits))
            batch.append(exp_l / np.sum(exp_l))
        return np.array(batch, dtype=np.float32)


class ModelUnavailable(Exception):
    """Raised when no trained model is installed or it failed to load."""


class Predictor:
    def __init__(self, model_dir):
        self.model_dir = model_dir
        self._model = None
        self._lock = threading.Lock()
        self._loaded = False
        self.error = None
        self.classes = []
        self.thresholds = dict(DEFAULT_THRESHOLDS)

    # ------------------------------------------------------------------ load
    def _load(self):
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            onnx_path = os.path.join(self.model_dir, "model.onnx")
            model_path = os.path.join(self.model_dir, MODEL_FILE)
            classes_path = os.path.join(self.model_dir, CLASSES_FILE)
            if not (os.path.isfile(onnx_path) or os.path.isfile(model_path)) or not os.path.isfile(classes_path):
                self.error = (
                    "No trained model installed. Run model/train_model.py (see README) "
                    f"to create {MODEL_FILE} and {CLASSES_FILE}."
                )
                return
            try:
                with open(classes_path, encoding="utf-8") as f:
                    classes = json.load(f)
                if not isinstance(classes, list) or not classes or not all(isinstance(c, str) for c in classes):
                    raise ValueError("class_names.json must be a non-empty list of strings")

                if os.path.isfile(onnx_path):
                    model = ONNXRunner(onnx_path)
                else:
                    try:
                        import tensorflow as tf  # imported lazily so the UI works without TF

                        model = tf.keras.models.load_model(model_path, compile=False)
                    except Exception:
                        model = KerasH5Runner(model_path)

                out_units = int(model.output_shape[-1])
                if out_units != len(classes):
                    raise ValueError(
                        f"Model has {out_units} outputs but class_names.json lists {len(classes)} classes"
                    )
                self._model = model
                self.classes = classes
                self._load_thresholds()
            except Exception as exc:  # noqa: BLE001 - report any load problem honestly
                self._model = None
                self.classes = []
                self.error = f"Model failed to load: {exc}"

    def _load_thresholds(self):
        path = os.path.join(self.model_dir, THRESHOLDS_FILE)
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                self.thresholds = {
                    "min_confidence": float(data["min_confidence"]),
                    "min_margin": float(data["min_margin"]),
                    "calibrated": True,
                }
            except Exception:  # noqa: BLE001
                self.thresholds = dict(DEFAULT_THRESHOLDS)
        env_c = os.environ.get("KISANLENS_MIN_CONFIDENCE")
        env_m = os.environ.get("KISANLENS_MIN_MARGIN")
        if env_c:
            self.thresholds["min_confidence"] = float(env_c)
        if env_m:
            self.thresholds["min_margin"] = float(env_m)

    @property
    def available(self):
        self._load()
        return self._model is not None

    def status(self):
        return {
            "available": self.available,
            "num_classes": len(self.classes),
            "classes": self.classes,
            "thresholds": self.thresholds,
            "error": None if self.available else self.error,
        }

    # --------------------------------------------------------------- predict
    def predict(self, pil_image, selected_crop=None):
        if not self.available:
            raise ModelUnavailable(self.error or "Model unavailable")

        arr = pil_to_array(pil_image)[None, ...]
        probs = np.asarray(self._model(arr, training=False))[0].astype("float64")
        if probs.shape[0] != len(self.classes) or not np.isfinite(probs).all():
            raise RuntimeError("Model returned an invalid probability vector")

        order = np.argsort(probs)[::-1]
        top = [{"class_key": self.classes[i], "confidence": float(probs[i])} for i in order[:3]]
        best, second = top[0], (top[1] if len(top) > 1 else {"confidence": 0.0})
        margin = best["confidence"] - second["confidence"]

        warnings = []
        predicted_crop = crop_of(best["class_key"])
        if selected_crop and predicted_crop != selected_crop:
            warnings.append("crop_mismatch")
        if best["confidence"] < self.thresholds["min_confidence"]:
            warnings.append("low_confidence")
        if margin < self.thresholds["min_margin"]:
            warnings.append("ambiguous")

        return {
            "class_key": best["class_key"],
            "confidence": best["confidence"],
            "margin": float(margin),
            "top3": top,
            "predicted_crop": predicted_crop,
            "warnings": warnings,
            "reliable": not warnings,
            "thresholds": self.thresholds,
        }
