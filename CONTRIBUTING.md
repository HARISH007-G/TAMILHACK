# Contributing to AI-Based Palm Leaf Manuscript Reader

Welcome to the **AI-Based Palm Leaf Manuscript Reader** project! This repository is being actively developed for **THAMIZH HACK FEST 2026** (October 15–16).

This guide outlines our collaborative git workflow, branch strategy, testing requirements, and communication protocols for our four-member development team.

---

## 1. Team Role & Branch Architecture

To prevent merge conflicts and ensure clean integration, each member owns a dedicated domain and feature branch:

| Role | Domain / Responsibilities | Dedicated Branch | Primary Files Owned |
| :--- | :--- | :--- | :--- |
| **Team Leader** | Integration, end-to-end pipeline, app workflow, and release engineering | `feature/integration` | `app.py`, pipeline coordination, deployment configs |
| **Member 2** | Image preprocessing, text-line segmentation, binarization, crop extraction | `feature/segmentation` | `scripts/segment_palm_leaf_lines.py`, `scripts/curate_dataset_crops.py` |
| **Member 3** | Tamil OCR inference, ONNX/Paddle runtime, character decoding, confidence scoring | `feature/ocr` | `scripts/benchmark_ocr_engines.py`, `models/`, OCR engine wrappers |
| **Member 4** | Web UI, responsive layouts, text editor, side-by-side comparison, export (TXT/JSON) | `feature/frontend` | `templates/`, `static/css/`, `static/js/` |

> [!IMPORTANT]
> The `main` branch is protected and reserved exclusively for stable, demo-ready code. Never commit or push directly to `main`. All changes must merge via tested Pull Requests.

---

## 2. Setting Up Your Local Environment

### Step 1: Clone the Repository
```bash
git clone https://github.com/HARISH007-G/OLAITOTEXT.git
cd OLAITOTEXT
```

### Step 2: Configure Git Identity
Ensure your commits reflect your name and institutional email:
```bash
git config user.name "Your Full Name"
git config user.email "your.email@bitsathy.ac.in"
```

### Step 3: Set Up Python Environments
Because the legacy TensorFlow CNN application and modern ONNX/RapidOCR tools have different dependency trees, we maintain two clean configurations:

1. **Core Web App Environment (Flask + TensorFlow 2.12):**
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **OCR & Segmentation Environment (Python 3.10+):**
   ```bash
   python -m venv venv-modern-ocr
   # On Windows:
   .\venv-modern-ocr\Scripts\activate
   pip install -r requirements-ocr.txt
   ```

---

## 3. Daily Git Workflow

### Step 1: Sync Your Local Repository
Always start by fetching the latest changes from `origin`:
```bash
git checkout main
git pull origin main
```

### Step 2: Switch to or Create Your Feature Branch
```bash
# Check out your assigned branch (e.g. for Member 2)
git checkout -b feature/segmentation origin/main
# Or if branch already exists:
git checkout feature/segmentation
git merge main
```

### Step 3: Work in Isolation & Commit Cleanly
- Make small, atomic commits with informative commit messages following Conventional Commits format:
  - `feat(segmentation): implement adaptive horizontal valley threshold`
  - `fix(frontend): resolve text editor sync on mobile viewport`
  - `docs(ocr): update model dictionary reference notes`
- Check status before committing:
  ```bash
  git status
  ```
- **Never stage virtual environments or scratch files**: Ensure `venv/`, `.env`, and temporary outputs are not staged.

### Step 4: Run Mandatory Quality Tests Before Pushing
Before pushing any commit, run the dataset quality test suite to verify no regressions were introduced:
```bash
.\venv-modern-ocr\Scripts\python.exe scripts\test_dataset_quality.py
```
Ensure all 9 tests pass cleanly (`Ran 9 tests in ... OK`).

### Step 5: Push and Open a Pull Request
Push your feature branch to GitHub:
```bash
git push -u origin feature/segmentation
```
Navigate to GitHub and create a Pull Request against `main`.

---

## 4. Conflict Avoidance & Shared File Policy

1. **Avoid Editing Shared Files Simultaneously:**
   - If you need changes to `app.py`, coordinate directly with the Team Leader.
   - If frontend needs a new API route, agree on the JSON request/response schema before implementation.
2. **Never Commit Secrets:**
   - No passwords, GitHub tokens, or cloud API keys in repository files. Use `.env.example` as a template for local variables.
3. **Preserve Master Assets:**
   - Never overwrite or modify `static/input/` images or `reports/dataset_curation/dataset_manifest.csv` without prior team consensus.

---

## 5. Reporting Blockers

If you encounter an issue that halts your progress (e.g., ONNX model runtime crash, dependency conflict, Git merge conflict):
1. **Do not force-push or reset history.**
2. Post a descriptive blocker message in the team chat containing:
   - What you were attempting to do.
   - The exact error traceback or terminal output.
   - Your current git branch and commit hash (`git rev-parse HEAD`).
3. Notify the Team Leader immediately for pair-debugging.
