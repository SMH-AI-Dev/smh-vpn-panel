"""Pure Xray config builders: DB state -> modern Xray (25.x) config JSON."""
from __future__ import annotations

STAT_API_INBOUND = {
    "tag": "api",
    "listen": "127.0.0.1",
    "port": 10085,
    "protocol": "dokodemo-door",
    "settings": {"address": "127.0.0.1"},
}

PRIVATE_NETS = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",
    "127.0.0.0/8",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
]

DEFAULT_SNI = "www.samsung.com"


def stream_settings(params: dict) -> dict:
    network = params.get("network", "tcp")
    security = params.get("security", "none")

    stream: dict = {"network": network}

    if network == "ws":
        ws: dict = {"path": params.get("ws_path") or "/"}
        host = params.get("host_override")
        if host:
            ws["headers"] = {"Host": host}
        stream["wsSettings"] = ws
    elif network == "grpc":
        stream["grpcSettings"] = {"serviceName": params.get("grpc_service") or "grpc"}

    if security == "reality":
        sni_list = params.get("sni_list") or [DEFAULT_SNI]
        dest = params.get("dest") or f"{sni_list[0]}:443"
        stream["security"] = "reality"
        stream["realitySettings"] = {
            "show": False,
            "dest": dest,
            "xver": 0,
            "serverNames": sni_list,
            "privateKey": params.get("reality_private", ""),
            "shortIds": params.get("short_ids") or [""],
        }
    elif security == "tls":
        stream["security"] = "tls"
        stream["tlsSettings"] = {
            "certificates": [
                {
                    "certificateFile": params.get("tls_certfile", ""),
                    "keyFile": params.get("tls_keyfile", ""),
                }
            ],
            "minVersion": "1.2",
        }
    else:
        stream["security"] = "none"

    return stream


def build_xray_inbound(inbound: dict) -> dict:
    """inbound: {tag, protocol, port, listen, params, clients: [{email_tag, credential}]}"""
    params = inbound.get("params") or {}
    protocol = inbound["protocol"]

    clients: list[dict] = []
    for client in inbound.get("clients", []):
        email = client["email_tag"]
        if protocol == "vless":
            entry = {"id": client["credential"], "email": email, "level": 0}
            if params.get("flow"):
                entry["flow"] = params["flow"]
            clients.append(entry)
        elif protocol == "vmess":
            clients.append(
                {"id": client["credential"], "email": email, "alterId": 0, "level": 0}
            )
        elif protocol == "trojan":
            clients.append({"password": client["credential"], "email": email, "level": 0})
        elif protocol == "shadowsocks":
            clients.append({"password": client["credential"], "email": email})

    if protocol == "shadowsocks":
        method = params.get("ss_method", "aes-256-gcm")
        settings: dict = {"method": method, "clients": clients}
        if not method.startswith("2022-"):
            # Shadowsocks-2022 ciphers do not support UDP; legacy ones do.
            settings["network"] = "tcp,udp"
    elif protocol == "vless":
        settings = {"clients": clients, "decryption": "none"}
    else:
        settings = {"clients": clients}

    return {
        "tag": inbound["tag"],
        "listen": inbound.get("listen") or "0.0.0.0",
        "port": inbound["port"],
        "protocol": protocol,
        "settings": settings,
        "streamSettings": stream_settings(
            {**params, "host_override": inbound.get("host_override", "")}
        ),
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls", "quic"],
            "routeOnly": False,
        },
    }


def build_routing_rules(routing_cfg: dict) -> list[dict]:
    routing_cfg = routing_cfg or {}
    rules: list[dict] = [
        {"type": "field", "inboundTag": ["api"], "outboundTag": "api"}
    ]
    if routing_cfg.get("block_port25", True):
        rules.append({"type": "field", "port": "25", "outboundTag": "blocked"})
    if routing_cfg.get("block_private", True):
        rules.append({"type": "field", "ip": PRIVATE_NETS, "outboundTag": "blocked"})
    if routing_cfg.get("block_bittorrent", False):
        rules.append(
            {"type": "field", "protocol": ["bittorrent"], "outboundTag": "blocked"}
        )
    return rules


def build_full_config(xray_inbounds: list[dict], cfg) -> dict:
    """xray_inbounds: list of dicts already accepted by build_xray_inbound()."""
    return {
        "log": {"loglevel": "warning", "access": "none", "dnsLog": False},
        "api": {"tag": "api", "services": ["StatsService", "HandlerService"]},
        "stats": {},
        "policy": {
            "levels": {
                "0": {
                    "statsUserUplink": True,
                    "statsUserDownlink": True,
                    "handshake": 4,
                    "connIdle": 300,
                    "uplinkOnly": 0,
                    "downlinkOnly": 0,
                    "bufferSize": 0,
                }
            },
            "system": {
                "statsInboundUplink": True,
                "statsInboundDownlink": True,
            },
        },
        "inbounds": [STAT_API_INBOUND, *xray_inbounds],
        "outbounds": [
            {
                "tag": "direct",
                "protocol": "freedom",
                "settings": {"domainStrategy": "UseIPv4"},
            },
            {"tag": "blocked", "protocol": "blackhole", "settings": {}},
        ],
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules": build_routing_rules(cfg.get("routing", {})),
        },
    }
