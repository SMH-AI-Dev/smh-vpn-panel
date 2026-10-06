"""Server/system status and detailed machine specifications."""
from __future__ import annotations

import os
import platform
import socket
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


def _os_pretty_name() -> str:
    if os.name == "posix":
        try:
            with open("/etc/os-release", "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass
    return f"{platform.system()} {platform.release()}".strip()


def _cpu_model() -> str:
    if os.name == "posix":
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    lowered = line.lower()
                    if lowered.startswith("model name") or lowered.startswith("hardware"):
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return (platform.processor() or platform.machine() or "unknown").strip()


def _cpu_freq_mhz() -> int | None:
    try:
        freq = psutil.cpu_freq()
        return int(freq.current) if freq and freq.current else None
    except Exception:
        return None


def _load_avg() -> list[float] | None:
    try:
        return [round(value, 2) for value in os.getloadavg()]
    except (OSError, AttributeError):
        return None


def snapshot(config, runner, session_factory, manager) -> dict:
    from ..models import Client, Inbound

    services = {"panel": "active", "xray": service_state(runner, "xray")}
    if config.get("wireguard.enabled", True):
        services["wg"] = service_state(runner, "wg")
    else:
        services["wg"] = "disabled"

    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage(os.path.abspath(os.sep))

    specs = {
        "hostname": socket.gethostname(),
        "os": _os_pretty_name(),
        "kernel": platform.release(),
        "arch": platform.machine(),
        "cpu_model": _cpu_model(),
        "cores_physical": psutil.cpu_count(logical=False),
        "cores_logical": psutil.cpu_count(logical=True),
        "cpu_freq_mhz": _cpu_freq_mhz(),
        "load_avg": _load_avg(),
    }

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
        "mem": {
            "total": mem.total,
            "used": mem.used,
            "free": mem.free,
            "available": mem.available,
            "percent": mem.percent,
        },
        "swap": {
            "total": swap.total,
            "used": swap.used,
            "free": swap.free,
            "percent": swap.percent,
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
        },
        "uptime_sec": int(time.time() - psutil.boot_time()),
        "xray_version": manager.version(),
        "totals": {"up": up, "down": down},
        "counts": counts,
        "specs": specs,
        "dev_mode": config.is_dev(),
    }
