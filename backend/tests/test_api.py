"""API smoke test against a real Postgres test DB (legalmetro_test); OCR is replaced by a recorded fixture."""
import json
import os
import secrets
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

TEST_DB = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg:///legalmetro_test")
os.environ["DATABASE_URL"] = TEST_DB
os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))

try:
    with create_engine(TEST_DB).begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
except Exception as e:  # pragma: no cover
    pytest.skip(f"test database unavailable: {e}", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

import app.pipeline as pipeline  # noqa: E402
from app.cli import create_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models import engine  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
SAMPLE = Path(__file__).parent / "samples" / "noncompliant.jpg"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import app.main as m
    m.UPLOAD_DIR = tmp_path_factory.mktemp("uploads")
    pipeline.run_ocr = lambda data, name: json.loads((FIX / "noncompliant.ocr.json").read_text())
    pipeline.run_barcode = lambda data: {"barcodes": [{"data": "8901234100028", "type": "EAN_13", "box": [0, 0, 10, 10]}]}
    create_user("off@test.in", "pw-officer", "officer", "Officer T")
    create_user("biz@test.in", "pw-biz", "business", "Biz One")
    create_user("biz2@test.in", "pw-biz2", "business", "Biz Two")
    with TestClient(app) as c:
        yield c


def login(c, email, pw):
    r = c.post("/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_full_flow(client):
    c = client
    assert c.post("/auth/login", json={"email": "biz@test.in", "password": "nope"}).status_code == 401
    assert c.get("/scans").status_code == 401
    biz, biz2, off = login(c, "biz@test.in", "pw-biz"), login(c, "biz2@test.in", "pw-biz2"), login(c, "off@test.in", "pw-officer")

    r = c.post("/scans", headers=biz, files={"file": ("l.jpg", SAMPLE.read_bytes(), "image/jpeg")})
    assert r.status_code == 200, r.text
    scan = r.json()
    assert scan["effective"]["status"] == "non_compliant"
    sid = scan["id"]

    # Ownership: other business user can't see it; officer can.
    assert c.get(f"/scans/{sid}", headers=biz2).status_code == 404
    assert c.get("/scans", headers=biz2).json()["total"] == 0
    assert c.get("/scans?q=cruncho", headers=off).json()["total"] == 1

    # Only officers review.
    body = {"overrides": {"packing_date": {"status": "pass", "value": "07/2026", "note": "printed on crimp"}}}
    assert c.post(f"/scans/{sid}/reviews", headers=biz, json=body).status_code == 403
    r = c.post(f"/scans/{sid}/reviews", headers=off, json=body)
    assert r.status_code == 200, r.text
    f = {x["id"]: x for x in r.json()["effective"]["fields"]}
    assert f["packing_date"]["status"] == "pass" and f["packing_date"]["reviewed"]["machine_status"] == "missing"
    assert r.json()["machine_result"]["status"] == "non_compliant"  # original kept
    assert [a["action"] for a in r.json()["audit"]] == ["scan_created", "scan_reviewed"]

    # Override everything to pass -> filter by effective status.
    all_pass = {"overrides": {k: {"status": "pass"} for k in f}}
    c.post(f"/scans/{sid}/reviews", headers=off, json=all_pass)
    assert c.get("/scans?status=compliant", headers=off).json()["total"] == 1
    assert c.get("/scans?status=non_compliant", headers=off).json()["total"] == 0

    pdf = c.get(f"/scans/{sid}/report.pdf", headers=biz)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_barcode_upload_and_stats(client):
    c = client
    off = login(c, "off@test.in", "pw-officer")
    img = ("l.jpg", SAMPLE.read_bytes(), "image/jpeg")
    r = c.post("/scans", headers=off, files={"file": img, "barcode": ("b.png", b"\x89PNG", "image/png")})
    assert r.status_code == 200, r.text
    bc = r.json()["machine_result"]["barcode"]
    assert bc["code"] == "8901234100028" and bc["source"] == "barcode_photo" and bc["registry"]["mrp"] == 199.0
    assert r.json()["has_barcode_image"]
    assert c.get(f"/scans/{r.json()['id']}/barcode-image", headers=off).status_code == 200

    assert c.post("/scans/text", headers=off, json={"text": "x"}).status_code in (404, 405)  # e-commerce audit removed

    st = c.get("/stats", headers=off).json()
    assert st["total"] == 2
    assert st["barcodes"]["scanned"] == 1 and sum(st["by_status"].values()) == 2
    assert c.get("/stats", headers=login(c, "biz2@test.in", "pw-biz2")).json()["total"] == 0  # scoped to own scans


def test_scan_history_is_append_only(client):
    with pytest.raises(Exception, match="append-only"):
        with engine.begin() as c:
            c.execute(text("UPDATE scans SET status = 'compliant'"))
    with pytest.raises(Exception, match="append-only"):
        with engine.begin() as c:
            c.execute(text("DELETE FROM audit_log"))
