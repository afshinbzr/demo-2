import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session, selectinload

from .. import auth as auth_module
from ..audit import log_action
from ..db import SessionLocal, get_db
from ..extraction import extract_statement
from ..models import Citation, LineItem, Quarantine, Statement, User
from ..quality import run_quality_checks
from ..ratios import compute_ratios, ratios_to_dicts
from ..schemas import LineItemUpdate, StatementDetailOut, StatementListItem
from ..versioning import correct_line_item

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/statements", tags=["statements"])

# Classification levels a role may read, from spec 1.2/1.3 (least privilege).
VISIBLE_CLASSIFICATIONS = {
    "viewer": {"Public", "Internal"},
    "editor": {"Public", "Internal"},
    "steward": {"Public", "Internal", "Confidential"},
    "admin": {"Public", "Internal", "Confidential", "Restricted"},
}


def _visible_query(db: Session, user: User):
    allowed = VISIBLE_CLASSIFICATIONS[user.role]
    return (
        db.query(Statement)
        .filter(Statement.is_deleted.is_(False), Statement.classification.in_(allowed))
    )


def _assert_visible(statement: Statement, user: User) -> None:
    if statement.classification not in VISIBLE_CLASSIFICATIONS[user.role]:
        raise HTTPException(status_code=403, detail="Insufficient classification clearance")


def recompute_statement(db: Session, statement: Statement, record_quarantine: bool = False) -> None:
    """Re-run quality scoring and credit ratios from the statement's current
    active line items. Used after initial extraction and after any manual
    correction (value changes ripple into both scores and ratios)."""
    active_items = [li for li in statement.line_items if not li.is_deleted]
    scores = run_quality_checks(db, statement, active_items, record_quarantine=record_quarantine)
    statement.completeness_score = scores.completeness
    statement.validity_score = scores.validity
    statement.consistency_score = scores.consistency
    statement.uniqueness_score = scores.uniqueness
    statement.citation_coverage_score = scores.citation_coverage
    statement.quality_score = scores.composite
    statement.ratios_json = json.dumps(ratios_to_dicts(compute_ratios(active_items)))


@router.post("/upload")
def upload_statements(
    background_tasks: BackgroundTasks,
    files: list[UploadFile],
    classification: str = "Internal",
    db: Session = Depends(get_db),
    user: User = Depends(auth_module.require_role("editor")),
):
    if classification not in {"Public", "Internal", "Confidential", "Restricted"}:
        raise HTTPException(status_code=400, detail="Invalid classification")

    created_ids = []
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"'{f.filename}' is not a PDF")
        content = f.file.read()
        statement = Statement(
            filename=f.filename,
            classification=classification,
            owner_id=user.id,
            uploaded_by_id=user.id,
            status="processing",
        )
        db.add(statement)
        db.commit()
        db.refresh(statement)
        log_action(db, entity_type="statement", entity_id=statement.id, action="create", user=user,
                   detail=f"Uploaded '{f.filename}'")
        created_ids.append(statement.id)
        background_tasks.add_task(_process_statement, statement.id, content)

    return {"statement_ids": created_ids}


def _process_statement(statement_id: int, pdf_bytes: bytes) -> None:
    """Runs in a background task with its own DB session."""
    db = SessionLocal()
    try:
        statement = db.get(Statement, statement_id)
        if not statement:
            return
        try:
            result = extract_statement(pdf_bytes)
        except Exception as exc:  # noqa: BLE001 - surface any extraction failure to the record
            logger.exception("Extraction failed for statement %s", statement_id)
            statement.status = "error"
            statement.error_detail = str(exc)
            db.commit()
            return

        statement.company_name = result.company_name
        statement.statement_type = result.statement_type
        statement.fiscal_period = result.fiscal_period
        statement.currency = result.currency
        statement.ai_notes = result.notes
        statement.raw_extraction_text = result.raw_text
        statement.period_type = result.period_type
        statement.periods_covered = result.periods_covered
        statement.language_detected = result.language_detected
        statement.structure_note = result.structure_note
        statement.unit_scale_note = result.unit_scale_note
        statement.unit_scale_uncertain = result.unit_scale_uncertain
        statement.assurance_level = result.assurance_level
        statement.assurance_standard = result.assurance_standard
        statement.summary_sections_json = json.dumps(result.summary_sections)
        if result.assurance_citation:
            statement.assurance_quote = result.assurance_citation.cited_text
            statement.assurance_quote_page = result.assurance_citation.page_number
            statement.assurance_verified = result.assurance_citation.verified

        line_items = []
        for pf in result.fields:
            li = LineItem(
                statement_id=statement.id,
                field_name=pf.field_name,
                raw_label=pf.raw_label,
                value=pf.value,
                unit=pf.unit,
                period=pf.period,
            )
            db.add(li)
            db.flush()
            for c in pf.citations:
                db.add(Citation(
                    line_item_id=li.id, cited_text=c.cited_text,
                    page_number=c.page_number, verified=c.verified,
                ))
            line_items.append(li)
        db.commit()

        recompute_statement(db, statement, record_quarantine=True)

        db.flush()  # session has autoflush=False; quarantine rows added in run_quality_checks
        # must be flushed before the count below sees them.
        pending = db.query(Quarantine).filter(Quarantine.statement_id == statement.id).count()
        statement.status = "quarantined" if pending else "processed"
        db.commit()
    finally:
        db.close()


@router.get("", response_model=list[StatementListItem])
def list_statements(db: Session = Depends(get_db), user: User = Depends(auth_module.get_current_user)):
    return _visible_query(db, user).order_by(Statement.uploaded_at.desc()).all()


@router.get("/{statement_id}", response_model=StatementDetailOut)
def get_statement(statement_id: int, db: Session = Depends(get_db),
                   user: User = Depends(auth_module.get_current_user)):
    statement = (
        db.query(Statement)
        .options(selectinload(Statement.line_items).selectinload(LineItem.citations))
        .filter(Statement.id == statement_id, Statement.is_deleted.is_(False))
        .first()
    )
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")
    _assert_visible(statement, user)

    if statement.classification in {"Confidential", "Restricted"}:
        log_action(db, entity_type="statement", entity_id=statement.id, action="view_sensitive", user=user,
                   detail=f"Viewed {statement.classification} statement")

    statement.line_items = [li for li in statement.line_items if not li.is_deleted]
    return statement


@router.patch("/{statement_id}/line_items/{line_item_id}")
def correct_line_item_endpoint(
    statement_id: int,
    line_item_id: int,
    payload: LineItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(auth_module.require_role("editor")),
):
    item = db.get(LineItem, line_item_id)
    if not item or item.statement_id != statement_id or item.is_deleted:
        raise HTTPException(status_code=404, detail="Line item not found")

    new_item = correct_line_item(
        db, item,
        new_value=payload.value,
        new_raw_label=payload.raw_label,
        new_unit=payload.unit,
        new_period=payload.period,
        user=user,
        source="manual correction",
    )

    statement = db.get(Statement, statement_id)
    recompute_statement(db, statement, record_quarantine=False)
    db.commit()

    return {"ok": True, "new_line_item_id": new_item.id}
