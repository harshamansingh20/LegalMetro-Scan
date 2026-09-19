import hashlib
import os
import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from .auth import current_user, hash_password, make_token, officer, verify_password
from .models import AuditLog, Review, Scan, Session, User, audit, init_db
from .pipeline import analyze_image, load_rules
from .pipeline.ocr import OCRError
from .pipeline.report import apply_reviews, render_pdf

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", Path(__file__).parent.parent / "uploads"))
MAX_UPLOAD = 12 * 1024 * 1024
IMAGE_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
# Dummy hash so unknown-email logins take as long as wrong-password ones.
_DUMMY_HASH = hash_password(uuid.uuid4().hex)



@asynccontextmanager
async def lifespan(app):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


app = FastAPI(title="LegalMetro Scan API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o],
    allow_methods=["*"],
    allow_headers=["*"],
)


def user_out(u: User):
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role}


# ---------- auth ----------

class LoginIn(BaseModel):
    email: str
    password: str


@app.post("/auth/login")
def login(body: LoginIn):
    with Session() as db:
        u = db.scalar(select(User).where(User.email == body.email.strip().lower()))
        ok = verify_password(body.password, u.password_hash if u else _DUMMY_HASH) and u is not None
        audit(db, "login" if ok else "login_failed", actor_id=u.id if u else None, email=body.email.strip().lower())
        db.commit()
    if not ok:
        raise HTTPException(401, "Invalid email or password")
    return {"token": make_token(u), "user": user_out(u)}


@app.get("/auth/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


# ---------- scans ----------

def _load_scan(db, scan_id: int, user: User) -> Scan:
    s = db.get(Scan, scan_id)
    # Business users only ever see their own scans; 404 (not 403) so IDs can't be probed.
    if not s or (user.role != "officer" and s.user_id != user.id):
        raise HTTPException(404, "Scan not found")
    return s


def _reviews(db, scan_id):
    rows = db.execute(
        select(Review, User.name).join(User, User.id == Review.reviewer_id).where(Review.scan_id == scan_id).order_by(Review.id)
    ).all()
    return [
        {"id": r.id, "reviewer": name, "overrides": r.overrides, "note": r.note, "status": r.status, "created_at": r.created_at.isoformat()}
        for r, name in rows
    ]


def scan_detail(db, s: Scan, user: User):
    reviews = _reviews(db, s.id)
    owner = db.get(User, s.user_id)
    out = {
        "id": s.id,
        "created_at": s.created_at.isoformat(),
        "source": s.source,
        "listing": s.listing,
        "has_image": bool(s.image_path),
        "has_barcode_image": bool(s.barcode_image_path),
        "user": user_out(owner),
        "machine_result": s.result,
        "effective": apply_reviews(s.result, reviews),
        "reviews": reviews,
        "ocr": {"elapsed_ms": s.ocr.get("elapsed_ms"), "lines": s.ocr["lines"], "width": s.ocr.get("width"), "height": s.ocr.get("height")},
    }
    if user.role == "officer":
        out["audit"] = [
            {"action": a.action, "actor": name, "detail": a.detail, "created_at": a.created_at.isoformat()}
            for a, name in db.execute(
                select(AuditLog, User.name).outerjoin(User, User.id == AuditLog.actor_id).where(AuditLog.scan_id == s.id).order_by(AuditLog.id)
            )
        ]
    return out


def _read_image(f: UploadFile) -> tuple[bytes, str]:
    ext = IMAGE_EXT.get(f.content_type or "")
    if not ext:
        raise HTTPException(415, "Upload a JPEG, PNG or WebP image")
    data = f.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Image too large (max 12 MB)")
    return data, ext


def _save(data: bytes, ext: str) -> str:
    name = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / name).write_bytes(data)
    return name


def _store_scan(user, ocr, result, source, image=None, barcode=None, listing=None):
    commodity = next((f["value"] for f in result["fields"] if f["id"] == "commodity_name"), None)
    bc = (result.get("barcode") or {}).get("code") or ""
    with Session() as db:
        s = Scan(
            user_id=user.id, source=source, listing=listing,
            image_path=_save(*image) if image else None,
            image_sha256=hashlib.sha256(image[0]).hexdigest() if image else None,
            barcode_image_path=_save(*barcode) if barcode else None,
            ocr=ocr, result=result, status=result["status"], rules_version=result["rules_version"],
            search_text=" ".join([commodity or "", bc, (listing or {}).get("url") or ""] + [l["text"] for l in ocr["lines"]]),
        )
        db.add(s)
        db.flush()
        audit(db, "scan_created", actor_id=user.id, scan_id=s.id, source=source, status=result["status"], ocr_ms=ocr.get("elapsed_ms"))
        db.commit()
        return scan_detail(db, s, user)


@app.post("/scans")
def create_scan(
    file: UploadFile = File(...),
    barcode: UploadFile | None = File(None),
    user: User = Depends(current_user),
):
    """Label photo, plus an optional barcode close-up."""
    image = _read_image(file)
    bar = _read_image(barcode) if barcode and barcode.filename else None
    try:
        ocr, result = analyze_image(image[0], "label" + image[1], bar[0] if bar else None)
    except OCRError as e:
        raise HTTPException(503, str(e))
    return _store_scan(user, ocr, result, "packaging", image=image, barcode=bar)


def _effective_status():
    latest = select(Review.status).where(Review.scan_id == Scan.id).order_by(Review.id.desc()).limit(1).scalar_subquery()
    return func.coalesce(latest, Scan.status)


@app.get("/scans")
def list_scans(
    user: User = Depends(current_user),
    q: str | None = None,
    status: Literal["compliant", "needs_review", "non_compliant"] | None = None,
    reviewed: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    eff = _effective_status().label("effective_status")
    has_review = select(func.count(Review.id)).where(Review.scan_id == Scan.id).scalar_subquery()
    stmt = select(Scan, User.name, User.email, eff, has_review.label("n_reviews")).join(User, User.id == Scan.user_id)
    if user.role != "officer":
        stmt = stmt.where(Scan.user_id == user.id)
    if q:
        like = f"%{q}%"  # bound parameter, not string-built SQL
        stmt = stmt.where(or_(Scan.search_text.ilike(like), User.name.ilike(like), User.email.ilike(like)))
    if status:
        stmt = stmt.where(_effective_status() == status)
    if reviewed is not None:
        stmt = stmt.where(has_review > 0 if reviewed else has_review == 0)
    if date_from:
        stmt = stmt.where(Scan.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Scan.created_at < date_to + timedelta(days=1))
    with Session() as db:
        total = db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = db.execute(stmt.order_by(Scan.id.desc()).limit(limit).offset(offset)).all()
    items = []
    for s, name, email, st, n in rows:
        fields = {f["id"]: f for f in s.result["fields"]}
        items.append({
            "id": s.id, "created_at": s.created_at.isoformat(), "user": {"name": name, "email": email},
            "commodity": fields.get("commodity_name", {}).get("value"),
            "manufacturer": fields.get("manufacturer", {}).get("value"),
            "status": st, "machine_status": s.status, "reviewed": n > 0, "source": s.source,
            "score": s.result.get("score"), "barcode": (s.result.get("barcode") or {}).get("code"),
            "issues": sum(f["status"] != "pass" for f in s.result["fields"]),
        })
    return {"total": total, "items": items}


@app.get("/scans/{scan_id}")
def get_scan(scan_id: int, user: User = Depends(current_user)):
    with Session() as db:
        return scan_detail(db, _load_scan(db, scan_id, user), user)


@app.get("/scans/{scan_id}/image")
def get_image(scan_id: int, user: User = Depends(current_user)):
    with Session() as db:
        s = _load_scan(db, scan_id, user)
    if not s.image_path:
        raise HTTPException(404, "No image for this scan")
    return FileResponse(UPLOAD_DIR / s.image_path)


@app.get("/scans/{scan_id}/barcode-image")
def get_barcode_image(scan_id: int, user: User = Depends(current_user)):
    with Session() as db:
        s = _load_scan(db, scan_id, user)
    if not s.barcode_image_path:
        raise HTTPException(404, "No barcode photo for this scan")
    return FileResponse(UPLOAD_DIR / s.barcode_image_path)


class FieldOverride(BaseModel):
    status: Literal["pass", "fail", "missing", "review"]
    value: str | None = None
    note: str = ""


class ReviewIn(BaseModel):
    overrides: dict[str, FieldOverride]
    note: str = ""


@app.post("/scans/{scan_id}/reviews")
def add_review(scan_id: int, body: ReviewIn, user: User = Depends(officer)):
    valid = {f["id"] for f in load_rules()["fields"]}
    if bad := set(body.overrides) - valid:
        raise HTTPException(422, f"Unknown field(s): {sorted(bad)}")
    with Session() as db:
        s = _load_scan(db, scan_id, user)
        prior = _reviews(db, s.id)
        overrides = {k: v.model_dump() for k, v in body.overrides.items()}
        eff = apply_reviews(s.result, prior + [{"overrides": overrides, "reviewer": user.name, "created_at": ""}])
        db.add(Review(scan_id=s.id, reviewer_id=user.id, overrides=overrides, note=body.note, status=eff["status"]))
        audit(db, "scan_reviewed", actor_id=user.id, scan_id=s.id, fields=sorted(overrides), status=eff["status"])
        db.commit()
        return scan_detail(db, s, user)


@app.get("/scans/{scan_id}/report.pdf")
def report(scan_id: int, user: User = Depends(current_user)):
    with Session() as db:
        s = _load_scan(db, scan_id, user)
        detail = scan_detail(db, s, user)
        audit(db, "report_exported", actor_id=user.id, scan_id=s.id)
        db.commit()
    pdf = render_pdf(detail, str(UPLOAD_DIR / s.image_path) if s.image_path else None)
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="legalmetro-scan-{scan_id}.pdf"'})


@app.get("/stats")
def stats(user: User = Depends(current_user), days: int = Query(30, ge=1, le=365)):
    """Enforcement statistics over effective (officer-reviewed where applicable) results."""
    # ponytail: aggregates in Python over all visible scans; move to SQL / a rollup table past ~50k scans.
    with Session() as db:
        q = select(Scan).order_by(Scan.id)
        if user.role != "officer":
            q = q.where(Scan.user_id == user.id)
        scans = db.scalars(q).all()
        reviews = {}
        for r, name in db.execute(select(Review, User.name).join(User, User.id == Review.reviewer_id).order_by(Review.id)):
            reviews.setdefault(r.scan_id, []).append({"overrides": r.overrides, "reviewer": name, "created_at": r.created_at.isoformat()})
    rules = load_rules()
    by_field = {f["id"]: {"id": f["id"], "label": f["label"], "rule_ref": f.get("rule_ref"), "pass": 0, "fail": 0, "missing": 0, "review": 0} for f in rules["fields"]}
    status_n = {"compliant": 0, "needs_review": 0, "non_compliant": 0}
    since = date.today() - timedelta(days=days - 1)
    daily = {since + timedelta(days=i): {"compliant": 0, "needs_review": 0, "non_compliant": 0} for i in range(days)}
    makers, recent, exposure, bc_n, bc_mismatch = {}, [], 0, 0, 0
    for s in scans:
        eff = apply_reviews(s.result, reviews.get(s.id, []))
        status_n[eff["status"]] += 1
        exposure += eff["penalty"]["amount"]
        for f in eff["fields"]:
            if f["id"] in by_field:
                by_field[f["id"]][f["status"]] += 1
        d = s.created_at.astimezone().date()
        if d in daily:
            daily[d][eff["status"]] += 1
        if eff.get("barcode"):
            bc_n += 1
            bc_mismatch += bool(eff["barcode"]["mismatches"])
        fields = {f["id"]: f for f in eff["fields"]}
        maker = (fields.get("manufacturer", {}).get("value") or "Unknown").split(",")[0].strip()[:60]
        m = makers.setdefault(maker, {"name": maker, "scans": 0, "non_compliant": 0})
        m["scans"] += 1
        m["non_compliant"] += eff["status"] == "non_compliant"
        if eff["status"] == "non_compliant":
            recent.append({"id": s.id, "commodity": fields.get("commodity_name", {}).get("value"), "created_at": s.created_at.isoformat(),
                           "issues": [f["label"] for f in eff["fields"] if f["status"] in ("fail", "missing")]})
    total = len(scans)
    return {
        "total": total,
        "by_status": status_n,
        "compliance_rate": round(100 * status_n["compliant"] / total) if total else 0,
        "reviewed": len(reviews),
        "awaiting_review": sum(1 for s in scans if s.id not in reviews and s.status != "compliant"),
        "barcodes": {"scanned": bc_n, "registry_mismatches": bc_mismatch},
        "penalty_exposure": exposure,
        "penalty_section": rules.get("penalties", {}).get("section"),
        "by_field": list(by_field.values()),
        "daily": [{"date": d.isoformat(), **v} for d, v in daily.items()],
        "top_flagged": sorted((m for m in makers.values() if m["non_compliant"]), key=lambda m: (-m["non_compliant"], -m["scans"]))[:5],
        "recent_flagged": recent[::-1][:6],
    }


@app.get("/rules")
def rules(user: User = Depends(current_user)):
    return load_rules()


@app.get("/health")
def health():
    return {"ok": True}
