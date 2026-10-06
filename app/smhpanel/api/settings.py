"""Settings endpoints (backed by config.json)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..schemas import SettingsPatch
from .deps import audit, get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])

ALLOWED = {
    "panel.title": str,
    "panel.public_host": str,
    "subscription.host": str,
    "subscription.port": int,
    "firewall.auto_open": bool,
    "routing.block_port25": bool,
    "routing.block_private": bool,
    "routing.block_bittorrent": bool,
    "wireguard.enabled": bool,
    "wireguard.port": int,
    "wireguard.subnet": str,
    "wireguard.mtu": int,
    "wireguard.dns": str,
    "wireguard.wan_iface": str,
}

MUTABLE = ("subscription", "firewall", "routing", "wireguard", "panel")


def _safe_config(config) -> dict:
    panel = dict(config.get("panel") or {})
    tls = dict(panel.get("tls") or {})
    panel["tls"] = {
        "enabled": bool(tls.get("enabled")),
        "certfile": bool(tls.get("certfile")),
    }
    return {
        "panel": panel,
        "subscription": config.get("subscription"),
        "firewall": config.get("firewall"),
        "routing": config.get("routing"),
        "wireguard": config.get("wireguard"),
        "dev_mode": config.is_dev(),
    }


@router.get("")
def get_settings(request: Request):
    return _safe_config(request.app.state.config)


@router.patch("")
def patch_settings(
    payload: SettingsPatch, request: Request, db: Session = Depends(get_db)
):
    config = request.app.state.config
    manager = request.app.state.manager
    actor = request.state.admin.get("username", "admin")

    applied: list[str] = []
    for top, leaves in (payload.patch or {}).items():
        if not isinstance(leaves, dict):
            raise HTTPException(400, f"invalid section: {top}")
        for leaf, value in leaves.items():
            dotted = f"{top}.{leaf}"
            if dotted not in ALLOWED:
                raise HTTPException(400, f"unknown setting: {dotted}")
            expected = ALLOWED[dotted]
            if expected is bool and not isinstance(value, bool):
                raise HTTPException(400, f"{dotted} must be a boolean")
            if expected is int and not isinstance(value, int):
                raise HTTPException(400, f"{dotted} must be an integer")
            if expected is str and not isinstance(value, str):
                raise HTTPException(400, f"{dotted} must be a string")
            config.set(dotted, value)
            applied.append(dotted)

    config.save()
    audit(db, actor, "settings.update", ", ".join(applied) or "(no changes)")
    db.commit()

    apply_result = None
    if any(path.startswith("routing.") for path in applied):
        ok, msg = manager.apply()
        apply_result = {"ok": ok, "message": msg}

    return {"ok": True, "applied": applied, "apply": apply_result}
