"""Pipeline tests on recorded PaddleOCR output (tests/fixtures) — no OCR service needed."""
import json
from pathlib import Path

from app.pipeline import analyze_ocr, load_rules
from app.pipeline.extract import group_rows

FIX = Path(__file__).parent / "fixtures"


def run(name):
    r = analyze_ocr(json.loads((FIX / f"{name}.ocr.json").read_text()), load_rules())
    return r, {f["id"]: f for f in r["fields"]}


def test_compliant_label_passes_all_fields():
    r, f = run("compliant")
    assert r["status"] == "compliant", [(k, v["status"], v["messages"]) for k, v in f.items()]
    assert f["net_quantity"]["value"] == "1 kg"
    assert f["mrp"]["value"] == "Rs. 145.00"
    assert f["packing_date"]["value"] == "08/2026"
    assert "411019" in f["manufacturer"]["value"]


def test_noncompliant_label_flags_violations():
    r, f = run("noncompliant")
    assert r["status"] == "non_compliant"
    assert f["net_quantity"]["status"] == "fail"  # "gms"
    assert f["mrp"]["status"] == "fail"  # no "inclusive of all taxes"
    assert f["packing_date"]["status"] == "missing"
    assert f["consumer_care"]["status"] == "missing"
    assert f["unit_sale_price"]["status"] == "review"  # conditional field
    assert "Ingredients" not in f["manufacturer"]["value"]  # stop keyword ends capture


def line(text, y, x=0, h=20, conf=0.99):
    return {"text": text, "confidence": conf, "box": [x, y, x + 200, y + h]}


def test_rows_merge_boxes_on_same_line():
    rows = group_rows([line("Rs. 50", 102, x=210), line("MRP", 100), line("Net Wt 1 kg", 200), line("Pkd 01/26", 198, x=600)])
    assert [r["text"] for r in rows] == ["MRP Rs. 50", "Net Wt 1 kg", "Pkd 01/26"]  # wide gap = separate column


def test_mrp_split_across_lines_and_low_confidence_goes_to_review():
    ocr = {"lines": [line("M.R.P.", 0, conf=0.6), line("Rs.99.00 incl. of all taxes", 40, conf=0.6)]}
    f = {x["id"]: x for x in analyze_ocr(ocr, load_rules())["fields"]}
    assert f["mrp"]["value"] == "Rs.99.00"
    assert f["mrp"]["status"] == "review"


def test_mfd_by_is_not_mistaken_for_a_date():
    ocr = {"lines": [line("Mfd. by: ABC Foods, Delhi 110001", 0), line("Pkd: JAN 2026", 40)]}
    f = {x["id"]: x for x in analyze_ocr(ocr, load_rules())["fields"]}
    assert f["packing_date"]["value"] == "JAN 2026"


def test_two_column_skewed_label():
    # Real PaddleOCR output on a perspective-warped two-column panel (tests/samples/hard.jpg).
    r, f = run("hard")
    assert r["status"] == "compliant", [(k, v["status"], v["messages"]) for k, v in f.items()]
    assert "388001" in f["manufacturer"]["value"] and "Pkd" not in f["manufacturer"]["value"]
    assert f["packing_date"]["value"] == "03/2026"
    assert f["unit_sale_price"]["value"] == "53,00 per 100 g"  # currency sign lost in OCR, still found


def test_barcode_registry_mrp_mismatch():
    # mustard_oil.jpg: EAN-13 read from the label photo; demo registry says MRP Rs. 199, label says Rs. 210.
    r, f = run("mustard_oil")
    assert r["barcode"]["code"] == "8901234100028" and r["barcode"]["valid_checksum"] and r["barcode"]["gs1_org"] == "India"
    assert any("registry MRP Rs. 199.00" in m for m in f["mrp"]["messages"])
    assert f["manufacturer"]["status"] == "fail"  # no PIN code
    assert r["status"] == "non_compliant" and r["penalty"]["amount"] == 25000


def test_unit_sale_price_must_match_mrp_over_quantity():
    r, f = run("face_wash")  # Rs. 199 / 100 ml = Rs. 1.99 per ml, label says Rs. 2.49 per ml
    assert f["unit_sale_price"]["status"] == "fail"
    assert "expected Rs. 1.99 per ml" in f["unit_sale_price"]["messages"][0]
    assert f["commodity_name"]["value"] == "Neem Face Wash"


def test_gtin_check_digit():
    from app.pipeline.barcode import gtin_valid
    assert gtin_valid("8901234100011") and gtin_valid("4006381333931") and not gtin_valid("8901234100012")


def test_real_photo_label_value_table():
    # Real phone photo of a snack pack (tilted, glossy). Values sit in a column right of their labels,
    # "MRP (INCL. OF / ALL TAXES)" spans two lines, and "Manufactured by" is cropped off the top.
    r, f = run("real_mexilla")
    assert (f["net_quantity"]["value"], f["packing_date"]["value"], f["mrp"]["value"]) == ("75g", "08/09/26", "Rs. 20.00")
    assert f["mrp"]["status"] == "pass" and f["unit_sale_price"]["status"] == "pass"  # Rs 0.27/g ~ 20/75
    assert f["manufacturer"]["status"] == "review" and "201307" in f["manufacturer"]["value"]  # PIN-address fallback
    assert r["barcode"]["code"] == "8904063214560" and r["barcode"]["valid_checksum"]
    assert r["status"] == "needs_review"


def test_barcode_photo_from_a_different_pack_is_flagged():
    from app.pipeline import analyze_ocr, load_rules
    ocr = json.loads((FIX / "real_mexilla.ocr.json").read_text())
    photo = [{"data": "8901491100267", "type": "EAN_13", "source": "barcode_photo"}]
    r = analyze_ocr(ocr, load_rules(), photo + [dict(b, source="label") for b in ocr["barcodes"]])
    assert "8904063214560" in r["barcode"]["mismatches"][0]
