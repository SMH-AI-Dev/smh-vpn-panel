"""Minimal Mihomo/Clash-Meta YAML subscription generation (flow-style YAML)."""
from __future__ import annotations

import json

from .links import _host_for, _sni_for


def clash_proxy_for(inbound, client, cfg) -> dict | None:
    params = inbound.params or {}
    host = _host_for(inbound, cfg)
    name = f"{inbound.tag} - {client.name}"
    protocol = inbound.protocol
    network = params.get("network", "tcp")
    security = params.get("security", "none")

    if protocol == "vless":
        proxy: dict = {
            "name": name,
            "type": "vless",
            "server": host,
            "port": inbound.port,
            "uuid": client.credential,
            "udp": True,
            "tls": security in ("tls", "reality"),
        }
        if params.get("flow"):
            proxy["flow"] = params["flow"]
        if security == "reality":
            proxy["servername"] = _sni_for(inbound, params, cfg)
            proxy["client-fingerprint"] = params.get("fingerprint") or "chrome"
            proxy["reality-opts"] = {
                "public-key": params.get("reality_public", ""),
                "short-id": (params.get("short_ids") or [""])[0],
            }
        elif security == "tls":
            proxy["servername"] = _sni_for(inbound, params, cfg)
    elif protocol == "vmess":
        proxy = {
            "name": name,
            "type": "vmess",
            "server": host,
            "port": inbound.port,
            "uuid": client.credential,
            "alterId": 0,
            "cipher": "auto",
            "udp": True,
            "tls": security == "tls",
        }
        if security == "tls":
            proxy["servername"] = _sni_for(inbound, params, cfg)
    elif protocol == "trojan":
        proxy = {
            "name": name,
            "type": "trojan",
            "server": host,
            "port": inbound.port,
            "password": client.credential,
            "udp": True,
            "sni": _sni_for(inbound, params, cfg),
        }
    elif protocol == "shadowsocks":
        proxy = {
            "name": name,
            "type": "ss",
            "server": host,
            "port": inbound.port,
            "cipher": params.get("ss_method", "aes-256-gcm"),
            "password": client.credential,
            "udp": True,
        }
    else:
        return None

    if network == "ws":
        proxy["network"] = "ws"
        opts: dict = {"path": params.get("ws_path") or "/"}
        if inbound.host_override:
            opts["headers"] = {"Host": inbound.host_override}
        proxy["ws-opts"] = opts
    elif network == "grpc":
        proxy["network"] = "grpc"
        proxy["grpc-opts"] = {"grpc-service-name": params.get("grpc_service") or "grpc"}

    return proxy


def clash_config(proxies: list[dict]) -> str:
    names = [p["name"] for p in proxies]
    lines: list[str] = ["proxies:"]
    for proxy in proxies:
        lines.append("  - " + json.dumps(proxy, ensure_ascii=False))
    lines.append("proxy-groups:")
    lines.append(
        "  - "
        + json.dumps(
            {"name": "PROXY", "type": "select", "proxies": names + ["DIRECT"]},
            ensure_ascii=False,
        )
    )
    lines.append("rules:")
    lines.append("  - MATCH,PROXY")
    return "\n".join(lines) + "\n"
