"""PostgreSQL models. scans, reviews and audit_log are append-only (enforced by DB triggers)."""
import os
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

engine = create_engine(os.getenv("DATABASE_URL", "postgresql+psycopg:///legalmetro"))
Session = sessionmaker(engine, expire_on_commit=False)


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('officer', 'business')"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Scan(Base):
    __tablename__ = "scans"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[str] = mapped_column(String(20), default="packaging")  # packaging (older records may be 'ecommerce' from a removed feature)
    image_path: Mapped[str | None] = mapped_column(String(255))  # None only on legacy e-commerce text records
    barcode_image_path: Mapped[str | None] = mapped_column(String(255))
    listing: Mapped[dict | None] = mapped_column(JSONB)  # legacy e-commerce records: {url, platform}
    image_sha256: Mapped[str | None] = mapped_column(String(64))
    ocr: Mapped[dict] = mapped_column(JSONB)  # raw PaddleOCR output: lines, confidences, boxes
    result: Mapped[dict] = mapped_column(JSONB)  # rule-engine output at scan time
    status: Mapped[str] = mapped_column(String(20), index=True)
    rules_version: Mapped[str] = mapped_column(String(50))
    search_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class Review(Base):
    """Officer confirmation/override of a scan. Never edits the scan; the latest review wins."""
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    overrides: Mapped[dict] = mapped_column(JSONB)  # {field_id: {status, value?, note?}}
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20))  # overall status after this review
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(50))
    scan_id: Mapped[int | None] = mapped_column(ForeignKey("scans.id"), index=True)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# Columns added after the first release; create_all() doesn't alter existing tables.
UPGRADE_SQL = """
ALTER TABLE scans ADD COLUMN IF NOT EXISTS source varchar(20) NOT NULL DEFAULT 'packaging';
ALTER TABLE scans ADD COLUMN IF NOT EXISTS barcode_image_path varchar(255);
ALTER TABLE scans ADD COLUMN IF NOT EXISTS listing jsonb;
ALTER TABLE scans ALTER COLUMN image_path DROP NOT NULL;
ALTER TABLE scans ALTER COLUMN image_sha256 DROP NOT NULL;
"""

APPEND_ONLY_SQL = """
CREATE OR REPLACE FUNCTION forbid_change() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION '% is append-only: % not allowed', TG_TABLE_NAME, TG_OP; END;
$$ LANGUAGE plpgsql;
""" + "".join(
    f"""
DROP TRIGGER IF EXISTS {t}_append_only ON {t};
CREATE TRIGGER {t}_append_only BEFORE UPDATE OR DELETE ON {t} FOR EACH ROW EXECUTE FUNCTION forbid_change();
DROP TRIGGER IF EXISTS {t}_no_truncate ON {t};
CREATE TRIGGER {t}_no_truncate BEFORE TRUNCATE ON {t} FOR EACH STATEMENT EXECUTE FUNCTION forbid_change();
"""
    for t in ("scans", "reviews", "audit_log")
)


def init_db():
    # ponytail: create_all + idempotent triggers; switch to Alembic at the first schema change on real data.
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text(UPGRADE_SQL))
        c.execute(text(APPEND_ONLY_SQL))


def audit(db, action, actor_id=None, scan_id=None, **detail):
    db.add(AuditLog(action=action, actor_id=actor_id, scan_id=scan_id, detail=detail))
