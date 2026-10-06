"""System endpoints: status, services, backup, logs, certs, traffic chart."""
from __future__ import annotations

import re
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..models import AuditLog, TrafficSample
from ..schemas import CertRequest
from ..services.backup import create_backup
from ..services.system import snapshot
from .deps import audit, get_db

router = APIRouter(prefix="/api/system", tags=["system"])

SERVICE_MAP = {"xray": "xray", "wg": "wg", "panel": "smhpanel"}
ACTIONS = {"start", "stop", "restart"}


@router.get("/status")
def status(request: Request):
    app = request.app
    return snapshot(
        app.state.config,
        app.state.runner,
        app.state.session_factory,
        app.state.manager,
    )


@router.post("/service/{name}/{action}")
def service_action(
    name: str, action: str, request: Request, db: Session = Depends(get_db)
):
    if name not in SERVICE_MAP or action not in ACTIONS:
        raise HTTPException(400, "invalid service or action")
    runner = request.app.state.runner
    actor = request.state.admin.get("username", "admin")
    code, out, err = runner.run("smhpanel-service", action, SERVICE_MAP[name])
    audit(db, actor, f"service.{action}", name)
    db.commit()
    if code != 0:
        raise HTTPException(500, (err or out or "helper failed").strip())
    return {"ok": True, "output": (out or "").strip()}


@router.get("/backup")
def backup(request: Request):
    data = create_backup(request.app.state.config)
    return Response(
        content=data,
        media_type="application/gzip",
        headers={
            "Content-Disposition": 'attachment; filename="smhpanel-backup.tar.gz"'
        },
    )


@router.get("/logs")
def logs(request: Request, limit: int = 200, db: Session = Depends(get_db)):
    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.id.desc())
        .limit(max(1, min(limit, 1000)))
        .all()
    )
    return [
        {
            "ts": row.ts.isoformat() if row.ts else None,
            "actor": row.actor,
            "action": row.action,
            "detail": row.detail,
        }
        for row in rows
    ]


@router.get("/certs")
def certs(request: Request):
    directory = Path(request.app.state.config.paths()["certs"])
    items = []
    if directory.exists():
        for entry in sorted(directory.iterdir()):
            if entry.suffix in (".crt", ".pem"):
                items.append({"name": entry.name, "size": entry.stat().st_size})
    return items


@router.post("/cert")
def issue_cert(payload: CertRequest, request: Request, db: Session = Depends(get_db)):
    domain = payload.domain.strip().lower()
    if ".." in domain or not re.fullmatch(r"[a-z0-9]([a-z0-9.-]*[a-z0-9])?", domain):
        raise HTTPException(400, "invalid domain")
    runner = request.app.state.runner
    actor = request.state.admin.get("username", "admin")
    code, out, err = runner.run("smhpanel-cert-issue", domain)
    audit(db, actor, "cert.issue", domain)
    db.commit()
    if code != 0:
        raise HTTPException(500, (err or out or "certificate issuance failed").strip())
    return {"ok": True, "output": (out or "").strip()}


@router.get("/traffic")
def traffic_samples(request: Request, hours: int = 24, db: Session = Depends(get_db)):
    cutoff = int(time.time()) - max(1, min(hours, 24 * 7)) * 3600
    rows = (
        db.query(TrafficSample)
        .filter(TrafficSample.ts_minute >= cutoff)
        .order_by(TrafficSample.ts_minute)
        .all()
    )
    return [{"ts": r.ts_minute, "up": r.up, "down": r.down} for r in rows]
