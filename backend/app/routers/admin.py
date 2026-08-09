from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth as auth_module
from ..db import get_db
from ..models import AuditLog, DataDictionaryEntry, Statement, User
from ..schemas import AuditLogOut, DataDictionaryOut, UserOut
from .statements import VISIBLE_CLASSIFICATIONS

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), user: User = Depends(auth_module.require_role("admin"))):
    return db.query(User).order_by(User.role.desc()).all()


@router.get("/data_dictionary", response_model=list[DataDictionaryOut])
def data_dictionary(db: Session = Depends(get_db), user: User = Depends(auth_module.get_current_user)):
    return db.query(DataDictionaryEntry).order_by(DataDictionaryEntry.field_name).all()


@router.get("/audit_log", response_model=list[AuditLogOut])
def audit_log(
    entity_type: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    user: User = Depends(auth_module.require_role("steward")),
):
    q = db.query(AuditLog)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)

    # The audit log's `detail` text quotes filenames and values from the record
    # it describes, so statement rows have to respect the same classification
    # clearance the statements router enforces - otherwise the audit view
    # becomes a side channel onto Restricted statements.
    allowed = VISIBLE_CLASSIFICATIONS[user.role]
    visible_statement_ids = {
        row[0]
        for row in db.query(Statement.id).filter(Statement.classification.in_(allowed)).all()
    }
    rows = q.order_by(AuditLog.timestamp.desc()).limit(min(limit, 1000)).all()
    return [
        r for r in rows
        if r.entity_type != "statement" or r.entity_id in visible_statement_ids
    ]
