import json
from typing import Any

from sqlalchemy.orm import Session

from .models import AuditLog, User


def log_action(
    db: Session,
    *,
    entity_type: str,
    entity_id: int | None,
    action: str,
    user: User | None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    detail: str | None = None,
) -> None:
    """Write one audit_log row. Called for every create and update (including
    the AI extraction run), and whenever a Confidential/Restricted record's
    detail page is opened (spec 1.2, 1.4). List and dashboard reads are not
    logged - they re-fetch on every navigation and would flood the table."""
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=user.id if user else None,
        username=user.username if user else None,
        old_value=json.dumps(old_value, default=str) if old_value is not None else None,
        new_value=json.dumps(new_value, default=str) if new_value is not None else None,
        detail=detail,
    )
    db.add(entry)
    db.commit()
