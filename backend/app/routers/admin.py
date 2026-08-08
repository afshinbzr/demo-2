from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth as auth_module
from ..db import get_db
from ..models import AuditLog, DataDictionaryEntry, User
from ..schemas import AuditLogOut, DataDictionaryOut, UserOut

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
    return q.order_by(AuditLog.timestamp.desc()).limit(min(limit, 1000)).all()
