"""Demo authentication: a role-picker login, not real credentials.

This is a deliberate simplification for the demo (documented in the plan) —
there is no password check. What IS real: every session maps to a concrete
user+role, every mutating action is tied to that user (spec 1.1 — no
anonymous writes), and RBAC is enforced server-side on every route.
"""

import hmac
import os
import secrets

from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from .db import get_db
from .models import User

ROLE_RANK = {"viewer": 0, "editor": 1, "steward": 2, "admin": 3}
COOKIE_NAME = "fs_session"

# Roles that can mutate data or trigger a (paid) Claude API call.
UPLOAD_ROLES = {"editor", "steward", "admin"}

# In-memory session store: token -> user_id. Fine for a single-process demo;
# would be Redis/DB-backed in production.
_SESSIONS: dict[str, int] = {}

DEMO_USERS = [
    ("admin", "admin"),
    ("dana_steward", "steward"),
    ("evan_editor", "editor"),
    ("vic_viewer", "viewer"),
]


def seed_demo_users(db: Session) -> None:
    for username, role in DEMO_USERS:
        existing = db.query(User).filter(User.username == username).first()
        if not existing:
            db.add(User(username=username, role=role))
    db.commit()


def check_upload_role_password(role: str, password: str | None) -> bool:
    """Viewer is always free to log into (view-only, costs nothing). Roles
    that can upload/edit - which can trigger a paid Claude API call - require
    a shared password via the UPLOAD_ROLE_PASSWORD env var. If that env var
    isn't set at all, the gate stays open (matches pre-existing local-dev
    behavior); main.py logs a startup warning so this isn't silently
    insecure once actually deployed."""
    if role not in UPLOAD_ROLES:
        return True
    expected = os.environ.get("UPLOAD_ROLE_PASSWORD")
    if not expected:
        return True
    return bool(password) and hmac.compare_digest(password, expected)


def create_session(user: User) -> str:
    token = secrets.token_urlsafe(24)
    _SESSIONS[token] = user.id
    return token


def get_current_user(
    fs_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not fs_session or fs_session not in _SESSIONS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    user_id = _SESSIONS[fs_session]
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid")
    return user


def require_role(min_role: str):
    min_rank = ROLE_RANK[min_role]

    def _check(user: User = Depends(get_current_user)) -> User:
        if ROLE_RANK.get(user.role, -1) < min_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role '{min_role}' or higher (you are '{user.role}')",
            )
        return user

    return _check


def set_session_cookie(response: Response, token: str) -> None:
    # SESSION_COOKIE_SECURE=true in production (served over HTTPS) - browsers
    # reject `Secure` cookies over plain http, so local dev needs it off.
    secure = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=60 * 60 * 8,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)
