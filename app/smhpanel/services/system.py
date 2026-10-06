"""Server/system status snapshot."""
from __future__ import annotations

import os
import time

import psutil


def service_state(runner, name: str) -> str:
    code, out, err = runner.run("smhpanel-service", "status", name)
    text = ((out or "") + "\n" + (err or "")).strip().lower()
    first = text.splitlines()[0].strip() if text else ""
    if first.startswith("active"):
        return "active"
    if first in ("inactive", "failed", "dead", "unknown") or first == "":
        return "inactive" if first != "unknown" else "unknown"
    return "unknown"


def snapshot(config, runner, session_factory, manager) -> dict:
    from ..models import Client, Inbound

    services = {"panel": "active", "xray": service_state(runner, "xray")}
    if config.get("wireguard.enabled", True):
        services["wg"] = service_state(runner, "wg")
    else:
        services["wg"] = "disabled"

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(os.path.abspath(os.sep))

    with session_factory() as session:
        up = sum((c.up_bytes or 0) for c in session.query(Client).all())
        down = sum((c.down_bytes or 0) for c in session.query(Client).all())
        counts = {
            "inbounds": session.query(Inbound).count(),
            "clients": session.query(Client).count(),
            "active_clients": session.query(Client)
            .filter(Client.enabled.is_(True))
            .count(),
        }

    return {
        "services": services,
        "cpu_percent": psutil.cpu_percent(interval=None),
        "mem": {"total": mem.total, "used": mem.used, "percent": mem.percent},
        "disk": {"total": disk.total, "used": disk.used, "percent": disk.percent},
        "uptime_sec": int(time.time() - psutil.boot_time()),
        "xray_version": manager.version(),
        "totals": {"up": up, "down": down},
        "counts": counts,
        "dev_mode": config.is_dev(),
    }
