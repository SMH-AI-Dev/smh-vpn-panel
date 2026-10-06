"""Shared FastAPI dependencies and helpers."""

from __future__ import annotations

from fastapi import Request


def get_db(request: Request):
    factory = request.app.state.session_factory
    db = factory()
    try:
        yield db
    finally:
        db.close()


def audit(session, actor: str, action: str, detail: str = "") -> None:
    from ..models import AuditLog

    session.add(AuditLog(actor=actor, action=action, detail=detail))
