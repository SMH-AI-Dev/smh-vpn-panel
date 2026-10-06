"""WireGuard config generation and dump parsing tests."""
from __future__ import annotations

from types import SimpleNamespace

from smhpanel.config import AppConfig
from smhpanel.services.wireguard import (
    allocate_ip,
    build_client_conf,
    build_server_conf,
    parse_dump,
    server_address,
)

CFG = AppConfig(
    {
        "wireguard": {
            "iface": "wg0",
            "port": 51820,
            "subnet": "10.66.66.0/24",
            "mtu": 1420,
            "dns": "1.1.1.1",
            "wan_iface": "eth0",
        },
        "panel": {"public_host": "203.0.113.10"},
    }
)


def test_server_address_and_allocate():
    assert server_address(CFG) == "10.66.66.1/24"
    assert allocate_ip(CFG, set()) == "10.66.66.2"
    assert allocate_ip(CFG, {"10.66.66.2", "10.66.66.3"}) == "10.66.66.4"


def test_build_server_conf():
    inbound = SimpleNamespace(
        port=51820,
        params={"server_private": "SRVPRIV", "server_address": "10.66.66.1/24"},
    )
    clients = [
        {"name": "Phone", "extra": {"wg_public": "PHONEPUB", "wg_ip": "10.66.66.2"}},
        {"name": "Laptop", "extra": {"wg_public": "LAPTOPPUB", "wg_ip": "10.66.66.3"}},
    ]
    conf = build_server_conf(inbound, clients, CFG)
    assert "[Interface]" in conf
    assert "Address = 10.66.66.1/24" in conf
    assert "ListenPort = 51820" in conf
    assert "PrivateKey = SRVPRIV" in conf
    assert "MASQUERADE" in conf
    assert "[Peer]" in conf
    assert "PublicKey = PHONEPUB" in conf
    assert "AllowedIPs = 10.66.66.2/32" in conf


def test_build_client_conf():
    inbound = SimpleNamespace(
        port=51820, params={"server_public": "SRVPUB"}, address_override=""
    )
    client = SimpleNamespace(extra={"wg_private": "CLIENTPRIV", "wg_ip": "10.66.66.2"})
    conf = build_client_conf(inbound, client, CFG, "")
    assert "PrivateKey = CLIENTPRIV" in conf
    assert "Address = 10.66.66.2/32" in conf
    assert "PublicKey = SRVPUB" in conf
    assert "Endpoint = 203.0.113.10:51820" in conf
    assert "AllowedIPs = 0.0.0.0/0" in conf
    assert "PersistentKeepalive = 25" in conf


def test_parse_dump():
    dump = (
        "IFPUB\tIFPRIV\t51820\toff\n"
        "PEERPUB\t(none)\t203.0.113.5:51820\t10.66.66.2/32\t1699999999\t12345\t67890\toff\n"
    )
    peers = parse_dump(dump)
    assert "PEERPUB" in peers
    entry = peers["PEERPUB"]
    assert entry["rx"] == 12345 and entry["tx"] == 67890
    assert entry["handshake"] == 1699999999
    assert parse_dump("") == {}


def test_wireguard_key_formats():
    import base64

    from smhpanel.keys import x25519_keypair, x25519_keypair_std

    std_priv, std_pub = x25519_keypair_std()
    assert len(std_priv) == 44 and std_priv.endswith("=")
    assert len(std_pub) == 44 and std_pub.endswith("=")
    assert len(base64.b64decode(std_priv)) == 32

    url_priv, _ = x25519_keypair()
    assert "=" not in url_priv and len(url_priv) == 43
