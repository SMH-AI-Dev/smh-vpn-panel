"""Xray config builder tests."""
from __future__ import annotations

import base64

from smhpanel.config import AppConfig
from smhpanel.services.xray_config import (
    build_full_config,
    build_xray_inbound,
    stream_settings,
)


def cfg() -> AppConfig:
    return AppConfig({"routing": {"block_port25": True, "block_private": True, "block_bittorrent": False}})


def vless_inbound() -> dict:
    return {
        "tag": "vless-reality",
        "protocol": "vless",
        "port": 443,
        "listen": "0.0.0.0",
        "params": {
            "network": "tcp",
            "security": "reality",
            "flow": "xtls-rprx-vision",
            "reality_private": "PRIVKEY",
            "short_ids": ["abcd1234"],
            "sni_list": ["www.samsung.com"],
            "dest": "",
        },
        "clients": [
            {"email_tag": "vless-reality.1", "credential": "uuid-1"},
        ],
    }


def test_stream_reality_dest_default():
    stream = stream_settings(
        {
            "network": "tcp",
            "security": "reality",
            "reality_private": "PRIVKEY",
            "short_ids": ["abcd1234"],
            "sni_list": ["www.samsung.com"],
        }
    )
    assert stream["security"] == "reality"
    assert stream["realitySettings"]["dest"] == "www.samsung.com:443"
    assert stream["realitySettings"]["privateKey"] == "PRIVKEY"
    assert stream["realitySettings"]["serverNames"] == ["www.samsung.com"]


def test_build_vless_inbound():
    inbound = build_xray_inbound(vless_inbound())
    assert inbound["tag"] == "vless-reality"
    assert inbound["port"] == 443
    assert inbound["protocol"] == "vless"
    assert inbound["settings"]["decryption"] == "none"
    client = inbound["settings"]["clients"][0]
    assert client["id"] == "uuid-1"
    assert client["email"] == "vless-reality.1"
    assert client["flow"] == "xtls-rprx-vision"
    assert inbound["streamSettings"]["security"] == "reality"
    assert inbound["sniffing"]["enabled"] is True


def test_build_ss_inbound_2022_no_udp_legacy_udp():
    legacy = build_xray_inbound(
        {
            "tag": "ss-legacy",
            "protocol": "shadowsocks",
            "port": 8388,
            "listen": "0.0.0.0",
            "params": {"network": "tcp", "security": "none", "ss_method": "aes-256-gcm"},
            "clients": [{"email_tag": "ss.1", "credential": "pw"}],
        }
    )
    assert legacy["settings"]["network"] == "tcp,udp"
    modern = build_xray_inbound(
        {
            "tag": "ss-2022",
            "protocol": "shadowsocks",
            "port": 8389,
            "listen": "0.0.0.0",
            "params": {
                "network": "tcp",
                "security": "none",
                "ss_method": "2022-blake3-aes-256-gcm",
                "ss_server_key": "SERVERKEY==",
            },
            "clients": [{"email_tag": "ss.2", "credential": "pw2"}],
        }
    )
    assert "network" not in modern["settings"]
    assert modern["settings"]["method"] == "2022-blake3-aes-256-gcm"
    assert modern["settings"]["password"] == "SERVERKEY=="


def test_full_config_shape():
    config = build_full_config([build_xray_inbound(vless_inbound())], cfg())
    assert config["api"]["tag"] == "api"
    assert "StatsService" in config["api"]["services"]
    assert config["stats"] == {}
    assert config["policy"]["levels"]["0"]["statsUserUplink"] is True
    assert config["inbounds"][0]["protocol"] == "dokodemo-door"
    assert config["inbounds"][0]["port"] == 10085
    assert config["inbounds"][1]["tag"] == "vless-reality"
    tags = [out["tag"] for out in config["outbounds"]]
    assert tags == ["direct", "blocked"]
    rules = config["routing"]["rules"]
    assert rules[0]["inboundTag"] == ["api"]
    assert any(rule.get("port") == "25" for rule in rules)
    assert any("10.0.0.0/8" in rule.get("ip", []) for rule in rules)
    assert not any(rule.get("protocol") == ["bittorrent"] for rule in rules)


def test_full_config_routing_toggles():
    custom = AppConfig(
        {
            "routing": {
                "block_port25": False,
                "block_private": False,
                "block_bittorrent": True,
            }
        }
    )
    config = build_full_config([], custom)
    rules = config["routing"]["rules"]
    assert not any(rule.get("port") == "25" for rule in rules)
    assert not any("10.0.0.0/8" in rule.get("ip", []) for rule in rules)
    assert any(rule.get("protocol") == ["bittorrent"] for rule in rules)


def test_tls_settings_shape():
    stream = stream_settings(
        {
            "network": "tcp",
            "security": "tls",
            "tls_certfile": "/etc/smhpanel/certs/x.crt",
            "tls_keyfile": "/etc/smhpanel/certs/x.key",
        }
    )
    assert stream["security"] == "tls"
    certs = stream["tlsSettings"]["certificates"][0]
    assert certs["certificateFile"].endswith(".crt")
    assert certs["keyFile"].endswith(".key")


def test_ws_and_grpc_streams():
    ws = stream_settings({"network": "ws", "ws_path": "/media"})
    assert ws["wsSettings"]["path"] == "/media"
    grpc = stream_settings({"network": "grpc", "grpc_service": "svc1"})
    assert grpc["grpcSettings"]["serviceName"] == "svc1"
