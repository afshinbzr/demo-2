from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import auth as auth_module
from ..audit import log_action
from ..db import get_db
from ..models import User
from ..schemas import LoginRequest, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/demo_users")
def list_demo_users(db: Session = Depends(get_db)):
    """Public endpoint powering the login page's role picker.

    `upload_password_required` lets the UI show the shared-password step only
    when one is actually enforced, instead of prompting for a password the
    backend would accept anything for."""
    users = db.query(User).order_by(User.role.desc()).all()
    return {
        "users": [{"username": u.username, "role": u.role} for u in users],
        "upload_password_required": auth_module.upload_password_configured(),
    }


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Unknown demo user")

    if not auth_module.check_upload_role_password(user.role, payload.password):
        raise HTTPException(status_code=403, detail="Incorrect password for this role")

    token = auth_module.create_session(user)
    auth_module.set_session_cookie(response, token)
    log_action(db, entity_type="user", entity_id=user.id, action="login", user=user)
    return user


@router.post("/logout")
def logout(response: Response, user: User = Depends(auth_module.get_current_user), db: Session = Depends(get_db)):
    auth_module.clear_session_cookie(response)
    log_action(db, entity_type="user", entity_id=user.id, action="logout", user=user)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(auth_module.get_current_user)):
    return user
