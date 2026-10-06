"""Client management endpoints."""
from __future__ import annotations

import io
from datetime import datetime

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..keys import (
    new_sub_token,
    new_uuid,
    random_b64,
    random_password,
    x25519_keypair_std,
)
from ..models import Client, Inbound
from ..schemas import ClientIn, ClientUpdate, EnableIn
from ..services.links import links_for_client, subscription_url
from ..services.wireguard import allocate_ip, build_client_conf
from .deps import audit, get_db

router = APIRouter(prefix="/api/clients", tags=["clients"])


def _get_or_404(db: Session, client_id: int) -> Client:
    row = db.get(Client, client_id)
    if row is None:
        raise HTTPException(status_code=404, detail="client not found")
    return row


def _credential_for(inbound: Inbound) -> str:
    if inbound.protocol in ("vless", "vmess"):
        return new_uuid()
    if inbound.protocol == "trojan":
        return random_password(24)
    if inbound.protocol == "shadowsocks":
        method = (inbound.params or {}).get("ss_method", "")
        if method == "2022-blake3-aes-128-gcm":
            return random_b64(16)
        if method.startswith("2022-"):
            return random_b64(32)
        return random_password(24)
    return random_password(24)


def _make_email(db: Session, inbound: Inbound) -> str:
    n = len(inbound.clients) + 1
    while True:
        tag = f"{inbound.tag}.{n}"
        if db.query(Client).filter(Client.email_tag == tag).first() is None:
            return tag
        n += 1


def _parse_expiry(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59
    )


def serialize_client(c: Client) -> dict:
    inbound = c.inbound
    extra = dict(c.extra or {})
    extra.pop("wg_private", None)
    return {
        "id": c.id,
        "inbound_id": c.inbound_id,
        "inbound_tag": inbound.tag if inbound else None,
        "protocol": inbound.protocol if inbound else None,
        "name": c.name,
        "credential": c.credential,
        "email_tag": c.email_tag,
        "enabled": c.enabled,
        "disabled_reason": c.disabled_reason,
        "quota_gb": c.quota_gb,
        "expiry": c.expiry.date().isoformat() if c.expiry else None,
        "up": c.up_bytes or 0,
        "down": c.down_bytes or 0,
        "used": (c.up_bytes or 0) + (c.down_bytes or 0),
        "sub_token": c.sub_token,
        "note": c.note or "",
        "extra": extra,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("")
def list_clients(
    request: Request, inbound_id: int | None = None, db: Session = Depends(get_db)
):
    query = db.query(Client).order_by(Client.id.desc())
    if inbound_id is not None:
        query = query.filter(Client.inbound_id == inbound_id)
    return [serialize_client(c) for c in query.all()]


@router.get("/{client_id}")
def get_client(client_id: int, db: Session = Depends(get_db)):
    return serialize_client(_get_or_404(db, client_id))


@router.post("")
def create_client(payload: ClientIn, request: Request, db: Session = Depends(get_db)):
    config = request.app.state.config
    manager = request.app.state.manager
    wg_manager = request.app.state.wg_manager
    actor = request.state.admin.get("username", "admin")

    inbound = db.get(Inbound, payload.inbound_id)
    if inbound is None:
        raise HTTPException(status_code=404, detail="inbound not found")

    extra: dict = {}
    if inbound.is_wireguard:
        used = {(c.extra or {}).get("wg_ip") for c in inbound.clients}
        used.discard(None)
        ip = allocate_ip(config, used)
        private, public = x25519_keypair_std()
        credential = public
        extra = {"wg_private": private, "wg_public": public, "wg_ip": ip}
    else:
        credential = _credential_for(inbound)

    client = Client(
        inbound_id=inbound.id,
        name=payload.name,
        credential=credential,
        email_tag=_make_email(db, inbound),
        quota_gb=payload.quota_gb,
        expiry=_parse_expiry(payload.expiry),
        sub_token=new_sub_token(),
        note=payload.note or "",
        extra=extra,
    )
    db.add(client)
    audit(db, actor, "client.create", f"{client.name} @ {inbound.tag}")
    db.commit()

    ok, msg = (wg_manager if inbound.is_wireguard else manager).apply()
    data = serialize_client(client)
    data["apply_error"] = None if ok else msg
    return data


@router.patch("/{client_id}")
def update_client(
    client_id: int,
    payload: ClientUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    client = _get_or_404(db, client_id)
    fields = payload.model_fields_set
    if "name" in fields and payload.name is not None:
        client.name = payload.name
    if "quota_gb" in fields:
        client.quota_gb = payload.quota_gb
    if "expiry" in fields:
        client.expiry = _parse_expiry(payload.expiry)
    if "note" in fields and payload.note is not None:
        client.note = payload.note
    audit(db, request.state.admin.get("username", "admin"), "client.update", client.name)
    db.commit()
    return serialize_client(client)


@router.post("/{client_id}/reset-usage")
def reset_usage(
    client_id: int, request: Request, db: Session = Depends(get_db)
):
    client = _get_or_404(db, client_id)
    client.up_bytes = 0
    client.down_bytes = 0
    audit(db, request.state.admin.get("username", "admin"), "client.reset_usage", client.name)
    db.commit()
    return serialize_client(client)


@router.post("/{client_id}/enable")
def enable_client(
    client_id: int,
    payload: EnableIn,
    request: Request,
    db: Session = Depends(get_db),
):
    manager = request.app.state.manager
    wg_manager = request.app.state.wg_manager
    client = _get_or_404(db, client_id)
    inbound = client.inbound

    client.enabled = payload.enabled
    if payload.enabled:
        client.disabled_reason = None
    audit(
        db,
        request.state.admin.get("username", "admin"),
        "client.enable" if payload.enabled else "client.disable",
        client.name,
    )
    db.commit()

    ok, msg = (
        wg_manager if (inbound is not None and inbound.is_wireguard) else manager
    ).apply()
    data = serialize_client(client)
    data["apply_error"] = None if ok else msg
    return data


@router.delete("/{client_id}")
def delete_client(client_id: int, request: Request, db: Session = Depends(get_db)):
    manager = request.app.state.manager
    wg_manager = request.app.state.wg_manager
    client = _get_or_404(db, client_id)
    inbound = client.inbound
    name = client.name
    is_wg = inbound is not None and inbound.is_wireguard

    db.delete(client)
    audit(db, request.state.admin.get("username", "admin"), "client.delete", name)
    db.commit()

    ok, msg = (wg_manager if is_wg else manager).apply()
    return {"ok": True, "apply_error": None if ok else msg}


@router.get("/{client_id}/links")
def client_links(client_id: int, request: Request, db: Session = Depends(get_db)):
    config = request.app.state.config
    client = _get_or_404(db, client_id)
    inbound = client.inbound

    links = links_for_client(client, config)
    wg_conf = None
    if inbound is not None and inbound.is_wireguard:
        wg_conf = build_client_conf(inbound, client, config, "")

    return {
        "links": links,
        "subscription_url": subscription_url(client, config),
        "wg_conf": wg_conf,
    }


@router.get("/{client_id}/qr.png")
def client_qr(
    client_id: int,
    request: Request,
    target: str = "sub",
    index: int = 0,
    db: Session = Depends(get_db),
):
    config = request.app.state.config
    client = _get_or_404(db, client_id)
    inbound = client.inbound

    if target == "link":
        if inbound is not None and inbound.is_wireguard:
            data = build_client_conf(inbound, client, config, "")
        else:
            links = links_for_client(client, config)
            if not links or index >= len(links):
                raise HTTPException(status_code=404, detail="no link to encode")
            data = links[index]
    else:
        data = subscription_url(client, config)

    image = qrcode.make(data)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(
        buffer.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )
