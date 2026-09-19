"""Result formatting: apply officer reviews on top of the machine result, and render the PDF report."""
import copy

from fpdf import FPDF

from .rules import load_rules, summarize

STATUS_TEXT = {
    "pass": "Pass",
    "fail": "Fail - needs review",
    "missing": "Missing",
    "review": "Needs review",
    "compliant": "Compliant",
    "needs_review": "Needs officer review",
    "non_compliant": "Likely non-compliant - needs officer review",
}


def apply_reviews(result: dict, reviews: list[dict]) -> dict:
    """reviews: oldest first, each {overrides, reviewer, created_at, note}. Returns the effective result."""
    eff = copy.deepcopy(result)
    by_id = {f["id"]: f for f in eff["fields"]}
    for r in reviews:
        for fid, o in r["overrides"].items():
            f = by_id.get(fid)
            if not f:
                continue
            if o.get("value"):
                f["value"] = o["value"]
            f["status"] = o["status"]
            f["reviewed"] = {"by": r["reviewer"], "at": r["created_at"], "note": o.get("note", ""), "machine_status": result_status(result, fid)}
    summarize(eff, load_rules())
    eff["reviewed"] = bool(reviews)
    return eff


def result_status(result, fid):
    return next(f["status"] for f in result["fields"] if f["id"] == fid)


def _latin1(s) -> str:
    # Core PDF fonts are latin-1 only.
    s = str(s or "").replace("₹", "Rs.").replace("—", "-").replace("–", "-").replace("’", "'")
    return s.encode("latin-1", "replace").decode("latin-1")


def render_pdf(scan: dict, image_path: str | None) -> bytes:
    res = scan["effective"]
    pdf = FPDF()
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "LegalMetro Scan - Label Compliance Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for k, v in [
        ("Scan ID", scan["id"]),
        ("Scanned", scan["created_at"]),
        ("Submitted by", f"{scan['user']['name']} ({scan['user']['role']})"),
        ("Source", "E-commerce listing" if scan.get("source") == "ecommerce" else "Packaging photo"),
        ("Ruleset", res["rules_version"]),
        ("Officer reviewed", "Yes" if res.get("reviewed") else "No"),
    ] + ([("Listing URL", scan["listing"]["url"])] if (scan.get("listing") or {}).get("url") else []):
        pdf.cell(0, 6, _latin1(f"{k}: {v}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 9, _latin1(f"Overall: {STATUS_TEXT[res['status']]}  (score {res.get('score', 0)}%)"), new_x="LMARGIN", new_y="NEXT")
    pen = res.get("penalty") or {}
    pdf.set_font("Helvetica", "", 10)
    if pen.get("amount"):
        pdf.cell(0, 6, _latin1(f"Indicative maximum fine (first offence, {pen['section']}): Rs. {pen['amount']:,}"), new_x="LMARGIN", new_y="NEXT")
    bc = res.get("barcode")
    if bc:
        reg = bc.get("registry")
        pdf.cell(0, 6, _latin1(
            f"Barcode: {bc['code']} ({bc['type']}, check digit {'valid' if bc['valid_checksum'] else 'INVALID'}, GS1 {bc.get('gs1_org') or '-'})"
            + (f" - registry: {reg['brand']} {reg['name']}, MRP Rs. {reg['mrp']:.2f}" if reg else " - not in registry")
        ), new_x="LMARGIN", new_y="NEXT")

    if image_path:
        try:
            pdf.image(image_path, w=70)
        except Exception:
            pass  # unreadable/unsupported image shouldn't block the report

    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    with pdf.table(col_widths=(50, 28, 16, 96), text_align="LEFT") as t:
        t.row(["Declaration (rule)", "Status", "Conf.", "Extracted value / notes"])
        pdf.set_font("Helvetica", "", 9)
        for f in res["fields"]:
            notes = "; ".join(f["messages"])
            if f.get("reviewed"):
                rv = f["reviewed"]
                notes += f"{'; ' if notes else ''}Officer {rv['by']} set to {f['status']}" + (f": {rv['note']}" if rv["note"] else "")
            t.row([
                _latin1(f"{f['label']}\n{f.get('rule_ref') or ''}".strip()),
                _latin1(STATUS_TEXT[f["status"]]),
                f"{f['confidence']:.0%}",
                _latin1(f"{f['value'] or '-'}\n{notes}".strip()),
            ])

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, _latin1(
        "Decision-support output: flagged items indicate 'needs review', not a confirmed violation. "
        "This checks label declarations under the Legal Metrology (Packaged Commodities) Rules, 2011; it does not verify "
        "product authenticity. Font-size checks are approximate (relative text height, no physical calibration)."
    ))
    return bytes(pdf.output())
