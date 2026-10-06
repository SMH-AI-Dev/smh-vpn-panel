"""Share-link format tests."""
from __future__ import annotations

import base64
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urlparse

from smhpanel.config import AppConfig
from smhpanel.services.links import (
    ss_uri,
    subscription_payload,
    trojan_uri,
    vless_uri,
    vmess_uri,
)

CFG = AppConfig(
    {
        "panel": {"public_host": "203.0.113.10", "tls": {"enabled": True}, "port": 2053},
        "subscription": {"host": "", "port": 0},
    }
)

CLIENT = SimpleNamespace(
    credential="11111111-2222-3333-4444-555555555555", name="Alice", sub_token="tok123"
)


def make_inbound(protocol="vless", port=443, **params):
    base = {
        "network": "tcp",
        "security": "none",
        "flow": "",
        "ws_path": "/",
        "grpc_service": "grpc",
        "sni_list": [],
        "reality_public": "",
        "short_ids": [],
        "fingerprint": "chrome",
        "ss_method": "aes-256-gcm",
    }
    base.update(params)
    return SimpleNamespace(
        protocol=protocol,
        port=port,
        tag="test",
        params=base,
        address_override="",
        host_override="",
        sni_override="",
    )


def test_vless_reality_uri():
    inbound = make_inbound(
        security="reality",
        reality_public="PBK123",
        short_ids=["abcd1234"],
        sni_list=["www.samsung.com"],
        flow="xtls-rprx-vision",
    )
    uri = vless_uri(inbound, CLIENT, CFG)
    assert uri.startswith("vless://11111111-2222-3333-4444-555555555555@203.0.113.10:443?")
    assert uri.endswith("#test%20-%20Alice")
    parsed = urlparse(uri)
    query = parse_qs(parsed.query)
    assert query["type"] == ["tcp"]
    assert query["security"] == ["reality"]
    assert query["pbk"] == ["PBK123"]
    assert query["fp"] == ["chrome"]
    assert query["sni"] == ["www.samsung.com"]
    assert query["sid"] == ["abcd1234"]
    assert query["spx"] == ["/"]
    assert query["flow"] == ["xtls-rprx-vision"]
    # raw URI must encode the spider path
    assert "spx=%2F" in uri


def test_vless_ws_uri():
    inbound = make_inbound(network="ws", ws_path="/media")
    inbound.host_override = "cdn.example.com"
    uri = vless_uri(inbound, CLIENT, CFG)
    query = parse_qs(urlparse(uri).query)
    assert query["type"] == ["ws"]
    assert query["path"] == ["/media"]
    assert query["host"] == ["cdn.example.com"]
    assert query["security"] == ["none"]


def test_vless_grpc_uri():
    inbound = make_inbound(network="grpc", grpc_service="mysvc")
    uri = vless_uri(inbound, CLIENT, CFG)
    query = parse_qs(urlparse(uri).query)
    assert query["type"] == ["grpc"]
    assert query["serviceName"] == ["mysvc"]


def test_vmess_ws_uri_roundtrip():
    inbound = make_inbound(protocol="vmess", port=8443, network="ws", ws_path="/x")
    uri = vmess_uri(inbound, CLIENT, CFG)
    assert uri.startswith("vmess://")
    payload = json.loads(base64.b64decode(uri[len("vmess://"):]).decode("utf-8"))
    assert payload["v"] == "2"
    assert payload["add"] == "203.0.113.10"
    assert payload["port"] == "8443"
    assert payload["id"] == CLIENT.credential
    assert payload["net"] == "ws"
    assert payload["path"] == "/x"
    assert payload["ps"] == "test - Alice"


def test_trojan_uri():
    inbound = make_inbound(protocol="trojan", port=443, security="tls")
    inbound.sni_override = "tr.example.com"
    uri = trojan_uri(inbound, CLIENT, CFG)
    assert uri.startswith("trojan://11111111-2222-3333-4444-555555555555@203.0.113.10:443?")
    query = parse_qs(urlparse(uri).query)
    assert query["security"] == ["tls"]
    assert query["sni"] == ["tr.example.com"]
    assert query["type"] == ["tcp"]


def test_ss_uri_roundtrip():
    inbound = make_inbound(protocol="shadowsocks", port=8388, ss_method="chacha20-ietf-poly1305")
    client = SimpleNamespace(credential="secret", name="Bob", sub_token="t2")
    uri = ss_uri(inbound, client, CFG)
    assert uri.startswith("ss://")
    userinfo, rest = uri[len("ss://"):].split("@", 1)
    assert rest.startswith("203.0.113.10:8388#")
    decoded = base64.urlsafe_b64decode(userinfo).decode("utf-8")
    assert decoded == "chacha20-ietf-poly1305:secret"


def test_subscription_payload_base64():
    links = ["vless://a@h:1#x", "trojan://b@h:2#y"]
    body = subscription_payload(links, "base64")
    assert base64.b64decode(body).decode("utf-8") == "\n".join(links)
    raw = subscription_payload(links, "raw")
    assert raw == "\n".join(links) + "\n"
