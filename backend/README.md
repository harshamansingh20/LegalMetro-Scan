# LegalMetro Scan — Backend

FastAPI + PostgreSQL. Label photos go through four separate, testable steps:

```
app/pipeline/ocr.py      image  -> PaddleOCR sidecar -> text lines + confidence + boxes
app/pipeline/extract.py  lines  -> reading-order rows -> candidate value per declaration
app/pipeline/rules.py    fields -> JSON ruleset (app/rules.json) -> pass/fail/missing/review, score, S.36 penalty estimate
app/pipeline/barcode.py  barcode -> GTIN check digit, GS1 prefix, registry lookup (app/products.json), MRP/qty cross-check
app/pipeline/report.py   result + officer reviews -> effective result, PDF report
```

Two processes, two virtualenvs:

| Process | Dir | Port | Why separate |
|---|---|---|---|
| OCR sidecar (PaddleOCR) | `ocr_service/` | 8001 | PaddlePaddle + OpenCV + model weights are heavy; keeping them out of the API env keeps the API light and lets OCR scale on its own |
| API | `app/` | 8000 | Auth, scans, reviews, audit log, PDF |

The API only ever talks to `OCR_URL` (localhost). No cloud OCR, no API keys, no billing.

## 1. PaddleOCR sidecar (the one non-trivial dependency)

Needs **Python 3.10–3.12**. PaddlePaddle has no wheels for 3.13/3.14 yet — the system `python3` on macOS/Homebrew may be too new.

```bash
brew install python@3.12            # or pyenv / deadsnakes on Linux
cd backend/ocr_service
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt     # ~1 GB: paddlepaddle, paddleocr, paddlex, opencv
PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True .venv/bin/uvicorn main:app --port 8001
```

**First start downloads the models** (PP-OCRv6 medium detection + recognition, ~100–200 MB) into
`~/.paddlex/official_models/`. That took ~3 minutes on a slow connection. After that it's fully offline;
startup is a few seconds. To pre-bake models (e.g. in a Docker image), start the service once during the build.
`PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` skips a connectivity probe on every start.

Check it: `curl -F file=@tests/samples/compliant.jpg localhost:8001/ocr`

Barcodes are decoded in the same sidecar with OpenCV's built-in `cv2.barcode` detector (EAN-8/13, UPC-A/E; ships with
`opencv-contrib-python`, no extra install). `/ocr` returns barcodes found on the label; `/barcode` reads a barcode
close-up without running OCR. The detector is sensitive to bar width, so it pads the image and tries several scales.

Settings (env vars):

| Var | Default | Notes |
|---|---|---|
| `OCR_DET_MODEL` / `OCR_REC_MODEL` | PaddleOCR default for `lang="en"` | e.g. `PP-OCRv6_mobile_det` / `PP-OCRv6_mobile_rec` for faster, slightly less accurate CPU inference |
| `OCR_MAX_SIDE` | 2000 | Images are EXIF-rotated then downscaled to this before OCR |
| `OCR_DET_MIN_SIDE` | 1800 | Text detection upscales so the short side is at least this. Recovers small print on chat-compressed (~1200 px) photos; set 0 to disable for speed |

Measured on an Apple Silicon Mac, CPU only: **~4–7 s per label** with the default (medium) models.
Inference is serialized behind one lock (Paddle predictors aren't thread-safe) — run more sidecar processes behind a
load balancer if you need throughput. Linux x86 with `paddlepaddle-gpu` is the production path if scans get heavy.

Troubleshooting:
- `No matching distribution found for paddlepaddle` → wrong Python version (use 3.12).
- Model download hangs → it pulls from HuggingFace/BOS mirrors; retry, or copy `~/.paddlex/official_models` from another machine.
- Very low confidences on real photos → glare/blur; the mobile app's framing guide helps, and the officer review flow exists for this.

## 2. API

```bash
brew install postgresql@16 && brew services start postgresql@16
createdb legalmetro
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env        # then set SECRET_KEY: python3 -c "import secrets; print(secrets.token_urlsafe(48))"
.venv/bin/python -m app.cli create-user officer@demo.in 'Officer@123' officer "Asha Rao (LM Inspector)"
.venv/bin/python -m app.cli create-user business@demo.in 'Business@123' business "Golden Harvest Foods"
.venv/bin/uvicorn app.main:app --port 8000     # add --host 0.0.0.0 to reach it from a physical phone on your LAN
```

Tables are created on startup. `scans`, `reviews` and `audit_log` are **append-only**, enforced by Postgres
triggers that reject `UPDATE`, `DELETE` and `TRUNCATE`. Officer overrides are new `reviews` rows; the API shows the
machine result and the effective (reviewed) result side by side.

### Endpoints

| Method | Path | Who | |
|---|---|---|---|
| POST | `/auth/login` | anyone | `{email, password}` → `{token, user}` (JWT, 12 h) |
| GET | `/auth/me` | any user | |
| POST | `/scans` | any user | multipart `file` (label photo, JPEG/PNG/WebP ≤ 12 MB), optional `barcode` (close-up) → runs the pipeline, stores the scan |
| GET | `/stats?days=30` | any user | enforcement statistics over effective results (business users: own scans only) |
| GET | `/scans` | any user | `q, status, reviewed, date_from, date_to, limit, offset`. Business users see only their own scans |
| GET | `/scans/{id}` | owner / officer | machine result, effective result, reviews, OCR lines, audit trail (officers) |
| GET | `/scans/{id}/image`, `/scans/{id}/barcode-image` | owner / officer | |
| POST | `/scans/{id}/reviews` | officer | `{overrides: {field_id: {status, value?, note?}}, note}` |
| GET | `/scans/{id}/report.pdf` | owner / officer | |
| GET | `/rules` | any user | current ruleset |

## 3. Editing the ruleset

`app/rules.json` is re-read on every scan, so edits apply without a restart. Each field has:
- `extract.keywords` — label prefixes to look for (e.g. `"net wt"`), `lookahead` rows to capture after it
- `extract.value_pattern` — regex for the value; `pattern_anywhere` searches the whole label if the keyword is missing
- `checks` — `regex` / `not_regex` / `min_height_ratio`, each with `severity: fail|review` and a message
- `required` — `true` or `"conditional"` (missing = needs review, not fail; used for unit sale price)

Bump `version` when you change it — every scan records the ruleset version it was checked against.
`penalties` holds the Section 36 figures used for the indicative penalty estimate; `rule_ref`/`description`/`pass_message`
feed the web app's rule-by-rule audit and Statutory Rules page.

`app/products.json` is a **demo** product registry (GTIN → brand, name, net quantity, MRP) used for barcode
cross-verification. Replace it with a real feed before any enforcement use.

## 4. Tests

```bash
createdb legalmetro_test
.venv/bin/pytest -q
```

`tests/test_pipeline.py` runs extraction + rules on recorded PaddleOCR output (`tests/fixtures/*.ocr.json`), no OCR
service needed. `tests/test_api.py` exercises auth, ownership, reviews, filters, PDF and the append-only triggers
against `legalmetro_test`. `tests/make_sample_labels.py` regenerates the synthetic label photos in `tests/samples/`.
