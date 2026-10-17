import io
import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402

H = {"X-Requested-With": "KisanLens"}


class StubPredictor:
    """Test double for the trained model. Used ONLY in tests."""
    available = True
    error = None
    thresholds = {"min_confidence": 0.7, "min_margin": 0.2, "calibrated": False}
    classes = ["tomato_early_blight", "tomato_healthy", "potato_late_blight"]

    def __init__(self, warnings=None, confidence=0.93, key="tomato_early_blight"):
        self.warnings, self.confidence, self.key = warnings or [], confidence, key

    def status(self):
        return {"available": True, "num_classes": 3, "classes": self.classes,
                "thresholds": self.thresholds, "error": None}

    def predict(self, img, selected_crop=None):
        rest = (1 - self.confidence) / 2
        return {"class_key": self.key, "confidence": self.confidence, "margin": self.confidence - rest,
                "top3": [{"class_key": self.key, "confidence": self.confidence},
                         {"class_key": "tomato_healthy", "confidence": rest},
                         {"class_key": "potato_late_blight", "confidence": rest}],
                "predicted_crop": self.key.split("_")[0], "warnings": self.warnings,
                "reliable": not self.warnings, "thresholds": self.thresholds}


def make_image(fmt="JPEG", size=(300, 300), color=(40, 140, 60)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, fmt)
    buf.seek(0)
    return buf


def upload(client, data, name="leaf.jpg", crop="tomato", headers=H):
    return client.post("/api/predict", data={"crop": crop, "image": (data, name)},
                       content_type="multipart/form-data", headers=headers)


@pytest.fixture
def app_factory(tmp_path):
    def _make(predictor=None):
        cfg = {"TESTING": True, "SECRET_KEY": "test", "DB_PATH": str(tmp_path / "t.db"),
               "UPLOAD_DIR": str(tmp_path / "uploads"), "MODEL_DIR": str(tmp_path / "no_model")}
        if predictor is not None:
            cfg["PREDICTOR"] = predictor
        return create_app(cfg)
    return _make


@pytest.fixture
def client_nomodel(app_factory):
    return app_factory().test_client()


@pytest.fixture
def client(app_factory):
    return app_factory(StubPredictor()).test_client()
