# Dataset setup guide

Datasets are **not** committed to Git (see `.gitignore`). Put them here before training.

## 1. PlantVillage (training data)

KisanLens trains on the **tomato** and **potato** classes of PlantVillage:

| Crop | Classes used (folder names vary slightly between copies) |
|---|---|
| Potato | Early blight, Late blight, Healthy |
| Tomato | Bacterial spot, Early blight, Late blight, Leaf Mold, Septoria leaf spot, Spider mites (two-spotted), Target Spot, Yellow Leaf Curl Virus, Mosaic virus, Healthy |

**Where to get it** (pick one; all are copies of the same research dataset)

- Kaggle: search for "PlantVillage" (several uploads exist; look for a copy that has folders such as `Tomato_Early_blight`, `Potato___Late_blight`).
- TensorFlow Datasets: `plant_village` (54,303 images, 38 classes; it is a republished, un-augmented copy).
- Original paper: Hughes, D. P. & Salathé, M. (2015), *An open access repository of images on plant health to enable the development of mobile disease diagnostics through machine learning and crowdsourcing*, arXiv:1511.08060.

**License: check before you rely on it.** The TensorFlow Datasets page does not state a dataset-specific
license (it notes the original data is no longer hosted at plantvillage.org and points to the republisher's terms), and
Kaggle copies carry their own, sometimes different, license labels. Read the license on the exact copy you download,
cite Hughes & Salathé (2015), and confirm that your use (hackathon demo, publication, commercial use) is allowed
before you distribute the data or a model trained on it.

**Expected layout** (the script discovers any folder whose name starts with `tomato` or `potato`;
other crops in the same download are ignored):

```
data/PlantVillage/
├── Potato___Early_blight/*.jpg
├── Potato___Late_blight/*.jpg
├── Potato___healthy/*.jpg
├── Tomato_Bacterial_spot/*.jpg
├── Tomato_Early_blight/*.jpg
└── ...
```

A one-level extra folder (`data/PlantVillage/PlantVillage/<classes>`) is also handled.

## 2. Real-world test photos (strongly recommended)

PlantVillage leaves are photographed on plain backgrounds. Before claiming the app works in the field, collect your
own photos (phone camera, real fields, mixed lighting) and test them. Use one folder per class, named with the class keys
from `model/class_names.json`:

```
data/realworld/
├── tomato_early_blight/*.jpg
├── tomato_healthy/*.jpg
└── potato_late_blight/*.jpg
```

Then run `python -m model.evaluate_realworld --dir data/realworld`. Have an agronomist confirm the labels, and never
use these images for training if you want an honest test.

## 3. Limits of the dataset

- Images are lab-style; accuracy on field photos is usually lower.
- Multiple photos of the same leaf can exist under different file names. The training script groups known augmented
  copies and byte-identical files together, but it cannot detect every near-duplicate, so reported test accuracy can
  still be optimistic.
- Class sizes are very unbalanced (e.g. few healthy potato images); class weights are used and per-class recall is reported.
