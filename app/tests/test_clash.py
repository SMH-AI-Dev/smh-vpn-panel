"""Clash/Mihomo YAML generation tests."""
from __future__ import annotations

from types import SimpleNamespace

import yaml

from smhpanel.config import AppConfig
from smhpanel.services.clash import clash_config, clash_proxy_for

CFG = AppConfig({"panel": {"public_host": "203.0.113.10"}})


def test_clash_reality_proxy():
    inbound = SimpleNamespace(
        protocol="vless",
        port=443,
        tag="vless-443",
        address_override="",
        host_override="",
        sni_override="",
        params={
            "network": "tcp",
            "security": "reality",
            "reality_public": "PBK",
            "short_ids": ["sid1"],
            "sni_list": ["www.samsung.com"],
            "fingerprint": "chrome",
            "flow": "xtls-rprx-vision",
        },
    )
    client = SimpleNamespace(credential="uuid-1", name="Alice")
    proxy = clash_proxy_for(inbound, client, CFG)
    assert proxy["type"] == "vless"
    assert proxy["tls"] is True
    assert proxy["reality-opts"]["public-key"] == "PBK"
    assert proxy["client-fingerprint"] == "chrome"
    assert proxy["flow"] == "xtls-rprx-vision"
    assert proxy["servername"] == "www.samsung.com"

    text = clash_config([proxy])
    doc = yaml.safe_load(text)
    assert doc["proxies"][0]["name"] == "vless-443 - Alice"
    assert doc["proxy-groups"][0]["name"] == "PROXY"
    assert "DIRECT" in doc["proxy-groups"][0]["proxies"]
    assert doc["rules"] == ["MATCH,PROXY"]


def test_clash_ss_proxy():
    inbound = SimpleNamespace(
        protocol="shadowsocks",
        port=8388,
        tag="ss",
        address_override="",
        host_override="",
        sni_override="",
        params={"network": "tcp", "security": "none", "ss_method": "aes-256-gcm"},
    )
    client = SimpleNamespace(credential="pw", name="Bob")
    proxy = clash_proxy_for(inbound, client, CFG)
    assert proxy["type"] == "ss"
    assert proxy["cipher"] == "aes-256-gcm"
    assert proxy["password"] == "pw"
