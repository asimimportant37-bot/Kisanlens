"""Shared constants and image preprocessing used by BOTH training and inference.

Keeping this in one module (with no TensorFlow import) guarantees that the
array fed to the network during training is produced exactly the way it is
produced at inference time:

    decode -> EXIF-orient -> RGB -> resize to 224x224 (PIL bilinear) -> float32 in [0, 255]

The MobileNetV2 input scaling (-1..1) and the training-only augmentation are
layers *inside* the saved Keras model, so they cannot drift apart either.
"""
import re

import numpy as np
from PIL import Image, ImageOps

IMG_SIZE = 224

# Ordered rules that map the many spellings of PlantVillage folder names onto
# one canonical class key, e.g. "Tomato__Tomato_YellowLeaf__Curl_Virus"
# and "Tomato___Tomato_Yellow_Leaf_Curl_Virus" -> "tomato_yellow_leaf_curl_virus".
_RULES = [
    (("yellow", "curl"), "yellow_leaf_curl_virus"),
    (("mosaic",), "mosaic_virus"),
    (("spider",), "spider_mites"),
    (("target",), "target_spot"),
    (("septoria",), "septoria_leaf_spot"),
    (("leaf", "mold"), "leaf_mold"),
    (("bacterial", "spot"), "bacterial_spot"),
    (("early", "blight"), "early_blight"),
    (("late", "blight"), "late_blight"),
    (("healthy",), "healthy"),
]


def canonical_key(raw_name: str) -> str:
    """Normalise a dataset folder name into a stable lowercase class key."""
    k = re.sub(r"[^a-z0-9]+", "_", raw_name.lower()).strip("_")
    crop = k.split("_")[0]
    for words, name in _RULES:
        if all(w in k for w in words):
            return f"{crop}_{name}"
    return k


def crop_of(class_key: str) -> str:
    return class_key.split("_")[0]


def pil_to_array(img: Image.Image) -> np.ndarray:
    """PIL image -> float32 array (IMG_SIZE, IMG_SIZE, 3) with values in 0..255."""
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB").resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
    return np.asarray(img, dtype=np.float32)


def load_image_array(path) -> np.ndarray:
    with Image.open(path) as img:
        img.load()
        return pil_to_array(img)
