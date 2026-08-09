import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import auth as auth_module
from ..db import get_db
from ..models import AuditLog, Citation, LineItem, Quarantine, Statement, User
from ..schemas import DashboardMetrics, ExecutiveDashboard, StatementListItem
from .statements import VISIBLE_CLASSIFICATIONS

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

STALE_AFTER_DAYS = 30


@router.get("", response_model=DashboardMetrics)
def get_dashboard(db: Session = Depends(get_db), user: User = Depends(auth_module.get_current_user)):
    allowed = VISIBLE_CLASSIFICATIONS[user.role]
    base_q = db.query(Statement).filter(
        Statement.is_deleted.is_(False), Statement.classification.in_(allowed)
    )

    total_statements = base_q.count()
    avg_quality = base_q.filter(Statement.quality_score.isnot(None)).with_entities(
        func.avg(Statement.quality_score)
    ).scalar()
    avg_completeness = base_q.filter(Statement.completeness_score.isnot(None)).with_entities(
        func.avg(Statement.completeness_score)
    ).scalar()

    quarantine_pending = (
        db.query(Quarantine)
        .join(Statement, Statement.id == Quarantine.statement_id)
        .filter(Quarantine.status == "pending", Statement.classification.in_(allowed))
        .count()
    )

    stale_cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=STALE_AFTER_DAYS)
    stale_count = base_q.filter(Statement.last_updated < stale_cutoff).count()

    last_audit = db.query(func.max(AuditLog.timestamp)).scalar()

    recent = base_q.order_by(Statement.uploaded_at.desc()).limit(10).all()
    trend_source = base_q.filter(Statement.quality_score.isnot(None)).order_by(
        Statement.uploaded_at.asc()
    ).all()
    trend = [
        {"label": s.filename, "score": s.quality_score, "uploaded_at": s.uploaded_at.isoformat()}
        for s in trend_source[-20:]
    ]

    return DashboardMetrics(
        total_statements=total_statements,
        avg_quality_score=round(avg_quality, 1) if avg_quality is not None else None,
        avg_completeness_pct=round(avg_completeness, 1) if avg_completeness is not None else None,
        quarantine_pending_count=quarantine_pending,
        stale_record_count=stale_count,
        last_audit_at=last_audit,
        quality_trend=trend,
        recent_statements=[StatementListItem.model_validate(s) for s in recent],
    )


@router.get("/executive", response_model=ExecutiveDashboard)
def get_executive_dashboard(
    db: Session = Depends(get_db), user: User = Depends(auth_module.require_role("steward"))
):
    allowed = VISIBLE_CLASSIFICATIONS[user.role]
    base_q = db.query(Statement).filter(
        Statement.is_deleted.is_(False), Statement.classification.in_(allowed)
    )

    total_statements = base_q.count()
    status_counts = {
        row[0]: row[1]
        for row in base_q.with_entities(Statement.status, func.count(Statement.id)).group_by(Statement.status)
    }

    avg_quality = base_q.filter(Statement.quality_score.isnot(None)).with_entities(
        func.avg(Statement.quality_score)
    ).scalar()

    # Citation verification rate: the clearest available proxy for "is the AI's
    # grounding holding up" - the fraction of ALL captured citations (across
    # every line item on every visible statement) that the API actually
    # verified against the source document, vs. self-reported-only.
    citation_counts = (
        db.query(Citation)
        .join(LineItem, LineItem.id == Citation.line_item_id)
        .join(Statement, Statement.id == LineItem.statement_id)
        .filter(Statement.is_deleted.is_(False), Statement.classification.in_(allowed))
        .with_entities(Citation.verified, func.count(Citation.id))
        .group_by(Citation.verified)
        .all()
    )
    verified_count = sum(c for verified, c in citation_counts if verified)
    total_citations = sum(c for _, c in citation_counts)
    citation_verification_rate = (
        round(100.0 * verified_count / total_citations, 1) if total_citations else None
    )

    all_quarantine = (
        db.query(Quarantine)
        .join(Statement, Statement.id == Quarantine.statement_id)
        .filter(Statement.classification.in_(allowed))
    )
    total_quarantine_ever = all_quarantine.count()
    resolved_quarantine = all_quarantine.filter(Quarantine.status == "resolved").count()
    quarantine_resolution_rate = (
        round(100.0 * resolved_quarantine / total_quarantine_ever, 1) if total_quarantine_ever else None
    )

    assurance_breakdown = {
        (row[0] or "unknown"): row[1]
        for row in base_q.with_entities(Statement.assurance_level, func.count(Statement.id))
        .group_by(Statement.assurance_level)
    }
    period_type_breakdown = {
        (row[0] or "unknown"): row[1]
        for row in base_q.with_entities(Statement.period_type, func.count(Statement.id))
        .group_by(Statement.period_type)
    }

    trend_source = (
        base_q.filter(Statement.quality_score.isnot(None))
        .order_by(Statement.uploaded_at.asc())
        .all()
    )
    quality_trend = [
        {
            "label": s.filename,
            "quality_score": s.quality_score,
            "citation_coverage_score": s.citation_coverage_score,
            "uploaded_at": s.uploaded_at.isoformat(),
        }
        for s in trend_source[-30:]
    ]

    return ExecutiveDashboard(
        total_statements=total_statements,
        processing_count=status_counts.get("processing", 0),
        processed_count=status_counts.get("processed", 0),
        quarantined_count=status_counts.get("quarantined", 0),
        error_count=status_counts.get("error", 0),
        avg_quality_score=round(avg_quality, 1) if avg_quality is not None else None,
        citation_verification_rate=citation_verification_rate,
        total_citations_captured=total_citations,
        quarantine_resolution_rate=quarantine_resolution_rate,
        total_quarantine_items=total_quarantine_ever,
        assurance_level_breakdown=assurance_breakdown,
        period_type_breakdown=period_type_breakdown,
        quality_trend=quality_trend,
    )
