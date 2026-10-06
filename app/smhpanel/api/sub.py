"""Public subscription endpoint (no auth; the token is the secret)."""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..models import Client
from ..services.clash import clash_config, clash_proxy_for
from ..services.links import links_for_client, subscription_payload
from .deps import get_db

router = APIRouter(tags=["subscription"])


@router.get("/sub/{token}")
def subscription(
    token: str,
    request: Request,
    format: str = "base64",
    db: Session = Depends(get_db),
):
    config = request.app.state.config
    client = db.query(Client).filter(Client.sub_token == token).first()
    if client is None:
        raise HTTPException(status_code=404, detail="not found")

    links = links_for_client(client, config)

    if format == "clash":
        proxies = []
        inbound = client.inbound
        if inbound is not None and not inbound.is_wireguard:
            proxy = clash_proxy_for(inbound, client, config)
            if proxy:
                proxies.append(proxy)
        body = clash_config(proxies)
        media_type = "text/yaml; charset=utf-8"
    elif format == "raw":
        body = subscription_payload(links, "raw")
        media_type = "text/plain; charset=utf-8"
    else:
        body = subscription_payload(links, "base64")
        media_type = "text/plain; charset=utf-8"

    title = base64.b64encode(
        f"{config.get('panel.title', 'SMH Panel')} - {client.name}".encode("utf-8")
    ).decode("ascii")

    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Profile-Title": f"base64:{title}",
            "profile-update-interval": "24",
            "Cache-Control": "no-store",
        },
    )
