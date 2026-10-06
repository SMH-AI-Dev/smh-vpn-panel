"""Share-link and subscription builders (v2rayN / v2rayNG / Hiddify compatible)."""
from __future__ import annotations

import base64
import json
from urllib.parse import quote, urlencode


def _host_for(inbound, cfg) -> str:
    return (inbound.address_override or "") or (cfg.get("panel.public_host") or "127.0.0.1")


def _sni_for(inbound, params: dict, cfg) -> str:
    if inbound.sni_override:
        return inbound.sni_override
    sni_list = params.get("sni_list") or []
    if sni_list:
        return sni_list[0]
    return inbound.host_override or _host_for(inbound, cfg)


def _label(inbound, client) -> str:
    return f"{inbound.tag} - {client.name}"


def _qs(query: dict) -> str:
    filtered = {k: v for k, v in query.items() if v not in (None, "")}
    return urlencode(filtered, quote_via=quote, safe="")


def vless_uri(inbound, client, cfg) -> str:
    params = inbound.params or {}
    host = _host_for(inbound, cfg)
    network = params.get("network", "tcp")
    security = params.get("security", "none")

    query: dict = {"type": network, "security": security}
    if security == "reality":
        query.update(
            {
                "pbk": params.get("reality_public", ""),
                "fp": params.get("fingerprint") or "chrome",
                "sni": _sni_for(inbound, params, cfg),
                "sid": (params.get("short_ids") or [""])[0],
                "spx": params.get("spider_x") or "/",
            }
        )
    elif security == "tls":
        query["sni"] = _sni_for(inbound, params, cfg)

    if network == "ws":
        query["path"] = params.get("ws_path") or "/"
        query["host"] = inbound.host_override or host
    elif network == "grpc":
        query["serviceName"] = params.get("grpc_service") or "grpc"

    if params.get("flow"):
        query["flow"] = params["flow"]

    return (
        f"vless://{client.credential}@{host}:{inbound.port}?{_qs(query)}"
        f"#{quote(_label(inbound, client))}"
    )


def vmess_uri(inbound, client, cfg) -> str:
    params = inbound.params or {}
    host = _host_for(inbound, cfg)
    network = params.get("network", "tcp")
    security = params.get("security", "none")

    obj = {
        "v": "2",
        "ps": _label(inbound, client),
        "add": host,
        "port": str(inbound.port),
        "id": client.credential,
        "aid": "0",
        "scy": "auto",
        "net": network,
        "type": "none",
        "host": inbound.host_override or host,
        "path": params.get("ws_path") or "/",
        "tls": "tls" if security == "tls" else "",
        "sni": _sni_for(inbound, params, cfg) if security == "tls" else "",
    }
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "vmess://" + base64.b64encode(raw).decode("ascii")


def trojan_uri(inbound, client, cfg) -> str:
    params = inbound.params or {}
    host = _host_for(inbound, cfg)
    network = params.get("network", "tcp")

    query: dict = {
        "security": "tls",
        "sni": _sni_for(inbound, params, cfg),
        "type": network,
    }
    if network == "ws":
        query["path"] = params.get("ws_path") or "/"
        query["host"] = inbound.host_override or host
    elif network == "grpc":
        query["serviceName"] = params.get("grpc_service") or "grpc"

    return (
        f"trojan://{client.credential}@{host}:{inbound.port}?{_qs(query)}"
        f"#{quote(_label(inbound, client))}"
    )


def ss_uri(inbound, client, cfg) -> str:
    params = inbound.params or {}
    host = _host_for(inbound, cfg)
    method = params.get("ss_method", "aes-256-gcm")
    userinfo = base64.urlsafe_b64encode(
        f"{method}:{client.credential}".encode("utf-8")
    ).decode("ascii")
    return f"ss://{userinfo}@{host}:{inbound.port}#{quote(_label(inbound, client))}"


_URI_BUILDERS = {
    "vless": vless_uri,
    "vmess": vmess_uri,
    "trojan": trojan_uri,
    "shadowsocks": ss_uri,
}


def links_for_client(client, cfg) -> list[str]:
    inbound = client.inbound
    if inbound is None or inbound.is_wireguard:
        return []
    builder = _URI_BUILDERS.get(inbound.protocol)
    if not builder:
        return []
    return [builder(inbound, client, cfg)]


def subscription_url(client, cfg) -> str:
    host = cfg.get("subscription.host") or cfg.get("panel.public_host") or "127.0.0.1"
    port = int(cfg.get("subscription.port") or cfg.get("panel.port") or 2053)
    scheme = "https" if cfg.get("panel.tls.enabled", True) else "http"
    return f"{scheme}://{host}:{port}/sub/{client.sub_token}"


def subscription_payload(links: list[str], fmt: str = "base64") -> str:
    body = "\n".join(links)
    if fmt == "raw":
        return body + ("\n" if links else "")
    if not links:
        return ""
    return base64.b64encode(body.encode("utf-8")).decode("ascii")
