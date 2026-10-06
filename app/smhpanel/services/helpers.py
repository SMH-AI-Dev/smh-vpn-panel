"""Wrappers around privileged helper scripts (production) with dev simulation."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

HELPER_NAMES = (
    "smhpanel-firewall-open",
    "smhpanel-firewall-close",
    "smhpanel-firewall-status",
    "smhpanel-xray-apply",
    "smhpanel-wg-apply",
    "smhpanel-wg-show",
    "smhpanel-service",
    "smhpanel-cert-issue",
    "smhpanel-cert-renew",
)


class HelperRunner:
    """Runs root helper scripts via sudo; simulates them in dev mode."""

    def __init__(self, config):
        self.config = config
        self.dev = config.is_dev()
        self.calls: list[tuple] = []
        self.dev_services = {"xray": "inactive", "wg": "inactive", "smhpanel": "active"}

    def helper_path(self, name: str) -> Path:
        return Path(self.config.paths()["helpers"]) / name

    def run(
        self,
        name: str,
        *args,
        input_text: str | None = None,
        timeout: int = 120,
    ) -> tuple[int, str, str]:
        """Returns (returncode, stdout, stderr)."""
        if name not in HELPER_NAMES:
            raise ValueError(f"unknown helper: {name}")
        self.calls.append((name, args))
        if self.dev:
            return self._simulate(name, args)
        cmd = ["sudo", "-n", str(self.helper_path(name)), *[str(a) for a in args]]
        try:
            proc = subprocess.run(
                cmd,
                input=input_text,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
            return 127, "", str(exc)

    def _simulate(self, name: str, args: tuple) -> tuple[int, str, str]:
        if name == "smhpanel-firewall-status":
            return 0, "Status: active\n", ""
        if name == "smhpanel-wg-show":
            return 0, "", ""
        if name == "smhpanel-service":
            action = args[0] if args else "status"
            service = args[1] if len(args) > 1 else "xray"
            if action == "status":
                return 0, self.dev_services.get(service, "unknown") + "\n", ""
            if action in ("start", "restart"):
                self.dev_services[service] = "active"
            elif action == "stop":
                self.dev_services[service] = "inactive"
            return 0, "ok (dev)\n", ""
        return 0, "ok (dev)\n", ""
