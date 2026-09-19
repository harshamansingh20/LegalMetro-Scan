"""PaddleOCR sidecar: one endpoint, image in -> text lines + confidences + boxes out.

Runs in its own venv so PaddlePaddle's heavy deps stay out of the main backend.
Start:  .venv/bin/uvicorn main:app --port 8001
"""
import io
import os
import threading
import time

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from paddleocr import PaddleOCR
from PIL import Image, ImageOps

MAX_SIDE = int(os.getenv("OCR_MAX_SIDE", "2000"))
# Text detection upscales so the image's SHORT side is at least this. Chat apps (WhatsApp) shrink photos to ~1200 px,
# and small declaration print was then missed entirely; 1800 recovered it on a real pack (~40% slower on CPU).
DET_MIN_SIDE = int(os.getenv("OCR_DET_MIN_SIDE", "1800"))

# Model names are optional overrides (e.g. PP-OCRv6_mobile_det for speed); None = PaddleOCR default for `lang`.
ocr = PaddleOCR(
    lang="en",
    text_detection_model_name=os.getenv("OCR_DET_MODEL") or None,
    text_recognition_model_name=os.getenv("OCR_REC_MODEL") or None,
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    text_det_limit_side_len=DET_MIN_SIDE,
    text_det_limit_type="min",
)
# ponytail: one global lock — Paddle predictors aren't thread-safe; run more sidecar processes if throughput matters.
lock = threading.Lock()
app = FastAPI(title="LegalMetro Scan OCR")
barcode_detector = cv2.barcode.BarcodeDetector()  # EAN-8/13, UPC-A/E, Code 128/39 etc., bundled with opencv-contrib


def find_barcodes(bgr):
    found = {}
    pad = max(40, min(bgr.shape[:2]) // 10)  # quiet zone: tight crops fail without a white margin
    padded = cv2.copyMakeBorder(bgr, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    # The detector is tuned for a band of bar widths, so sweep a few scales and stop at the first hit.
    for scale in (1, 0.5, 0.35, 2, 0.75, 1.5):
        img = padded if scale == 1 else cv2.resize(padded, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
        ok, infos, types, pts = barcode_detector.detectAndDecodeWithType(img)
        for data, kind, quad in zip(infos, types, pts) if ok else ():
            if data and data not in found:
                xs, ys = quad[:, 0] / scale - pad, quad[:, 1] / scale - pad
                found[data] = {"data": data, "type": kind, "box": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]}
        if found:
            break
    return list(found.values())


def read_image(file: UploadFile):
    try:
        img = Image.open(io.BytesIO(file.file.read()))
        img = ImageOps.exif_transpose(img).convert("RGB")  # phone photos carry rotation in EXIF
    except Exception:
        raise HTTPException(400, "Not a readable image")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    return img, np.ascontiguousarray(np.asarray(img)[:, :, ::-1])  # PaddleOCR/OpenCV expect BGR


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/ocr")
def run_ocr(file: UploadFile = File(...)):
    img, bgr = read_image(file)
    t = time.perf_counter()
    with lock:
        r = ocr.predict(bgr)[0]
    lines = [
        {"text": text, "confidence": round(float(score), 4), "box": [int(v) for v in box]}
        for text, score, box in zip(r["rec_texts"], r["rec_scores"], r["rec_boxes"])
        if text.strip()
    ]
    return {
        "width": img.width,
        "height": img.height,
        "elapsed_ms": int((time.perf_counter() - t) * 1000),
        "lines": lines,
        "barcodes": find_barcodes(bgr),
    }


@app.post("/barcode")
def run_barcode(file: UploadFile = File(...)):
    """Barcode-only read (e.g. a close-up of the back of the pack) — no OCR, fast."""
    img, bgr = read_image(file)
    return {"width": img.width, "height": img.height, "barcodes": find_barcodes(bgr)}
