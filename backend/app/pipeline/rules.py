"""Compliance rule engine: evaluates extracted fields against the JSON ruleset.

Per-field status: pass | fail | missing | review.  Overall: compliant | needs_review | non_compliant.
Wording on purpose: this is decision support — a human officer makes the final call.
"""
import json
import os
import re
from pathlib import Path
from statistics import median

from .units import money, quantity, unit_price

RULES_PATH = Path(os.getenv("RULES_PATH", Path(__file__).parent.parent / "rules.json"))


def load_rules(path=RULES_PATH):
    # Re-read on every call so edits to rules.json apply without a restart.
    return json.loads(Path(path).read_text())


def _usp_consistent(check, cand, cands):
    """Declared unit price vs MRP / net quantity. Unparseable inputs pass (other checks cover them)."""
    mrp, qty, usp = cands.get("mrp"), cands.get("net_quantity"), unit_price(cand["value"] or "")
    price, q = money(mrp["value"] or "") if mrp else None, quantity(qty["value"] or "") if qty else None
    if not (usp and price and q) or usp[1] != q[1]:
        return True, None
    expected = price / q[0]
    if abs(usp[0] - expected) <= check.get("tolerance", 0.02) * expected:
        return True, None
    per, unit = (100, f"100 {usp[1]}") if usp[0] < 0.1 else (1, usp[1])  # small prices read per 100 units, as on labels
    return False, (f"{check['message']}: declared Rs. {usp[0] * per:.2f} per {unit}, "
                   f"expected Rs. {expected * per:.2f} per {unit} (Rs. {price:.2f} / {qty['value']})")


def _check(check, cand, body_height, cands):
    if check["type"] == "unit_price_consistency":
        return _usp_consistent(check, cand, cands)
    if check["type"] == "min_height_ratio":
        return body_height > 0 and cand["height"] / body_height >= check["value"], None
    # Context checks also see the next line down: "MRP (INCL. OF" / "ALL TAXES): USP" is one declaration.
    text = cand["value"] if check.get("target") == "value" else f"{cand['context']} {cand.get('near', '')}"
    found = bool(re.search(check["pattern"], text or "", re.I))
    return (found if check["type"] == "regex" else not found), None  # "not_regex"


def evaluate_field(field, cand, body_height, threshold, cands=None):
    res = {"id": field["id"], "label": field["label"], "rule_ref": field.get("rule_ref"),
           "pass_message": field.get("pass_message"), "value": None, "confidence": 0.0, "box": None, "messages": []}
    if cand is None:
        if field["required"] is True:
            res.update(status="missing", messages=["Declaration not found on label"])
        else:
            res.update(status="review", messages=["Not found — required only for applicable categories; confirm"])
        return res
    res.update(value=cand["value"], confidence=cand["confidence"], box=cand["box"])
    status = "pass"
    if field["extract"].get("value_pattern") and not cand["value"]:
        status = "review"
        res["messages"].append("Declaration label found but value not readable")
    for c in field["checks"]:
        ok, detail = _check(c, cand, body_height, cands or {})
        if not ok:
            res["messages"].append(detail or c["message"])
            if c["severity"] == "fail":
                status = "fail"
            elif status == "pass":
                status = "review"
    if status == "pass" and cand["confidence"] < threshold:
        status = "review"
        res["messages"].append(
            "Declaration label not read — value inferred from the layout; verify manually" if cand.get("method") == "fallback"
            else f"Low confidence ({cand['confidence']:.0%}) — verify manually")
    res["status"] = status
    return res


def overall_status(fields):
    statuses = {f["status"] for f in fields}
    if statuses & {"fail", "missing"}:
        return "non_compliant"
    return "needs_review" if "review" in statuses else "compliant"


def summarize(result, rules):
    """Overall status, score and indicative penalty — recomputed whenever field statuses change."""
    fields = result["fields"]
    result["status"] = overall_status(fields)
    result["score"] = round(100 * sum(f["status"] == "pass" for f in fields) / len(fields))
    result["counts"] = {s: sum(f["status"] == s for f in fields) for s in ("pass", "fail", "missing", "review")}
    pen = rules.get("penalties", {})
    result["penalty"] = {
        "amount": pen.get("first_offence_max", 0) if result["status"] == "non_compliant" else 0,
        "pending_review": result["status"] == "needs_review",
        "section": pen.get("section"),
    }
    return result


def evaluate(candidates, rows, rules):
    # Typical body-text height. (Comparing to the tallest text meant comparing to the brand logo on real packs.)
    body_height = median(r["height"] for r in rows) if rows else 0
    fields = [evaluate_field(f, candidates.get(f["id"]), body_height, rules["review_threshold"], candidates) for f in rules["fields"]]
    return {"rules_version": rules["version"], "fields": fields}
