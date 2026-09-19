"""Render synthetic product-label photos for OCR/pipeline testing.

Run with any Python that has Pillow:  python tests/make_sample_labels.py
Writes tests/samples/*.jpg. Adds rotation, blur and noise so it isn't a clean scan.
"""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
OUT = Path(__file__).parent / "samples"

# EAN-13 encoding tables (GS1 General Specifications).
_L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
_R = ["".join("1" if b == "0" else "0" for b in c) for c in _L]
_G = [c[::-1] for c in _R]
_PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]


def ean13(first12):
    """Append the GS1 check digit."""
    s = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(first12))
    return first12 + str((10 - s % 10) % 10)


def draw_ean13(code, module=3, height=110):
    d = [int(c) for c in code]
    bits = "101" + "".join((_L if p == "L" else _G)[x] for p, x in zip(_PARITY[d[0]], d[1:7])) + "01010"
    bits += "".join(_R[x] for x in d[7:]) + "101"
    img = Image.new("RGB", ((len(bits) + 22) * module, height + 34), "white")
    dr = ImageDraw.Draw(img)
    for i, b in enumerate(bits):
        if b == "1":
            x = (i + 11) * module
            dr.rectangle([x, 8, x + module - 1, 8 + height], fill="black")
    dr.text((11 * module, height + 10), code, font=ImageFont.truetype(FONT, 20), fill="black")
    return img


# Demo GTINs (890 = GS1 India prefix). They match backend/app/products.json, a demo registry.
BARCODES = {
    "compliant": ean13("890123410001"),
    "mustard_oil": ean13("890123410002"),
    "face_wash": ean13("890123410003"),
}

LABELS = {
    # Every mandatory declaration present and well-formed.
    "compliant": [
        (BOLD, 64, "GOLDEN HARVEST"),
        (BOLD, 40, "Basmati Rice"),
        (FONT, 30, "Net Quantity: 1 kg"),
        (FONT, 26, "MRP Rs. 145.00 (Incl. of all taxes)"),
        (FONT, 24, "Unit Sale Price: Rs. 0.145 per g"),
        (FONT, 24, "Mfd. & Packed by: Golden Harvest Foods Pvt. Ltd."),
        (FONT, 22, "Plot 12, MIDC Industrial Area, Pune - 411019"),
        (FONT, 24, "Month & Year of Packing: 08/2026"),
        (FONT, 22, "Consumer Care: 1800-123-4567"),
        (FONT, 22, "Email: care@goldenharvest.in"),
    ],
    # Missing consumer care + date, non-standard unit "gms", MRP without tax phrase.
    "noncompliant": [
        (BOLD, 64, "CRUNCHO"),
        (BOLD, 40, "Potato Chips"),
        (FONT, 18, "Net Wt. 52 gms"),
        (FONT, 28, "MRP: Rs. 20"),
        (FONT, 24, "Marketed by: Cruncho Snacks"),
        (FONT, 22, "Ingredients: Potato, Edible Oil, Salt"),
    ],
    # MRP without "inclusive of all taxes", packer address without PIN; registry MRP differs (Rs. 199).
    "mustard_oil": [
        (BOLD, 60, "SHREE GOLD"),
        (BOLD, 40, "Kachi Ghani Mustard Oil"),
        (FONT, 30, "Net Qty: 1 L"),
        (FONT, 28, "MRP Rs. 210.00"),
        (FONT, 24, "Unit Sale Price: Rs. 21.00 per 100 ml"),
        (FONT, 24, "Packed by: Shree Oil Mills, Jaipur, Rajasthan"),
        (FONT, 24, "Pkd. On: 05/2026"),
        (FONT, 22, "Customer Care: care@shreegold.in"),
    ],
    # Everything declared, but USP Rs. 2.49/ml doesn't match MRP 199 / 100 ml = Rs. 1.99/ml.
    "face_wash": [
        (BOLD, 60, "PURE LEAF"),
        (BOLD, 40, "Neem Face Wash"),
        (FONT, 30, "Net Qty: 100 ml"),
        (FONT, 26, "MRP Rs. 199.00 (Incl. of all taxes)"),
        (FONT, 24, "Unit Sale Price: Rs. 2.49 per ml"),
        (FONT, 24, "Mfd. by: Pure Leaf Herbals Pvt. Ltd."),
        (FONT, 22, "Sector 5, IMT Manesar, Gurugram 122050"),
        (FONT, 24, "Mfg. Date: 04/2026"),
        (FONT, 22, "Consumer Care: 1800-200-3344, care@pureleaf.in"),
    ],
}


# Two-column panel, rupee sign, small text, then perspective-warped and downscaled like a quick phone shot.
HARD = [
    ((40, 30), BOLD, 44, "SUNRISE"),
    ((40, 90), BOLD, 28, "Toned Milk Powder"),
    ((40, 150), FONT, 20, "Net Wt. 500 g"),
    ((520, 150), FONT, 20, "M.R.P. ₹ 265.00"),
    ((520, 178), FONT, 16, "(Inclusive of all taxes)"),
    ((40, 220), FONT, 16, "Mfd. by: Sunrise Dairy Co-op Ltd."),
    ((40, 244), FONT, 16, "NH-48, Anand, Gujarat 388001"),
    ((520, 220), FONT, 16, "Pkd. On: 03/2026"),
    ((520, 244), FONT, 16, "USP: ₹ 53.00 per 100 g"),
    ((40, 300), FONT, 15, "For feedback / complaints contact: Consumer Cell,"),
    ((40, 322), FONT, 15, "Tel: 079-26801234  e-mail: care@sunrisedairy.coop"),
]


def render_hard(seed=7):
    img = Image.new("RGB", (900, 380), (236, 242, 250))
    d = ImageDraw.Draw(img)
    for (x, y), font, size, text in HARD:
        d.text((x, y), text, font=ImageFont.truetype(font, size), fill=(20, 40, 90))
    w, h = img.size
    # Perspective: shrink the right edge, as if shot at an angle.
    img = img.transform((w, h), Image.QUAD, (0, 0, 0, h, w, h + 40, w, -40), fillcolor=(80, 80, 80))
    img = img.resize((w * 3 // 4, h * 3 // 4)).filter(ImageFilter.GaussianBlur(0.6))
    return img


def render(lines, seed, barcode=None):
    rnd = random.Random(seed)
    img = Image.new("RGB", (1000, 120 + 62 * len(lines) + (180 if barcode else 0)), (250, 244, 228))
    d = ImageDraw.Draw(img)
    y = 50
    for font, size, text in lines:
        d.text((60, y), text, font=ImageFont.truetype(font, size), fill=(30, 30, 30))
        y += size + 30
    if barcode:
        img.paste(draw_ean13(barcode), (60, y + 10))
    # Photo-ish: tilt, soften, sensor noise.
    img = img.rotate(rnd.uniform(-3, 3), expand=True, fillcolor=(90, 90, 90))
    img = img.filter(ImageFilter.GaussianBlur(0.8))
    px = img.load()
    for _ in range(img.width * img.height // 40):
        x, yy = rnd.randrange(img.width), rnd.randrange(img.height)
        n = rnd.randint(-40, 40)
        px[x, yy] = tuple(max(0, min(255, c + n)) for c in px[x, yy])
    return img


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for i, (name, lines) in enumerate(LABELS.items()):
        render(lines, i, BARCODES.get(name)).save(OUT / f"{name}.jpg", quality=85)
        print("wrote", OUT / f"{name}.jpg")
    render_hard().save(OUT / "hard.jpg", quality=70)
    print("wrote", OUT / "hard.jpg")
    # A close-up of just the barcode, as a user would upload it separately.
    draw_ean13(BARCODES["mustard_oil"], module=4).save(OUT / "mustard_oil_barcode.png")
    print("wrote", OUT / "mustard_oil_barcode.png", BARCODES)
