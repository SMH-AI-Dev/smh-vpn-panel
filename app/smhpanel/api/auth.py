"""Authentication endpoints and session management."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from .. import __version__
from ..models import Admin
from ..schemas import ChangePasswordIn, LoginIn
from ..security import (
    SESSION_COOKIE,
    create_session_token,
    hash_password,
    verify_password,
)
from .deps import audit, get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str, config, max_age: int) -> None:
    secure = bool(config.get("panel.tls.enabled", True))
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


@router.post("/login")
def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    config = request.app.state.config
    limiter = request.app.state.rate_limiter
    client_ip = request.client.host if request.client else "unknown"

    if not limiter.allowed(client_ip):
        raise HTTPException(
            status_code=429, detail="too many failed attempts, try again later"
        )

    admin = db.query(Admin).filter(Admin.username == payload.username).first()
    if admin is None or not verify_password(payload.password, admin.password_hash):
        limiter.failure(client_ip)
        audit(db, payload.username or "unknown", "auth.login_failed", f"ip={client_ip}")
        db.commit()
        raise HTTPException(status_code=401, detail="invalid credentials")

    limiter.clear(client_ip)
    csrf = secrets.token_urlsafe(24)
    ttl_hours = int(config.get("security.session_ttl_hours", 24))
    token = create_session_token(
        config.secret(), admin.id, admin.username, csrf, ttl_hours
    )
    _set_session_cookie(response, token, config, ttl_hours * 3600)
    audit(db, admin.username, "auth.login", f"ip={client_ip}")
    db.commit()
    return {"ok": True, "username": admin.username, "csrf_token": csrf}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    config = request.app.state.config
    return {
        "username": request.state.admin.get("username"),
        "panel_title": config.get("panel.title", "SMH Panel"),
        "version": __version__,
        "dev_mode": config.is_dev(),
    }


@router.post("/change-password")
def change_password(
    payload: ChangePasswordIn, request: Request, db: Session = Depends(get_db)
):
    admin = db.get(Admin, int(request.state.admin["id"]))
    if admin is None:
        raise HTTPException(status_code=404, detail="admin not found")
    if not verify_password(payload.old_password, admin.password_hash):
        raise HTTPException(status_code=400, detail="current password is incorrect")
    admin.password_hash = hash_password(payload.new_password)
    audit(db, admin.username, "auth.password_changed")
    db.commit()
    return {"ok": True}
