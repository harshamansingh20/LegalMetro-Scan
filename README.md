# LegalMetro-Scan ⚖️

> **Smart India Hackathon (SIH) — Problem Statement SIH26034**  
> *Software System to check compliance of Packaged Commodities under Legal Metrology (Packaged Commodities) Rules, 2011 by scanning products, images and labels.*

---

## 📌 Executive Summary

**LegalMetro-Scan** is an automated compliance surveillance and inspection ecosystem built for **Legal Metrology Officers (LMOs)**, **E-Commerce Market Regulators**, and **Consumers**. 

By combining **Open-Source Computer Vision (Tesseract OCR)**, and a **Deterministic Legal Metrology Rule Engine**, the system audits physical packaging labels and e-commerce listings against the **Legal Metrology Act, 2009** and the **Legal Metrology (Packaged Commodities) Rules, 2011**.

When non-compliance is detected, the system immediately calculates statutory compounding fines under **Section 36** and generates a court-ready, printable **Form of Inspection Memo & Statutory Notice of Violation** in PDF format.

---

## 🏛️ Statutory Legal Metrology Rules Enforced

| Rule Provision | Regulatory Requirement | System Verification | Penalty / Impact |
| :--- | :--- | :--- | :--- |
| **Rule 6(1)(a)** | Complete Name & Address of Manufacturer / Packer / Importer | Address entity parser checks street, city, state, and **mandatory 6-digit postal PIN code**. | Section 36(1) Fine |
| **Rule 6(1)(b)** | Generic or Common Name of Commodity | Verifies commodity classification against generic descriptors (rejects trademark fantasy names). | Section 36(1) Fine |
| **Rule 6(1)(c) & Rule 5** | Standard Metric SI Units for Net Quantity | Enforces Fourth Schedule SI symbols (`g`, `kg`, `ml`, `l`, `m`, `N`). **Strictly penalizes illegal abbreviations (`gms`, `gm`, `k.g.`, `litres`, `box`).** | Non-standard package violation |
| **Rule 6(1)(d)** | Month & Year of Manufacture / Packing / Import | Regex date validator checks `MM/YYYY` format and **detects post-dated future packing fraud**. | Section 36(1) Fine |
| **Rule 6(1)(e) & Rule 2(m)** | Maximum Retail Price (MRP) & Tax Declaration | Verifies mandatory statutory phrase: `"inclusive of all taxes"` or `"incl. of all taxes"`. | Section 36(1) & Section 18 |
| **Rule 6(11)** | Unit Sale Price (USP) Mandate & Mathematical Consistency | Calculates: $$\Delta = \left\| \text{Declared USP} - \frac{\text{MRP}}{\text{Net Qty}} \right\|$$ Rejects math discrepancies and unrounded pricing. | Section 36(1) Deceptive Pricing |
| **Rule 6(1)(n)** | Consumer Care Grievance Redressal (4-Channel Mandate) | Audits presence of: (1) Contact Designation, (2) Helpline Phone, (3) Email Address, and (4) Postal Address. | Section 36(1) Fine |
| **Rule 6(1)(f) & 6(10)** | Country of Origin & E-Commerce Digital Disclosures | Crawls digital listings (Amazon, Flipkart, Blinkit) to verify mandatory disclosures before purchase. | Section 36(1) Fine |
| **Section 36** | Penalty for Non-Standard Packages | Automatically applies fine schedule: **₹25,000 for 1st offence** and **₹50,000 for 2nd offence**. | Official Notice PDF |

---

## 🚀 Key Features & Capabilities

1. **Multi-Mode Ingestion**:
   * **Field Inspector Mode**: Drag & drop packaging photos, mobile camera scans, or test pre-configured real-world retail samples in 1-click.
   * **E-Commerce Surveillance Mode**: Paste an Amazon / Flipkart / Blinkit product URL to audit digital listings under Rule 6(10).
2. **Open-Source OCR Pipeline**:
   * Uses **Tesseract OCR** (Apache-2.0, fully local) plus regex-based entity parsing — no API key, no per-scan cost, works offline.
3. **Deterministic Mathematical Verifier**:
   * Validates standard unit symbols (`g` vs `gms`).
   * Automatically calculates expected Unit Sale Price (USP) across multiple denominations (per g, per 100g, per kg, per ml, per litre) and detects mathematical overcharges.
4. **Court-Admissible Legal Notice Generator**:
   * 1-click generation of the official **Inspection Memo & Show Cause Notice under Section 36 & 48** in PDF format with legal citations, defect tables, and inspector signature block.
5. **Enforcement Analytics & Pareto Dashboard**:
   * Real-time metrics on inspected products, compliance pass rate, total potential compounding penalties, and top recurring defect categories.

---

## 🛠️ Architecture & Tech Stack

```
legalmetro-scan/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes_scan.py       # Image scan, sample catalog & audit store
│   │   │   ├── routes_ecommerce.py  # E-commerce URL crawler
│   │   │   ├── routes_reports.py    # PDF Legal Notice download
│   │   │   └── routes_stats.py      # Enforcement analytics
│   │   ├── core/
│   │   │   ├── rule_engine.py       # Deterministic Legal Metrology Rule Engine
│   │   │   ├── math_verifier.py     # USP & metric unit validator
│   │   │   ├── vision_extractor.py  # Tesseract OCR + regex entity extractor
│   │   │   ├── ecommerce_scraper.py # Marketplace crawler & parser
│   │   │   └── samples_registry.py  # Realistic Indian retail sample catalog
│   │   ├── models/
│   │   │   └── schemas.py           # Pydantic data contracts
│   │   ├── services/
│   │   │   └── pdf_generator.py     # ReportLab statutory notice builder
│   │   ├── static/
│   │   │   └── index.html           # Modern enforcement dashboard (Tailwind + JS)
│   │   └── main.py                  # FastAPI application entry point
│   └── tests/
│       ├── test_api.py              # Full REST API integration tests
│       ├── test_math.py             # USP calculation & illegal unit tests
│       ├── test_rules.py            # Statutory rules coverage tests
│       └── test_pdf.py              # PDF Notice generator test
├── requirements.txt
├── pytest.ini
└── README.md
```

* **Backend Engine**: FastAPI, Python 3.11+, Pydantic V2, Uvicorn
* **AI & Vision**: Tesseract OCR (`pytesseract`), Pillow — open-source, runs locally
* **Legal Notice Engine**: ReportLab (Vector PDF generator)
* **Frontend Portal**: Tailwind CSS, FontAwesome 6, Modern Vanilla JS SPA served directly by FastAPI
* **Testing**: Pytest & TestClient (15 passing automated test suites)

---

## ⚡ Quickstart & How to Run

### 1. Set Up Virtual Environment & Dependencies
```bash
# Clone or navigate to the repository
cd legalmetro-scan

# Install the Tesseract OCR engine (one-time, system package — not pip)
brew install tesseract        # macOS
# sudo apt-get install tesseract-ocr   # Debian/Ubuntu

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Vision extraction runs entirely on local Tesseract OCR — no API key, no signup, no cost.

### 3. Run Automated Tests
```bash
pytest backend/tests/ -v
```

### 4. Launch the LegalMetro-Scan Server
```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```


---

---

## 👥 Authors & Acknowledgments

* **Smart India Hackathon (SIH)** — Team LegalMetro-Scan
* Built for the **Department of Consumer Affairs, Ministry of Consumer Affairs, Food & Public Distribution, Government of India**.
