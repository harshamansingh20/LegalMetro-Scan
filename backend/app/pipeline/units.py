"""Parse money and quantities out of label text: 'Rs. 1,299.00' -> 1299.0, '1 L' -> (1000.0, 'ml')."""
import re

# Everything converts to grams, millilitres or a count.
UNITS = {
    "mg": (0.001, "g"), "g": (1, "g"), "gm": (1, "g"), "gms": (1, "g"), "gram": (1, "g"), "grams": (1, "g"),
    "kg": (1000, "g"), "kgs": (1000, "g"),
    "ml": (1, "ml"), "cl": (10, "ml"), "l": (1000, "ml"), "lt": (1000, "ml"), "ltr": (1000, "ml"), "ltrs": (1000, "ml"),
    "litre": (1000, "ml"), "litres": (1000, "ml"), "liter": (1000, "ml"), "liters": (1000, "ml"),
    "n": (1, "count"), "pc": (1, "count"), "pcs": (1, "count"), "piece": (1, "count"), "unit": (1, "count"), "units": (1, "count"),
}
# "53,00" (comma decimal, common OCR misread) is tried before "1,299.00" (thousands separator).
_NUM = r"(\d+,\d{1,2}(?!\d)|\d+(?:,\d{3})*(?:\.\d+)?)"


def _num(s):
    return float(s.replace(",", ".") if re.fullmatch(r"\d+,\d{1,2}", s) else s.replace(",", ""))


def money(text: str) -> float | None:
    m = re.search(_NUM, text or "")
    return _num(m.group(1)) if m else None


def quantity(text: str):
    """-> (amount in base unit, base unit) or None."""
    m = re.search(_NUM + r"\s*([a-z]+)", (text or "").lower())
    if not m or m.group(2) not in UNITS:
        return None
    factor, base = UNITS[m.group(2)]
    return _num(m.group(1)) * factor, base


def unit_price(text: str):
    """'Rs. 21.00 per 100 ml' -> (price per base unit, base unit) or None."""
    m = re.search(_NUM + r"\s*(?:/|per)\s*(\d+(?:\.\d+)?)?\s*([a-z]+)", (text or "").lower())
    if not m or m.group(3) not in UNITS:
        return None
    factor, base = UNITS[m.group(3)]
    per = float(m.group(2) or 1) * factor
    return _num(m.group(1)) / per, base


if __name__ == "__main__":
    assert money("Rs. 1,299.00") == 1299.0 and money("53,00") == 53.0
    assert quantity("1 L") == (1000.0, "ml") and quantity("500 g") == (500.0, "g") and quantity("2 kg") == (2000.0, "g")
    assert unit_price("Rs. 21.00 per 100 ml") == (0.21, "ml") and unit_price("Rs 90/kg") == (0.09, "g")
    print("ok")
