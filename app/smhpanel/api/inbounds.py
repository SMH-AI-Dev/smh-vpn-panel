"""Inbound management endpoints."""
from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..keys import random_b64, short_ids, x25519_keypair
from ..models import Inbound
from ..schemas import EnableIn, InboundIn, InboundUpdate
from ..services.wireguard import server_address
from .deps import audit, get_db

router = APIRouter(prefix="/api/inbounds", tags=["inbounds"])

REALITY_DEFAULT_SNIS = ["www.samsung.com", "www.lovelive-anime.jp", "dl.google.com"]

SS_METHODS = [
    "2022-blake3-aes-128-gcm",
    "2022-blake3-aes-256-gcm",
    "2022-blake3-chacha20-poly1305",
    "aes-256-gcm",
    "chacha20-ietf-poly1305",
]


def _get_or_404(db: Session, inbound_id: int) -> Inbound:
    row = db.get(Inbound, inbound_id)
    if row is None:
        raise HTTPException(status_code=404, detail="inbound not found")
    return row


def _unique_tag(db: Session, base: str) -> str:
    base = (base or "inbound").strip() or "inbound"
    base = "".join(ch for ch in base if ch.isalnum() or ch in "-_.") or "inbound"
    tag, n = base, 1
    while db.query(Inbound).filter(Inbound.tag == tag).first() is not None:
        n += 1
        tag = f"{base}-{n}"
    return tag


def _serialize(row: Inbound) -> dict:
    params = dict(row.params or {})
    for key in ("reality_private", "server_private"):
        params.pop(key, None)
    clients = row.clients
    return {
        "id": row.id,
        "tag": row.tag,
        "protocol": row.protocol,
        "port": row.port,
        "listen": row.listen,
        "enabled": row.enabled,
        "is_wireguard": row.is_wireguard,
        "params": params,
        "address_override": row.address_override,
        "host_override": row.host_override,
        "sni_override": row.sni_override,
        "client_count": len(clients),
        "active_clients": sum(1 for c in clients if c.enabled),
        "up": sum((c.up_bytes or 0) for c in clients),
        "down": sum((c.down_bytes or 0) for c in clients),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _validate_payload(payload: InboundIn) -> None:
    if payload.protocol == "shadowsocks":
        if payload.ss_method and payload.ss_method not in SS_METHODS:
            raise HTTPException(400, "unsupported shadowsocks method")
        if payload.network != "tcp":
            raise HTTPException(400, "shadowsocks supports the tcp network only")
        if payload.security != "none":
            raise HTTPException(400, "shadowsocks does not use TLS/Reality")
    if payload.protocol == "trojan" and payload.security != "tls":
        raise HTTPException(400, "trojan requires TLS")
    if payload.security == "reality":
        if payload.protocol != "vless":
            raise HTTPException(400, "reality is supported for VLESS only")
        if payload.network != "tcp":
            raise HTTPException(400, "reality requires the tcp network")


def _ensure_port_free(db: Session, port: int, exclude_id: int | None = None) -> None:
    query = db.query(Inbound).filter(Inbound.port == port, Inbound.enabled.is_(True))
    if exclude_id is not None:
        query = query.filter(Inbound.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(400, f"port {port} is already used by another enabled inbound")


def _resolve_tls_params(config, payload: InboundIn) -> dict:
    host = payload.sni_override or payload.host_override or config.get("panel.public_host", "")
    certs_dir = Path(config.paths()["certs"])
    certfile = certs_dir / f"{host}.crt"
    keyfile = certs_dir / f"{host}.key"
    if not config.is_dev() and not (certfile.exists() and keyfile.exists()):
        raise HTTPException(
            400,
            f"no certificate found for '{host}' — issue one first (Settings → Certificates)",
        )
    return {"tls_certfile": str(certfile), "tls_keyfile": str(keyfile)}


@router.get("")
def list_inbounds(request: Request, db: Session = Depends(get_db)):
    rows = db.query(Inbound).order_by(Inbound.id).all()
    return [_serialize(row) for row in rows]


@router.get("/{inbound_id}")
def get_inbound(inbound_id: int, db: Session = Depends(get_db)):
    return _serialize(_get_or_404(db, inbound_id))


@router.post("")
def create_inbound(
    payload: InboundIn, request: Request, db: Session = Depends(get_db)
):
    config = request.app.state.config
    manager = request.app.state.manager
    wg_manager = request.app.state.wg_manager
    actor = request.state.admin.get("username", "admin")

    if payload.protocol == "wireguard":
        if db.query(Inbound).filter(Inbound.is_wireguard.is_(True)).count():
            raise HTTPException(400, "a wireguard interface already exists")
        _ensure_port_free(db, payload.port)
        private, public = x25519_keypair()
        row = Inbound(
            tag=_unique_tag(db, payload.tag or "wireguard"),
            protocol="wireguard",
            port=payload.port,
            listen=payload.listen,
            enabled=payload.enabled,
            is_wireguard=True,
            params={
                "iface": config.get("wireguard.iface", "wg0"),
                "server_private": private,
                "server_public": public,
                "server_address": server_address(config),
            },
        )
        db.add(row)
        audit(db, actor, "inbound.create", f"{row.tag} (wireguard:{row.port})")
        db.commit()
        ok, msg = wg_manager.apply()
        if row.enabled:
            manager.open_port(row.port, "udp")
        data = _serialize(row)
        data["apply_error"] = None if ok else msg
        return data

    _validate_payload(payload)
    _ensure_port_free(db, payload.port)

    params: dict = {
        "network": payload.network,
        "security": payload.security,
        "flow": payload.flow,
        "fingerprint": payload.fingerprint or "chrome",
    }
    if (
        payload.protocol == "vless"
        and payload.network == "tcp"
        and payload.security in ("reality", "tls")
        and not params["flow"]
    ):
        params["flow"] = "xtls-rprx-vision"
    if payload.network == "ws":
        params["ws_path"] = payload.ws_path or f"/{secrets.token_hex(3)}"
    if payload.network == "grpc":
        params["grpc_service"] = payload.grpc_service or f"grpc-{secrets.token_hex(3)}"
    if payload.security == "reality":
        private, public = x25519_keypair()
        params.update(
            {
                "reality_private": private,
                "reality_public": public,
                "short_ids": short_ids(2),
                "sni_list": payload.sni_list or list(REALITY_DEFAULT_SNIS),
                "dest": payload.dest or "",
                "spider_x": "/",
            }
        )
    if payload.security == "tls":
        params.update(_resolve_tls_params(config, payload))
    if payload.protocol == "shadowsocks":
        method = payload.ss_method or "2022-blake3-aes-256-gcm"
        params["ss_method"] = method
        if method.startswith("2022-"):
            key_len = 16 if method.endswith("aes-128-gcm") else 32
            params["ss_server_key"] = random_b64(key_len)

    row = Inbound(
        tag=_unique_tag(db, payload.tag or f"{payload.protocol}-{payload.port}"),
        protocol=payload.protocol,
        port=payload.port,
        listen=payload.listen,
        enabled=payload.enabled,
        params=params,
        address_override=payload.address_override,
        host_override=payload.host_override,
        sni_override=payload.sni_override,
    )
    db.add(row)
    audit(db, actor, "inbound.create", f"{row.tag} ({row.protocol}:{row.port})")
    db.commit()

    ok, msg = manager.apply()
    if row.enabled:
        manager.open_port(row.port, "tcp")
    data = _serialize(row)
    data["apply_error"] = None if ok else msg
    return data


@router.patch("/{inbound_id}")
def update_inbound(
    inbound_id: int,
    payload: InboundUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    config = request.app.state.config
    manager = request.app.state.manager
    wg_manager = request.app.state.wg_manager
    row = _get_or_404(db, inbound_id)
    actor = request.state.admin.get("username", "admin")

    if payload.port is not None and payload.port != row.port:
        _ensure_port_free(db, payload.port, exclude_id=row.id)
    old_port, old_enabled = row.port, row.enabled

    if payload.port is not None:
        row.port = payload.port
    if payload.listen is not None:
        row.listen = payload.listen
    if payload.enabled is not None:
        row.enabled = payload.enabled
    if payload.tag is not None:
        row.tag = _unique_tag(db, payload.tag)
    if payload.address_override is not None:
        row.address_override = payload.address_override
    if payload.host_override is not None:
        row.host_override = payload.host_override
    if payload.sni_override is not None:
        row.sni_override = payload.sni_override

    if not row.is_wireguard:
        params = dict(row.params or {})
        if payload.network is not None:
            params["network"] = payload.network
        if payload.security is not None:
            params["security"] = payload.security
        if payload.flow is not None:
            params["flow"] = payload.flow
        if payload.ws_path is not None:
            params["ws_path"] = payload.ws_path
        if payload.grpc_service is not None:
            params["grpc_service"] = payload.grpc_service
        if payload.sni_list is not None:
            params["sni_list"] = payload.sni_list
        if payload.dest is not None:
            params["dest"] = payload.dest
        if payload.fingerprint is not None:
            params["fingerprint"] = payload.fingerprint or "chrome"
        if params.get("security") == "reality" and not params.get("reality_private"):
            private, public = x25519_keypair()
            params.update(
                {
                    "reality_private": private,
                    "reality_public": public,
                    "short_ids": short_ids(2),
                    "sni_list": params.get("sni_list") or list(REALITY_DEFAULT_SNIS),
                    "spider_x": "/",
                }
            )
        if params.get("security") == "tls" and not params.get("tls_certfile"):
            params.update(_resolve_tls_params(config, payload))
        row.params = params

    audit(db, actor, "inbound.update", f"{row.tag} (#{row.id})")
    db.commit()

    proto = "udp" if row.is_wireguard else "tcp"
    ok, msg = (wg_manager if row.is_wireguard else manager).apply()
    if old_port != row.port:
        manager.close_port(old_port, proto)
        manager.open_port(row.port, proto)
    elif old_enabled != row.enabled:
        (manager.open_port if row.enabled else manager.close_port)(row.port, proto)

    data = _serialize(row)
    data["apply_error"] = None if ok else msg
    return data


@router.post("/{inbound_id}/enable")
def enable_inbound(
    inbound_id: int,
    payload: EnableIn,
    request: Request,
    db: Session = Depends(get_db),
):
    manager = request.app.state.manager
    wg_manager = request.app.state.wg_manager
    row = _get_or_404(db, inbound_id)
    actor = request.state.admin.get("username", "admin")

    row.enabled = payload.enabled
    audit(db, actor, "inbound.enable" if payload.enabled else "inbound.disable", row.tag)
    db.commit()

    proto = "udp" if row.is_wireguard else "tcp"
    ok, msg = (wg_manager if row.is_wireguard else manager).apply()
    if payload.enabled:
        manager.open_port(row.port, proto)
    else:
        manager.close_port(row.port, proto)

    data = _serialize(row)
    data["apply_error"] = None if ok else msg
    return data


@router.delete("/{inbound_id}")
def delete_inbound(inbound_id: int, request: Request, db: Session = Depends(get_db)):
    manager = request.app.state.manager
    wg_manager = request.app.state.wg_manager
    row = _get_or_404(db, inbound_id)
    actor = request.state.admin.get("username", "admin")

    tag, port, is_wg = row.tag, row.port, row.is_wireguard
    manager.close_port(port, "udp" if is_wg else "tcp")
    db.delete(row)
    audit(db, actor, "inbound.delete", tag)
    db.commit()

    ok, msg = (wg_manager if is_wg else manager).apply()
    return {"ok": True, "apply_error": None if ok else msg}
