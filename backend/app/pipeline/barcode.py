"""Barcode cross-verification: GTIN check digit, GS1 prefix, registry lookup, label-vs-registry comparison."""
import json
import os
import re
from pathlib import Path

from .units import money, quantity

PRODUCTS_PATH = Path(os.getenv("PRODUCTS_PATH", Path(__file__).parent.parent / "products.json"))

# GS1 prefix -> member organisation. It tells you who issued the number, NOT the country of manufacture.
GS1_PREFIXES = [
    (0, 139, "USA / Canada"), (300, 379, "France"), (400, 440, "Germany"), (450, 459, "Japan"), (490, 499, "Japan"),
    (500, 509, "UK"), (690, 699, "China"), (729, 729, "Israel"), (800, 839, "Italy"), (840, 849, "Spain"),
    (870, 879, "Netherlands"), (880, 880, "South Korea"), (885, 885, "Thailand"), (888, 888, "Singapore"),
    (890, 890, "India"), (893, 893, "Vietnam"), (899, 899, "Indonesia"), (930, 939, "Australia"),
    (940, 949, "New Zealand"), (955, 955, "Malaysia"),
]


def gtin_valid(code: str) -> bool:
    if not re.fullmatch(r"\d{8}|\d{12,14}", code):
        return False
    digits = [int(c) for c in code]
    # Weights run 3,1,3... from the right, excluding the check digit.
    s = sum(d * (1 if i % 2 else 3) for i, d in enumerate(reversed(digits[:-1])))
    return (10 - s % 10) % 10 == digits[-1]


def gs1_org(code: str) -> str | None:
    if len(code) != 13:
        return None
    p = int(code[:3])
    return next((name for lo, hi, name in GS1_PREFIXES if lo <= p <= hi), "Other GS1 member")


def analyze_barcodes(barcodes: list[dict], fields: list[dict]) -> dict | None:
    """barcodes: [{data, type, box, source}] from the sidecar. Mutates `fields` to flag registry mismatches."""
    if not barcodes:
        return None
    b = barcodes[0]
    code = b["data"]
    out = {
        "code": code, "type": b["type"], "box": b.get("box"), "source": b.get("source", "label"),
        "valid_checksum": gtin_valid(code), "gs1_org": gs1_org(code), "others": [x["data"] for x in barcodes[1:]],
        "registry": None, "mismatches": [],
    }
    on_label = [x["data"] for x in barcodes[1:] if x.get("source") == "label"]
    if b.get("source") == "barcode_photo" and on_label:
        # Label photo and barcode photo disagree: probably two different products.
        out["mismatches"].append(f"Barcode photo ({code}) doesn't match the barcode printed on the label ({on_label[0]}) — are both photos of the same pack?")
    products = json.loads(PRODUCTS_PATH.read_text())
    entry = products["products"].get(code)
    out["registry_source"] = products["source"]
    if not entry:
        return out
    out["registry"] = entry
    by_id = {f["id"]: f for f in fields}

    def flag(fid, msg):
        out["mismatches"].append(msg)
        f = by_id.get(fid)
        if f:
            f["messages"].append(msg)
            if f["status"] == "pass":
                f["status"] = "review"  # registry may be stale; officer decides

    mrp = by_id.get("mrp", {}).get("value")
    if mrp and money(mrp) is not None and abs(money(mrp) - entry["mrp"]) > 0.01:
        flag("mrp", f"Label MRP Rs. {money(mrp):.2f} differs from registry MRP Rs. {entry['mrp']:.2f} for barcode {code}")
    qty = by_id.get("net_quantity", {}).get("value")
    lq, rq = quantity(qty or ""), quantity(entry["net_quantity"])
    if lq and rq and (lq[1] != rq[1] or abs(lq[0] - rq[0]) > 1e-6):
        flag("net_quantity", f"Label net quantity '{qty}' differs from registry '{entry['net_quantity']}'")
    return out
