"""Orchestrates Xray config generation, validation and lifecycle."""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from .helpers import HelperRunner
from .xray_config import build_full_config, build_xray_inbound

log = logging.getLogger(__name__)


class XrayManager:
    def __init__(self, config, session_factory, runner: HelperRunner):
        self.config = config
        self.session_factory = session_factory
        self.runner = runner

    # ----- config ---------------------------------------------------------
    def build_config(self) -> dict:
        from ..models import Inbound

        with self.session_factory() as session:
            rows = session.query(Inbound).order_by(Inbound.id).all()
            xray_inbounds = []
            for row in rows:
                if row.is_wireguard or not row.enabled:
                    continue
                clients = [c for c in row.clients if c.enabled]
                xray_inbounds.append(
                    build_xray_inbound(
                        {
                            "tag": row.tag,
                            "protocol": row.protocol,
                            "port": row.port,
                            "listen": row.listen,
                            "host_override": row.host_override,
                            "params": row.params or {},
                            "clients": [
                                {
                                    "email_tag": c.email_tag,
                                    "credential": c.credential,
                                }
                                for c in clients
                            ],
                        }
                    )
                )
            return build_full_config(xray_inbounds, self.config)

    # ----- lifecycle ------------------------------------------------------
    def apply(self) -> tuple[bool, str]:
        """Regenerate config and reload xray. Returns (ok, message)."""
        try:
            conf = self.build_config()
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("xray config build failed")
            return False, f"config build failed: {exc}"

        text = json.dumps(conf, ensure_ascii=False, indent=2)
        paths = self.config.paths()

        if self.config.is_dev():
            target = Path(paths["xray_config"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            return True, "dev: config written (xray not started)"

        candidate = Path(paths["data_dir"]) / "xray-config.candidate.json"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(text, encoding="utf-8")
        code, out, err = self.runner.run("smhpanel-xray-apply")
        if code != 0:
            return False, (err or out or f"helper exited with {code}").strip()
        return True, "applied"

    def restart(self) -> tuple[bool, str]:
        code, out, err = self.runner.run("smhpanel-service", "restart", "xray")
        return code == 0, ((out or err) or "").strip()

    def version(self) -> str | None:
        binary = self.config.find_xray_binary()
        if not binary:
            return None
        try:
            proc = subprocess.run(
                [binary, "version"], capture_output=True, text=True, timeout=10
            )
            lines = (proc.stdout or "").strip().splitlines()
            return lines[0] if lines else None
        except (OSError, subprocess.SubprocessError):
            return None

    # ----- firewall -------------------------------------------------------
    def open_port(self, port: int, proto: str = "tcp") -> None:
        if self.config.get("firewall.auto_open", True):
            self.runner.run("smhpanel-firewall-open", port, proto)

    def close_port(self, port: int, proto: str = "tcp") -> None:
        if self.config.get("firewall.auto_open", True):
            self.runner.run("smhpanel-firewall-close", port, proto)
