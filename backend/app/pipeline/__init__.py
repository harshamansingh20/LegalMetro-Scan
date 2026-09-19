"""OCR -> field extraction -> rule engine -> barcode cross-check -> result. Each step is its own module."""
from .barcode import analyze_barcodes
from .extract import extract_fields
from .ocr import run_barcode, run_ocr
from .rules import evaluate, load_rules, summarize


def analyze_ocr(ocr: dict, rules: dict, barcodes: list | None = None) -> dict:
    rows, candidates = extract_fields(ocr["lines"], rules)
    result = evaluate(candidates, rows, rules)
    result["barcode"] = analyze_barcodes(barcodes if barcodes is not None else ocr.get("barcodes", []), result["fields"])
    return summarize(result, rules)


def analyze_image(image_bytes: bytes, filename: str = "label.jpg", barcode_bytes: bytes | None = None):
    """Returns (ocr_output, result). A separate barcode close-up, if given, is read too."""
    ocr = run_ocr(image_bytes, filename)
    barcodes = [dict(b, source="label") for b in ocr.get("barcodes", [])]
    if barcode_bytes:
        extra = run_barcode(barcode_bytes)["barcodes"]
        # Close-up first: it's the one the user explicitly supplied for the barcode.
        barcodes = [dict(b, source="barcode_photo") for b in extra] + [b for b in barcodes if b["data"] not in {x["data"] for x in extra}]
    return ocr, analyze_ocr(ocr, load_rules(), barcodes)

