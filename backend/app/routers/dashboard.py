import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import auth as auth_module
from ..db import get_db
from ..models import AuditLog, Quarantine, Statement, User
from ..schemas import DashboardMetrics, StatementListItem
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
