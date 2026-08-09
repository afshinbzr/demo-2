import datetime
import json

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[str] = mapped_column(String(16))  # admin | steward | editor | viewer
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)


class Statement(Base):
    __tablename__ = "statements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    statement_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fiscal_period: Mapped[str | None] = mapped_column(String(32), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    classification: Mapped[str] = mapped_column(String(16), default="Internal")
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    steward_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    uploaded_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)
    last_updated: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    status: Mapped[str] = mapped_column(String(16), default="processing")
    # processing | processed | quarantined | error

    ai_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_extraction_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Period coverage
    period_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # single_period | multi_year | unknown
    periods_covered: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # comma-joined, most-recent first, e.g. "FY2026, FY2025"

    # Format/language/unit consistency observations (spec: inconsistent formats,
    # mixed EN/FR terminology, inconsistent unit scale within one document)
    language_detected: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # english | french | bilingual_en_fr | other | unknown
    structure_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_scale_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_scale_uncertain: Mapped[bool] = mapped_column(Boolean, default=False)

    # Assurance/engagement level (Canadian CPA standards). The human-readable
    # descriptions live in frontend/src/assuranceStandards.ts (display-only).
    assurance_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # compilation | review | audit | none | unknown
    assurance_standard: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assurance_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    assurance_quote_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assurance_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # True: the assurance quote was API-matched against the actual source text.

    summary_sections_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON-encoded dict of lender-oriented narrative sections (profitability,
    # liquidity, leverage, cash flow, red flags, overall assessment) - kept
    # structured rather than one prose blob so the UI can render it scannable.
    ratios_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON-encoded list of computed credit-analysis ratios (see ratios.py).

    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    completeness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    validity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    uniqueness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    citation_coverage_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    line_items: Mapped[list["LineItem"]] = relationship(
        back_populates="statement", cascade="all, delete-orphan"
    )

    @property
    def ratios(self) -> list[dict]:
        """Parsed view of ratios_json for the API layer (Pydantic reads this
        like any other attribute via from_attributes)."""
        if not self.ratios_json:
            return []
        return json.loads(self.ratios_json)

    @property
    def summary_sections(self) -> dict:
        """Parsed view of summary_sections_json for the API layer."""
        if not self.summary_sections_json:
            return {}
        return json.loads(self.summary_sections_json)


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("statements.id"))

    field_name: Mapped[str] = mapped_column(String(64))
    raw_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    period: Mapped[str | None] = mapped_column(String(32), nullable=True)

    confidence: Mapped[str] = mapped_column(String(16), default="high")  # high | medium | low
    is_outlier: Mapped[bool] = mapped_column(Boolean, default=False)

    last_updated: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    statement: Mapped["Statement"] = relationship(back_populates="line_items")
    citations: Mapped[list["Citation"]] = relationship(
        back_populates="line_item", cascade="all, delete-orphan"
    )


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    line_item_id: Mapped[int] = mapped_column(ForeignKey("line_items.id"))
    cited_text: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)
    # True: API-matched this quote against the actual source PDF text.
    # False: the model's self-reported quote, not confirmed by citation matching.

    line_item: Mapped["LineItem"] = relationship(back_populates="citations")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(32))  # create|update|delete|view_sensitive|login
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class Quarantine(Base):
    __tablename__ = "quarantine"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("statements.id"))
    line_item_id: Mapped[int | None] = mapped_column(ForeignKey("line_items.id"), nullable=True)
    reason_code: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|reviewed|resolved
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class DataDictionaryEntry(Base):
    __tablename__ = "data_dictionary"

    field_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(16))
    description: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64))
    owner: Mapped[str] = mapped_column(String(64))
