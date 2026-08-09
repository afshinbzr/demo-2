from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth as auth_module
from ..audit import log_action
from ..db import get_db
from ..models import LineItem, Quarantine, Statement, User
from ..schemas import QuarantineOut, QuarantineResolve
from ..versioning import correct_line_item
from .statements import VISIBLE_CLASSIFICATIONS, _assert_visible, recompute_statement

router = APIRouter(prefix="/api/quarantine", tags=["quarantine"])


@router.get("", response_model=list[QuarantineOut])
def list_quarantine(
    status_filter: str = "pending",
    db: Session = Depends(get_db),
    user: User = Depends(auth_module.require_role("steward")),
):
    allowed = VISIBLE_CLASSIFICATIONS[user.role]
    q = (
        db.query(Quarantine)
        .join(Statement, Statement.id == Quarantine.statement_id)
        .filter(Statement.classification.in_(allowed))
    )
    if status_filter != "all":
        q = q.filter(Quarantine.status == status_filter)
    return q.order_by(Quarantine.created_at.desc()).all()


@router.post("/{quarantine_id}/resolve")
def resolve_quarantine(
    quarantine_id: int,
    payload: QuarantineResolve,
    db: Session = Depends(get_db),
    user: User = Depends(auth_module.require_role("steward")),
):
    item = db.get(Quarantine, quarantine_id)
    if not item:
        raise HTTPException(status_code=404, detail="Quarantine item not found")

    # Clearance is checked before the status/payload branches below, so this
    # endpoint can't be used to probe which quarantine ids exist on statements
    # the caller isn't cleared to see (the list sibling already filters them).
    statement = db.get(Statement, item.statement_id)
    if not statement or statement.is_deleted:
        raise HTTPException(status_code=404, detail="Quarantine item not found")
    _assert_visible(statement, user)

    if item.status != "pending":
        raise HTTPException(status_code=400, detail="Already reviewed")
    if payload.resolution not in {"approved", "corrected", "rejected"}:
        raise HTTPException(status_code=400, detail="resolution must be approved|corrected|rejected")

    if payload.resolution == "corrected":
        if not item.line_item_id or payload.corrected_value is None:
            raise HTTPException(status_code=400, detail="corrected resolution requires line_item_id and corrected_value")
        line_item = db.get(LineItem, item.line_item_id)
        if not line_item:
            raise HTTPException(status_code=404, detail="Line item not found")
        correct_line_item(
            db, line_item, new_value=payload.corrected_value, user=user,
            source=f"quarantine review #{item.id}",
        )

    item.status = "resolved"
    item.reviewed_by_id = user.id
    # Only append the note when there is one, otherwise the stored value ends
    # in a stray colon that renders as "Resolved: approved:" in the UI.
    note = (payload.note or "").strip()
    item.resolution_note = f"{payload.resolution}: {note}" if note else payload.resolution
    from datetime import datetime, timezone
    item.reviewed_at = datetime.now(timezone.utc)
    db.commit()

    log_action(
        db, entity_type="quarantine", entity_id=item.id, action="update", user=user,
        detail=f"Resolved as '{payload.resolution}' for statement #{statement.id}",
    )

    recompute_statement(db, statement, record_quarantine=False)

    remaining_pending = (
        db.query(Quarantine)
        .filter(Quarantine.statement_id == statement.id, Quarantine.status == "pending")
        .count()
    )
    statement.status = "quarantined" if remaining_pending else "processed"
    db.commit()

    return {"ok": True}
