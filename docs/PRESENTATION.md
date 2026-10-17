# KisanLens – hackathon presentation & demo script (SETU 2026)

Fill the **[brackets]** with your own measured numbers. Do not quote any figure that you did not measure.

## 3-minute pitch

**1. Problem (20 s)**
"A farmer sees spots on a tomato leaf. The nearest expert may be hours away, and by the time help arrives the disease may have spread.
Guessing, or spraying the wrong thing, costs money and harms the crop."

**2. Solution (30 s)**
"KisanLens turns a phone photo into a first opinion. Take a picture of a tomato or potato leaf. A neural network suggests the most
likely condition, shows how sure it is, explains symptoms in simple Hindi or English, and tells the farmer when to call an expert."

**3. What makes it responsible (40 s)**
- "It says when it is unsure: low confidence, two close answers, or a different crop than selected all trigger a warning."
- "It never invents a result. If the model is not installed, you get an error, not a guess."
- "It gives prevention and care guidance, but no pesticide names or doses. Those depend on local conditions and need an expert."
- "Photos are private to the user's session and can be deleted any time."

**4. How it works (30 s)**
"MobileNetV2 transfer learning on the PlantVillage dataset, trained with a leak-free split. On held-out test images it reached
**[X]% accuracy / [Y] macro F1** (measured, see About page). On **[N] real field photos** we tested separately, accuracy was **[Z]%**,
which is why every result carries an uncertainty check."
*(If you have not done a real-photo test, say so plainly: "Field validation is our next step.")*

**5. Impact and next steps (30 s)**
"Next: more crops and languages (Hindi done; Marathi, Tamil, Telugu need only a translation file), real field photos collected with
KVKs, offline mobile use, and expert review loops."

**6. Close (10 s)**
"Healthy crops, smarter farming. Please try it on your own plant."

## Live demo flow (about 2 minutes)

Prepare beforehand: model installed (`/api/health` shows `"available": true`); 3 test photos on the phone/laptop: a clear diseased leaf,
a healthy leaf, and a blurry or non-leaf image; one scan already saved.

1. **Home** – point out the hero, then flip the language selector to **हिन्दी** and back.
2. **Detection** – choose *Tomato*, drag in the clear diseased leaf (mention drag-and-drop and camera capture on phones). Click *Analyze Leaf*.
3. **Results** – read the prediction and confidence aloud, show the top three, the symptoms/prevention/management boxes, and the
   "When to consult an expert" box. Say: "Confidence is the model's score, not proof." Click **Save Result**.
4. **Show honesty** – scan the blurry or non-leaf image. Show the amber warning and the advice to retake the photo.
   *(Optional: select Potato but upload a tomato leaf to show the crop-mismatch warning.)*
5. **Disease Library** – search "blight", filter by Potato, expand one card. Mention the reference list at the bottom.
6. **Scan History** – show the saved scan, the search box and the chart; delete the scan to show privacy control.
7. **About** – show the *measured* metrics and the stated limits.
8. **Trust slide (optional)** – open `/api/health`, and mention the 61 automated tests.

## Likely judge questions

| Question | Honest answer |
|---|---|
| How accurate is it? | "[X]% on held-out PlantVillage-style test images, [Z]% on [N] real photos. Test accuracy on lab-style images overstates field performance." |
| Why not just trust the confidence? | "Neural networks can be confidently wrong, especially on unfamiliar images. We add margin and crop-consistency checks and always recommend expert confirmation." |
| Why no pesticide recommendations? | "Approved products, doses and timing depend on state regulations, crop stage and weather. A photo is not enough to prescribe." |
| What if the disease isn't supported? | "It will still pick the closest class it knows, which is why uncertainty warnings matter. The About page lists the limits." |
| Can it add more crops? | "Yes: add class folders, retrain, add advisory entries. The library and API follow the model's class list." |
| Data license? | "PlantVillage (Hughes & Salathé 2015). We checked the license of the copy we used: [state it]." |

## Slide outline (8 slides)

1. Title + tagline  2. Problem  3. Solution (screenshot of results page)  4. Architecture (use the diagram in README)
5. Model + measured results (confusion matrix from `model/artifacts/`)  6. Responsible-AI design  7. Demo (live)  8. Roadmap + team

## Screenshots to capture before presenting

Take these in a real browser at desktop and phone width and add them to a `docs/screenshots/` folder:
Home, Detection with preview, Results (confident), Results (warning), Disease Library, Scan History, Hindi version of Results.
