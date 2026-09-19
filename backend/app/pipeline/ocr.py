"""OCR step: send the image to the self-hosted PaddleOCR sidecar (see ocr_service/)."""
import os

import httpx

OCR_URL = os.getenv("OCR_URL", "http://127.0.0.1:8001")


class OCRError(Exception):
    pass


def run_ocr(image_bytes: bytes, filename: str = "label.jpg") -> dict:
    return _post("/ocr", image_bytes, filename)


def run_barcode(image_bytes: bytes, filename: str = "barcode.jpg") -> dict:
    return _post("/barcode", image_bytes, filename)


def _post(path, image_bytes, filename):
    try:
        r = httpx.post(f"{OCR_URL}{path}", files={"file": (filename, image_bytes)}, timeout=120)
    except httpx.HTTPError as e:
        raise OCRError(f"OCR service unreachable at {OCR_URL}: {e}") from e
    if r.status_code != 200:
        raise OCRError(f"OCR service error {r.status_code}: {r.text[:200]}")
    return r.json()
