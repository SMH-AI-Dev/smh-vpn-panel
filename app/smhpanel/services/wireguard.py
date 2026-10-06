"""WireGuard interface/peer management: config generation and helper calls."""
from __future__ import annotations

import ipaddress
import logging
from pathlib import Path

from ..keys import x25519_keypair

log = logging.getLogger(__name__)


def subnet_network(cfg) -> ipaddress.IPv4Network:
    return ipaddress.ip_network(
        cfg.get("wireguard.subnet", "10.66.66.0/24"), strict=False
    )


def server_address(cfg) -> str:
    net = subnet_network(cfg)
    return f"{net.network_address + 1}/{net.prefixlen}"


def allocate_ip(cfg, used: set[str]) -> str:
    net = subnet_network(cfg)
    reserved = {str(net.network_address + 1)}
    for subnet_host in net.hosts():
        candidate = str(subnet_host)
        if candidate in reserved or candidate in used:
            continue
        return candidate
    raise RuntimeError("WireGuard subnet exhausted")


def _iface(cfg) -> str:
    return cfg.get("wireguard.iface", "wg0")


def build_server_conf(inbound, clients: list[dict], cfg) -> str:
    params = inbound.params or {}
    iface = _iface(cfg)
    wan = cfg.get("wireguard.wan_iface", "eth0")

    lines = [
        "[Interface]",
        f"Address = {params.get('server_address') or server_address(cfg)}",
        f"ListenPort = {inbound.port}",
        f"PrivateKey = {params.get('server_private', '')}",
    ]
    mtu = cfg.get("wireguard.mtu")
    if mtu:
        lines.append(f"MTU = {mtu}")
    lines += [
        f"PostUp = iptables -I FORWARD -i {iface} -j ACCEPT",
        f"PostUp = iptables -t nat -A POSTROUTING -o {wan} -j MASQUERADE",
        f"PostDown = iptables -D FORWARD -i {iface} -j ACCEPT",
        f"PostDown = iptables -t nat -D POSTROUTING -o {wan} -j MASQUERADE",
    ]

    for client in clients:
        extra = client.get("extra") or {}
        lines += [
            "",
            f"# {client.get('name', '')}",
            "[Peer]",
            f"PublicKey = {extra.get('wg_public', '')}",
            f"AllowedIPs = {extra.get('wg_ip', '')}/32",
        ]
    return "\n".join(lines) + "\n"


def build_client_conf(inbound, client, cfg, server_public: str) -> str:
    params = inbound.params or {}
    extra = client.extra or {}
    host = inbound.address_override or (cfg.get("panel.public_host") or "127.0.0.1")
    dns = cfg.get("wireguard.dns") or "1.1.1.1"
    mtu = cfg.get("wireguard.mtu")

    lines = [
        "[Interface]",
        f"PrivateKey = {extra.get('wg_private', '')}",
        f"Address = {extra.get('wg_ip', '')}/32",
        f"DNS = {dns}",
    ]
    if mtu:
        lines.append(f"MTU = {mtu}")
    lines += [
        "",
        "[Peer]",
        f"PublicKey = {params.get('server_public', server_public)}",
        f"Endpoint = {host}:{inbound.port}",
        "AllowedIPs = 0.0.0.0/0",
        "PersistentKeepalive = 25",
    ]
    return "\n".join(lines) + "\n"


def parse_dump(text: str) -> dict[str, dict]:
    """Parse `wg show <if> dump` output (first line = interface)."""
    peers: dict[str, dict] = {}
    lines = [line for line in (text or "").splitlines() if line.strip()]
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 8:
            continue
        peers[parts[0]] = {
            "endpoint": parts[2],
            "allowed_ips": parts[3],
            "handshake": int(parts[4] or 0),
            "rx": int(parts[5] or 0),
            "tx": int(parts[6] or 0),
        }
    return peers


class WireGuardManager:
    def __init__(self, config, session_factory, runner):
        self.config = config
        self.session_factory = session_factory
        self.runner = runner

    def interface(self, session):
        from ..models import Inbound

        return session.query(Inbound).filter(Inbound.is_wireguard.is_(True)).first()

    def apply(self) -> tuple[bool, str]:
        if not self.config.get("wireguard.enabled", True):
            return True, "wireguard disabled"
        from ..models import Inbound

        with self.session_factory() as session:
            row = self.interface(session)
            if row is None:
                return True, "no wireguard interface"
            clients = [
                {"name": c.name, "extra": c.extra or {}}
                for c in row.clients
                if c.enabled
            ]
            content = build_server_conf(row, clients, self.config)

        iface = _iface(self.config)
        paths = self.config.paths()
        if self.config.is_dev():
            target = Path(paths["data_dir"]) / f"wg-{iface}.conf"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return True, "dev: wireguard config written"
        candidate = Path(paths["data_dir"]) / f"wg-{iface}.candidate.conf"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(content, encoding="utf-8")
        code, out, err = self.runner.run("smhpanel-wg-apply")
        if code != 0:
            return False, (err or out or f"helper exited with {code}").strip()
        return True, "applied"

    def show(self) -> dict[str, dict]:
        code, out, _err = self.runner.run("smhpanel-wg-show")
        if code != 0:
            return {}
        return parse_dump(out)


def ensure_interface(config, session):
    """Create the WireGuard inbound row + server keys if missing. Returns row."""
    from ..models import Inbound

    row = (
        session.query(Inbound).filter(Inbound.is_wireguard.is_(True)).first()
    )
    if row is not None:
        return row
    private, public = x25519_keypair()
    row = Inbound(
        tag="wireguard",
        protocol="wireguard",
        port=int(config.get("wireguard.port", 51820)),
        listen="0.0.0.0",
        enabled=True,
        is_wireguard=True,
        params={
            "iface": _iface(config),
            "server_private": private,
            "server_public": public,
            "server_address": server_address(config),
        },
    )
    session.add(row)
    session.commit()
    return row
