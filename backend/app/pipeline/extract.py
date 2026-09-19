"""Field extraction: OCR boxes -> reading-order rows -> one candidate per mandatory declaration.

Pure functions, driven by the `extract` block of each field in rules.json.
"""
import re
from statistics import median

# How much we trust each way of finding a field (multiplied with OCR confidence).
METHOD_WEIGHT = {"keyword": 1.0, "term": 0.85, "pattern": 0.85, "fallback": 0.5}


def group_rows(lines):
    """Merge OCR boxes on the same visual line into rows, top-to-bottom, left-to-right.

    A wide horizontal gap splits a line into separate rows, so two-column label panels
    don't get glued together ("Mfd. by: X   Pkd. On: 03/2026").
    """
    boxes = sorted(lines, key=lambda l: (l["box"][1] + l["box"][3]) / 2)
    lines_ = []
    for l in boxes:
        x1, y1, x2, y2 = l["box"]
        cy = (y1 + y2) / 2
        cur = lines_[-1] if lines_ else None
        if cur and abs(cy - cur["cy"]) < 0.5 * cur["height"]:
            cur["items"].append(l)
        else:
            lines_.append({"cy": cy, "height": y2 - y1, "items": [l]})
    out = []
    for ln in lines_:
        items = sorted(ln["items"], key=lambda l: l["box"][0])
        seg = [items[0]]
        for prev, it in zip(items, items[1:]):
            if it["box"][0] - prev["box"][2] > COLUMN_GAP * ln["height"]:
                out.append(_row(seg))
                seg = []
            seg.append(it)
        out.append(_row(seg))
    return out


COLUMN_GAP = 2.0  # gap wider than 2x the text height = separate column


def _row(items):
    bs = [i["box"] for i in items]
    return {
        "text": " ".join(i["text"] for i in items),
        "confidence": sum(i["confidence"] for i in items) / len(items),
        "box": [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)],
        "height": median(b[3] - b[1] for b in bs),
    }


def _below_in_column(rows, i, n):
    """Next n rows under rows[i] that overlap it horizontally (same column)."""
    x1, _, x2, _ = rows[i]["box"]
    return [j for j in range(i + 1, len(rows)) if min(x2, rows[j]["box"][2]) > max(x1, rows[j]["box"][0])][:n]


def _right_of(rows, i, reach=2.5):
    """Rows to the right of rows[i] on roughly the same line, nearest first.

    Real labels often print a label column ("NET QUANTITY :", "MRP (INCL. OF ALL TAXES)") with the values in a
    separate column to the right; a tilted photo shifts that column up or down, hence `reach` row-heights.
    """
    x1, y1, x2, y2 = rows[i]["box"]
    cy, h = (y1 + y2) / 2, rows[i]["height"]
    near = [j for j, r in enumerate(rows) if j != i and r["box"][0] >= x2 - h
            and abs((r["box"][1] + r["box"][3]) / 2 - cy) <= reach * h]
    return sorted(near, key=lambda j: abs((rows[j]["box"][1] + rows[j]["box"][3]) / 2 - cy))


BARCODE_DIGITS = re.compile(r"[\d\s]{8,}")
PIN = re.compile(r"(?<!\d)\d{3}\s?\d{3}(?!\d)")
COMPANY = re.compile(r"\b(?:pvt|private|ltd|limited|llp|inc|corp)\b", re.I)  # "Haldiram Snacks Food Pvt Ltd" isn't a commodity
NOT_ADDRESS = re.compile(r"call|tel|phone|mobile|e-?mail|lic|fssai|batch|mrp|rs\.?|₹", re.I)


def _kw_regex(keywords):
    # Longest first so "mfd. & packed by" wins over "mfd".
    alts = "|".join(re.escape(k) for k in sorted(keywords, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alts})(?!\w)", re.I)


def _candidate(rows, idxs, method, value, context, near=""):
    used = [rows[i] for i in idxs]
    conf = sum(r["confidence"] for r in used) / len(used) * METHOD_WEIGHT[method]
    bs = [r["box"] for r in used]
    return {
        "value": value.strip(" :-–|") or None,
        "context": context,
        "near": near,  # the line right under the keyword, even if it starts another declaration — for checks only
        "confidence": round(conf, 3),
        "method": method,
        "rows": idxs,
        "height": max(r["height"] for r in used),
        "box": [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)],
    }


def extract_field(field, rows, other_kw):
    cfg = field["extract"]
    kw = _kw_regex(cfg["keywords"])
    vp = re.compile(cfg["value_pattern"], re.I) if cfg.get("value_pattern") else None
    side = re.compile(cfg.get("side_pattern") or cfg["value_pattern"], re.I) if vp else None
    look = cfg.get("lookahead", 1)

    for i, row in enumerate(rows):
        m = kw.search(row["text"])
        if not m:
            continue
        idxs = [i]
        for j in _below_in_column(rows, i, look):
            if other_kw.search(rows[j]["text"]) or BARCODE_DIGITS.fullmatch(rows[j]["text"]):
                break  # next declaration starts, or the digits printed under a barcode
            idxs.append(j)
        context = " ".join([row["text"][m.end():]] + [rows[j]["text"] for j in idxs[1:]])
        below = _below_in_column(rows, i, 1)
        near = rows[below[0]]["text"] if below else ""
        if vp:
            vm = vp.search(context)
            if not vm:  # label/value table: look for the value to the right
                for j in _right_of(rows, i):
                    sm = side.search(rows[j]["text"])
                    if sm:
                        # keep the label's own wording contiguous ("INCL. OF" + "ALL TAXES"), value after it
                        vm, idxs, context = sm, idxs + [j], f"{context} {near} {rows[j]['text']}"
                        break
            if not vm and cfg.get("require_value"):
                continue  # e.g. "Mfd. by" matched a date keyword but carries no date
            value = vm.group(0) if vm else ""
        else:
            value = context
        return _candidate(rows, idxs, "keyword", value, context, near)

    if vp and cfg.get("pattern_anywhere"):
        for i, row in enumerate(rows):
            vm = vp.search(row["text"])
            if vm:
                return _candidate(rows, [i], "pattern", vm.group(0), row["text"])

    if cfg.get("terms"):
        tr = _kw_regex(cfg["terms"])
        for i, row in enumerate(rows):
            # short lines only: ingredient lists ("Salt, Spices, Edible Oil…") mention commodity words too
            if tr.search(row["text"]) and not other_kw.search(row["text"]) and len(row["text"].split()) <= 6 \
                    and not COMPANY.search(row["text"]):
                return _candidate(rows, [i], "term", row["text"], row["text"])

    if cfg.get("fallback") == "pin_address":
        # "Manufactured by" cropped or unreadable: take the first address carrying a PIN code; officer confirms.
        for i, row in enumerate(rows):
            if PIN.search(row["text"]) and not NOT_ADDRESS.search(row["text"]) and not BARCODE_DIGITS.fullmatch(row["text"]):
                idxs = [i] + [j for j in _below_in_column(rows, i, look) if not other_kw.search(rows[j]["text"])]
                text = " ".join(rows[j]["text"] for j in idxs)
                return _candidate(rows, idxs, "fallback", text, text)

    if cfg.get("fallback") == "tallest_text":
        # ponytail: brand and generic name are usually the two biggest short text lines; officer confirms.
        cands = sorted(
            (i for i, r in enumerate(rows) if not re.search(r"\d", r["text"]) and not other_kw.search(r["text"])
             and len(r["text"].split()) <= 5),
            key=lambda i: -rows[i]["height"],
        )[:2]
        if cands:
            cands.sort()
            text = " / ".join(rows[i]["text"] for i in cands)
            return _candidate(rows, cands, "fallback", text, text)
    return None


def extract_fields(lines, rules):
    """lines: OCR output lines. Returns (rows, {field_id: candidate | None})."""
    rows = group_rows(lines)
    out = {}
    for f in rules["fields"]:
        others = [k for g in rules["fields"] if g is not f for k in g["extract"]["keywords"]] + rules.get("stop_keywords", [])
        out[f["id"]] = extract_field(f, rows, _kw_regex(others))
    return rows, out
