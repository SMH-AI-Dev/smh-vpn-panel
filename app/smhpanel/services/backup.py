"""Backup archive creation (tar.gz bytes)."""
from __future__ import annotations

import io
import tarfile
from pathlib import Path


def create_backup(config) -> bytes:
    paths = config.paths()
    buf = io.BytesIO()

    with tarfile.open(fileobj=buf, mode="w:gz") as tar:

        def add(path: Path, arcname: str) -> None:
            if path.exists() and path.is_file():
                tar.add(str(path), arcname=arcname)

        add(Path(paths["db"]), "smhpanel.db")
        if config.path:
            add(Path(config.path), "config.json")
        add(Path(paths["xray_config"]), "xray-config.json")

        certs = Path(paths["certs"])
        if certs.exists():
            for entry in certs.iterdir():
                if entry.is_file():
                    tar.add(str(entry), arcname=f"certs/{entry.name}")

        iface = config.get("wireguard.iface", "wg0")
        add(Path("/etc/wireguard") / f"{iface}.conf", f"wireguard/{iface}.conf")

    return buf.getvalue()
