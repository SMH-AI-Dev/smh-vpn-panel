"""Configuration loading/saving and path resolution for SMH Panel."""
from __future__ import annotations

import json
import os
import secrets
from copy import deepcopy
from pathlib import Path

DEFAULT_CONFIG: dict = {
    "panel": {
        "title": "SMH Panel",
        "port": 2053,
        "public_host": "127.0.0.1",
        "tls": {"enabled": True, "certfile": "", "keyfile": ""},
    },
    "subscription": {"host": "", "port": 0},
    "firewall": {"auto_open": True},
    "routing": {"block_port25": True, "block_private": True, "block_bittorrent": False},
    "wireguard": {
        "enabled": True,
        "iface": "wg0",
        "port": 51820,
        "subnet": "10.66.66.0/24",
        "mtu": 1420,
        "dns": "1.1.1.1",
        "wan_iface": "eth0",
    },
    "paths": {
        "data_dir": "",
        "db": "",
        "xray_config": "",
        "xray_binary": "",
        "certs": "",
        "helpers": "",
        "stats_api": "127.0.0.1:10085",
    },
    "runtime": {"dev_mode": "auto", "workers": True},
    "security": {"secret_key": "", "session_ttl_hours": 24},
}

PROD_PATHS = {
    "data_dir": "/var/lib/smhpanel",
    "db": "/var/lib/smhpanel/smhpanel.db",
    "xray_config": "/usr/local/etc/xray/config.json",
    "xray_binary": "/usr/local/bin/xray",
    "certs": "/etc/smhpanel/certs",
    "helpers": "/usr/local/sbin",
    "stats_api": "127.0.0.1:10085",
}


def deep_merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


class AppConfig:
    def __init__(self, data: dict, path: Path | None = None):
        self.data = deep_merge(DEFAULT_CONFIG, data or {})
        self.path = Path(path) if path else None

    # ----- generic access -------------------------------------------------
    def get(self, dotted: str, default=None):
        node = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value) -> None:
        parts = dotted.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    # ----- runtime mode / paths ------------------------------------------
    def is_dev(self) -> bool:
        """True when the app runs without real Linux integration (no helpers)."""
        flag = self.get("runtime.dev_mode", "auto")
        if flag is True:
            return True
        if flag is False:
            return False
        if os.name != "posix":
            return True
        helper = Path(PROD_PATHS["helpers"]) / "smhpanel-xray-apply"
        return not helper.exists()

    def paths(self) -> dict:
        stored = dict(self.data.get("paths") or {})
        if self.is_dev():
            base = Path.cwd() / "dev-data"
            defaults = {
                "data_dir": str(base),
                "db": str(base / "smhpanel.db"),
                "xray_config": str(base / "xray-config.json"),
                "xray_binary": "",
                "certs": str(base / "certs"),
                "helpers": str(base / "helpers"),
                "stats_api": "127.0.0.1:10085",
            }
        else:
            defaults = dict(PROD_PATHS)
        return {key: (stored.get(key) or default) for key, default in defaults.items()}

    def find_xray_binary(self) -> str | None:
        from shutil import which

        candidate = self.paths().get("xray_binary") or ""
        if candidate and Path(candidate).exists():
            return candidate
        return which("xray")

    # ----- persistence ----------------------------------------------------
    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def secret(self) -> str:
        key = self.get("security.secret_key") or ""
        if not key:
            key = secrets.token_urlsafe(48)
            self.set("security.secret_key", key)
        return key


def default_config_path() -> Path:
    env = os.environ.get("SMHPANEL_CONFIG")
    if env:
        return Path(env)
    if os.name == "posix":
        prod = Path("/etc/smhpanel/config.json")
        if prod.exists():
            return prod
    return Path("dev-config.json")


def load_config(path: str | Path | None = None) -> AppConfig:
    resolved = Path(path) if path else default_config_path()
    data: dict = {}
    if resolved.exists():
        data = json.loads(resolved.read_text(encoding="utf-8"))
    cfg = AppConfig(data, resolved)
    if not cfg.get("security.secret_key"):
        cfg.set("security.secret_key", secrets.token_urlsafe(48))
    return cfg


def create_default_config(path: str | Path, overrides: dict | None = None) -> AppConfig:
    cfg = AppConfig(deep_merge(DEFAULT_CONFIG, overrides or {}), Path(path))
    cfg.set("security.secret_key", secrets.token_urlsafe(48))
    return cfg
