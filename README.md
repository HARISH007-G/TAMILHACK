# MARAPOLI (மரபொலி) — Tamil Heritage Digital Archive

> **“தமிழ் மரபின் குரல் • தலைமுறைகளை இணைக்கும் தொழில்நுட்பம்”**  
> **Thamizh Hack Fest 2026 — Problem Statement P4: Digital Preservation of Tamil Oral History**

[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](http://creativecommons.org/licenses/by-nc-sa/4.0/)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Framework: Flask](https://img.shields.io/badge/Framework-Flask%202.3-green.svg)](https://flask.palletsprojects.com/)

---

## 1. Project Description
**MARAPOLI (மரபொலி)** is a unified AI-powered Tamil heritage preservation platform. Its primary flagship feature preserves Tamil oral histories, elders' memories, traditional knowledge, and dialect stories through speech-to-text transcription and a searchable heritage library. Its secondary feature digitizes ancient Tamil palm-leaf manuscripts (*Olai Chuvadi*) using computer vision and deep learning character recognition.

---

## 2. Problem Statement
Centuries-old palm-leaf manuscripts suffer from severe physical degradation:
- **Incised Stylus Strokes:** Characters are physically incised onto dried Palmyra leaf strips without print ink, creating low contrast.
- **Surface Deterioration:** Fading soot ink, natural leaf grain striations, biological staining, and surface abrasions around binding cord holes.
- **Orthographic Complexity:** Historical Tamil features delicate $1\dots 3\text{ px}$ pulli marks (`்`), upper vowel loops (`ி`, `ீ`), and script ligatures that conventional Latin-centric OCR engines fail to recognize.
- **Marginalia Bleed-in:** Unstructured line extractors often merge marginal chapter headings into verse text, distorting transcriptions.

---

## 3. Main Objective
Deliver a robust, inspectable, and collaborative end-to-end manuscript digitization system that:
1. Segregates left-margin heading metadata from core poetic verse couplets (*Tirukkural*).
2. Segment text lines deterministically without destructive binarization.
3. Evaluates and benchmarks Tamil character- and sequence-level recognition models (73-class CNN, Tesseract 5 Tamil, and PP-OCRv3 Tamil sequence recognizers).
4. Provides a collaborative web workspace for transcription verification and export.

---

## 4. Current Implementation Status
- **Web Application:** Functional prototype featuring home/team overview, manuscript character recognition, and ancient numeral recognition interfaces.
- **Segmentation Engine:** Deterministic horizontal valley projection algorithm isolating individual text lines from raw manuscript folios.
- **Dataset Curation (Phase E Completed):** 80 curated records derived from 60 original lines across 12 leaves, isolating 10 margin headings from 10 core verse strips, with full SHA-256 cryptographic provenance.
- **Quality Assurance:** 9 automated data-integrity regression tests passing in 0.32s.
- **Modern OCR Integration:** Tested ONNX Runtime inference engine using `ta_PP-OCRv3_rec` and matching Tamil character dictionary.

---

## 5. Existing Features Confirmed by Code Inspection
1. **Flask Web Application (`app.py`):**
   - Routing for `/` (Team & Project overview), `/characters` (manuscript line upload & prediction), `/numerals` (ancient Tamil numeral recognition).
   - In-memory base64 image encoding and HTML rendering.
2. **Keras CNN Classifiers:**
   - `Thirukkural.model`: 73-class CNN model for segmented Tamil characters.
   - `Numerals.model`: CNN classifier trained on Tamil historical numerals.
3. **Manuscript Line Segmenter (`scripts/segment_palm_leaf_lines.py`):**
   - Bounded horizontal projection profile segmenter generating crops and JSON coordinate manifests.
4. **Margin Segregator (`scripts/curate_dataset_crops.py`):**
   - Sobel vertical edge valley detector splitting left-margin chapter titles from poetic verses.
5. **Quality Test Suite (`scripts/test_dataset_quality.py`):**
   - 9 regression tests verifying bounding box containment, crop decodability, SHA-256 hashes, and leakage prevention.

---

## 6. Technology Stack
- **Backend:** Python 3.10+, Flask 2.3.2, Werkzeug
- **Deep Learning / Vision:** TensorFlow 2.12.0, Keras, OpenCV 4.7+, ONNX Runtime 1.23.2, RapidOCR-ONNX
- **OCR Backends:** Native 73-class CNN, PaddleOCR Tamil PP-OCRv3 (ONNX export), Tesseract OCR 5 (`tam.traineddata`)
- **Frontend:** HTML5, CSS3, JavaScript, Jinja2 Templates
- **Testing & Tooling:** Python `unittest`, NumPy, pandas

---

## 7. Repository Structure

```
AI_Based_Palm_Leaf_Manuscript_Reader/
├── .env.example                     # Environment configuration template
├── .gitignore                       # Clean Git exclusion rules
├── CONTRIBUTING.md                  # Team development guidelines & branching rules
├── LICENSE                          # CC BY-NC-SA 4.0 Academic License
├── README.md                        # Project documentation (this file)
├── requirements.txt                 # Flask & TensorFlow runtime dependencies
├── requirements-ocr.txt             # Modern OCR & ONNX evaluation dependencies
├── app.py                           # Flask web application entry point
├── CODE2000.TTF                     # Unicode font supporting Tamil characters
│
├── model_code/                      # CNN inference helper modules
│   ├── characters.py                # Character preprocessing and model inference
│   └── numerals.py                  # Numeral preprocessing and classification
│
├── Thirukkural.model/               # SavedModel: 73-class Tamil character CNN
├── Numerals.model/                  # SavedModel: Tamil historical numerals CNN
│
├── models/                          # Modern OCR models & dictionaries
│   ├── onnx_tamil/rec/              # ONNX PP-OCRv3 Tamil recognizer & dict.txt
│   └── paddle_tamil/                # PaddleOCR inference weights & archive
│
├── tessdata/                        # Tesseract 5 Tamil language data (tam.traineddata)
│
├── static/                          # Static web assets
│   ├── css/                         # Application stylesheets
│   ├── js/                          # Client-side scripts
│   ├── img/                         # Logos, team photos, UI assets
│   └── input/                       # Master manuscript scans (image1 - image12)
│
├── templates/                       # Jinja2 HTML templates
│   ├── login.html                   # Project & team home page
│   ├── characters.html              # Character upload and recognition view
│   └── upload.html                  # Legacy upload interface
│
├── scripts/                         # Research, segmentation, and evaluation tools
│   ├── curate_dataset_crops.py      # Phase E margin segregation pipeline
│   ├── audit_dataset_quality.py     # Manifest & cryptographic hash generator
│   ├── test_dataset_quality.py      # Automated dataset quality test suite (9 tests)
│   ├── segment_palm_leaf_lines.py   # Palm-leaf line segmentation script
│   └── benchmark_ocr_engines.py     # Multi-engine OCR benchmark runner
│
├── reports/                         # Research, benchmark, and curation outputs
│   ├── dataset_curation/            # Phase E curated manifest, crops, and overlays
│   │   ├── dataset_manifest.csv     # 80-record audited dataset manifest
│   │   ├── segmentation_review.csv  # Line-by-line boundary audit
│   │   ├── augmentation_research.md # Script-aware augmentation guidelines
│   │   ├── dataset_quality_report.md# Final Phase E quality report
│   │   ├── crops/                   # 20 segregated crops (10 margin + 10 verse)
│   │   └── overlays/                # 60 visual boundary inspection overlays
│   ├── ground_truth/                # Ground truth manifests and audit notes
│   ├── ocr_benchmark/               # Multi-engine benchmark results and audits
│   └── segmentation/                # 60 original line crops and 12 JSON manifests
│
└── docs/                            # Architectural design and research documents
```

---

## 8. Prerequisites
- **Operating System:** Windows 10/11, Ubuntu 20.04+, or macOS
- **Python:** Python 3.10.x recommended
- **Git:** Git 2.30+
- **Hardware:** Minimum 8 GB RAM; Intel Core i3 or equivalent (CPU inference supported)

---

## 9. Installation Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/selvapriya214/VOICETOTEXT.git
cd VOICETOTEXT
```

### 2. Configure Local Settings
```bash
cp .env.example .env
```

---

## 10. Virtual Environment & Dependency Setup

Due to differing library requirements between TensorFlow 2.12 and modern ONNX sequence recognizers, we maintain two clean environment profiles:

### Profile A: Web Application Environment (Flask + TensorFlow)
```bash
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### Profile B: OCR Research & Quality Test Environment (ONNX + RapidOCR)
```bash
python -m venv venv-modern-ocr
# On Windows PowerShell:
.\venv-modern-ocr\Scripts\activate
# On Linux/macOS:
source venv-modern-ocr/bin/activate

pip install -r requirements-ocr.txt
```

---

## 11. Required Model Weights Setup
All necessary model weights are stored in the repository and ready for CPU inference:
- **Keras CNNs:** Located at `Thirukkural.model/` and `Numerals.model/` (tracked in repository).
- **Tamil ONNX Recognizer:** Located at `models/onnx_tamil/rec/ta_PP-OCRv3_rec/model.onnx` (8.56 MB) with matching `dict.txt` (tracked in repository).
- **Tesseract Data:** Located at `tessdata/tam.traineddata` (3.09 MB, tracked in repository).

No external downloads are required to run the basic application or quality test suite.

---

## 12. Dataset & Sample Images Setup
The master manuscript images are provided in `static/input/`:
- `image1.png` to `image12.png`: 12 high-resolution scans of Tirukkural chapters 1 through 6 from the Tamil Virtual Academy (TVA) collection.
- Sample ancient Tamil numerals located in `static/input/numerals/`.

All master scans have recorded SHA-256 hashes in `reports/dataset_curation/dataset_manifest.csv`.

---

## 13. Application Launch Instructions
Activate the web application virtual environment and run Flask:

```bash
.\venv\Scripts\activate
python app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000/
```
- Click **"Start Here"** to access the character recognition page.
- Select sample images from `static/input/` to test upload and recognition.

---

## 14. How to Run Dataset Quality Tests
To verify data integrity, bounding box containment, and margin segregation:

```bash
.\venv-modern-ocr\Scripts\activate
python scripts/test_dataset_quality.py
```

Expected output:
```
.........
----------------------------------------------------------------------
Ran 9 tests in 0.321s

OK
```

> [!NOTE]
> Passing the nine dataset quality tests verifies cryptographic provenance, geometric boundary safety, crop decodability, and margin isolation. It guarantees that the dataset manifest is internally consistent; it does not measure or prove OCR transcription accuracy.

---

## 15. Known OCR Limitations
1. **Character-Level CNN Accuracy:** The legacy 73-class CNN requires isolated single-glyph segmentations and suffers from character over-segmentation on complex cursive ligatures.
2. **Modern Sequence Model Baseline:** The unmodified `ta_PP-OCRv3_rec` model was trained on modern printed Tamil. When applied to historical manuscripts without fine-tuning, error rates are elevated due to historical scribal cursive style and ink fading.
3. **Physical Abrasion:** Severely abraded leaves around cord holes (`image4.jpg`, lines 3–4) require human paleographic transcription and cannot be reliably decoded automatically.

---

## 16. Dataset Provenance & Verification Status
In accordance with scientific standards established in Phase E:
- **Total Records:** 80 curated entries in `reports/dataset_curation/dataset_manifest.csv`.
- **Verified from Source Evidence ($N = 10$):** Segregated margin headings directly verified from folio inscriptions (`REC_MH_001`–`REC_MH_010`).
- **Plausible but Unverified ($N = 57$):** 47 clean full-line crops and 10 segregated core-verse crops. Their text corresponds to canonical Tirukkural verses matching the manuscript folios, but they await certified diplomatic sign-off by a human epigraphist.
- **Requires Paleographic Review ($N = 13$):** 10 unsegregated margin lines, 2 cord-hole damaged lines, and 1 authentic scribal variant.

---

## 17. Four-Member Contribution Structure

| Role | Member / Lead | Domain Focus | Key Deliverables |
| :--- | :--- | :--- | :--- |
| **Team Leader** | Harikrishnan S | System Integration & Pipeline Coordination | End-to-end routing, backend integration, deployment config |
| **Member 2** | Member 2 | Preprocessing & Line Segmentation | Adaptive line segmentation, noise removal, clean crop export |
| **Member 3** | Member 3 | OCR Inference & Tamil Text Engine | ONNX sequence inference, confidence scoring, text decoding |
| **Member 4** | Member 4 | Frontend, Text Editor & Export | Responsive UI, side-by-side comparison, TXT/JSON export |

---

## 18. Team Development Workflow
Please consult [`CONTRIBUTING.md`](CONTRIBUTING.md) for full branch policies, commit guidelines, and pull request procedures:
1. Always work on your designated feature branch (`feature/integration`, `feature/segmentation`, `feature/ocr`, `feature/frontend`).
2. Run `python scripts/test_dataset_quality.py` before committing.
3. Open a Pull Request into `main` for review. Never force-push or push directly to `main`.

---

## 19. License & Institutional Acknowledgements
- **License:** [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)](http://creativecommons.org/licenses/by-nc-sa/4.0/). Free for academic and research use with mandatory citation.
- **Institutional Heritage:**
  - Tamil Technology Research Center (TTRC), Bannari Amman Institute of Technology (BIT)
  - Tamil Virtual Academy (TVA) for manuscript digital archives
  - Tamil University, Thanjavur
  - Yakkai Arakattalai
  - Special thanks to Dr. K. Muthukumar (Kongunadu Arts & Science College)
