import datetime

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str | None = None


class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cited_text: str
    page_number: int | None = None
    verified: bool


class LineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    field_name: str
    raw_label: str | None = None
    value: float | None = None
    unit: str | None = None
    period: str | None = None
    confidence: str
    is_outlier: bool
    version: int
    last_updated: datetime.datetime
    citations: list[CitationOut] = []


class LineItemUpdate(BaseModel):
    value: float | None = None
    raw_label: str | None = None
    unit: str | None = None
    period: str | None = None


class StatementListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    company_name: str | None = None
    statement_type: str | None = None
    fiscal_period: str | None = None
    classification: str
    status: str
    quality_score: float | None = None
    uploaded_at: datetime.datetime
    last_updated: datetime.datetime


class RatioOut(BaseModel):
    key: str
    label: str
    category: str
    value: float | None = None
    unit: str
    formula: str
    flag: str | None = None
    note: str


class StatementDetailOut(StatementListItem):
    currency: str | None = None
    ai_notes: str | None = None
    error_detail: str | None = None
    completeness_score: float | None = None
    validity_score: float | None = None
    consistency_score: float | None = None
    uniqueness_score: float | None = None
    citation_coverage_score: float | None = None
    version: int
    owner_id: int | None = None
    steward_id: int | None = None
    uploaded_by_id: int | None = None
    line_items: list[LineItemOut] = []

    period_type: str | None = None
    periods_covered: str | None = None
    language_detected: str | None = None
    structure_note: str | None = None
    unit_scale_note: str | None = None
    unit_scale_uncertain: bool = False
    assurance_level: str | None = None
    assurance_standard: str | None = None
    assurance_quote: str | None = None
    assurance_quote_page: int | None = None
    assurance_verified: bool = False
    summary_sections: dict[str, str] = {}
    ratios: list[RatioOut] = []


class QuarantineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    statement_id: int
    line_item_id: int | None = None
    reason_code: str
    detail: str
    status: str
    created_at: datetime.datetime
    reviewed_by_id: int | None = None
    reviewed_at: datetime.datetime | None = None
    resolution_note: str | None = None


class QuarantineResolve(BaseModel):
    resolution: str  # approved | corrected | rejected
    note: str | None = None
    corrected_value: float | None = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    entity_type: str
    entity_id: int | None = None
    action: str
    username: str | None = None
    timestamp: datetime.datetime
    detail: str | None = None
    old_value: str | None = None
    new_value: str | None = None


class DataDictionaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    field_name: str
    type: str
    description: str
    source: str
    owner: str


class DashboardMetrics(BaseModel):
    total_statements: int
    avg_quality_score: float | None
    avg_completeness_pct: float | None
    quarantine_pending_count: int
    stale_record_count: int
    last_audit_at: datetime.datetime | None
    quality_trend: list[dict]
    recent_statements: list[StatementListItem]


class ExecutiveDashboard(BaseModel):
    total_statements: int
    processing_count: int
    processed_count: int
    quarantined_count: int
    error_count: int
    avg_quality_score: float | None
    citation_verification_rate: float | None
    total_citations_captured: int
    quarantine_resolution_rate: float | None
    total_quarantine_items: int
    assurance_level_breakdown: dict[str, int]
    period_type_breakdown: dict[str, int]
    quality_trend: list[dict]
