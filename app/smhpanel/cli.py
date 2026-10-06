"""Command-line interface (used by the installer and admins)."""
from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path

from . import __version__
from .config import (
    AppConfig,
    create_default_config,
    deep_merge,
    default_config_path,
    load_config,
)
from .db import init_db, make_engine, make_session_factory
from .keys import random_password
from .models import Admin, Client, Inbound
from .security import hash_password
from .services.backup import create_backup
from .services.helpers import HelperRunner
from .services.system import snapshot
from .services.tls import generate_self_signed
from .services.wireguard import WireGuardManager, ensure_interface
from .services.xray_manager import XrayManager


def cmd_init(args) -> int:
    path = Path(args.config) if args.config else default_config_path()
    overrides: dict = {
        "panel": {"tls": {"enabled": not args.no_tls}},
        "wireguard": {"enabled": not args.no_wireguard},
    }
    if args.public_host:
        overrides["panel"]["public_host"] = args.public_host
    if args.panel_port:
        overrides["panel"]["port"] = int(args.panel_port)
    if args.wg_port:
        overrides["wireguard"]["port"] = int(args.wg_port)
    if args.wg_subnet:
        overrides["wireguard"]["subnet"] = args.wg_subnet

    if path.exists():
        cfg = load_config(path)
        cfg.data = deep_merge(cfg.data, overrides)
    else:
        cfg = create_default_config(path, overrides)
    if not cfg.get("panel.public_host"):
        cfg.set("panel.public_host", "127.0.0.1")
    cfg.save()

    engine = make_engine(cfg.paths()["db"])
    init_db(engine)
    factory = make_session_factory(engine)

    generated_password = None
    with factory() as session:
        admin = session.query(Admin).filter(Admin.username == args.admin_user).first()
        created_admin = admin is None
        if created_admin:
            generated_password = args.admin_pass or random_password(16)
            session.add(
                Admin(
                    username=args.admin_user,
                    password_hash=hash_password(generated_password),
                )
            )
        if not args.no_wireguard:
            ensure_interface(cfg, session)
        session.commit()

    if cfg.get("panel.tls.enabled"):
        certfile = cfg.get("panel.tls.certfile")
        keyfile = cfg.get("panel.tls.keyfile")
        if not certfile or not Path(certfile).exists():
            host = cfg.get("panel.public_host")
            certs_dir = Path(cfg.paths()["certs"])
            cert_path = certs_dir / f"{host}.crt"
            key_path = certs_dir / f"{host}.key"
            generate_self_signed(host, cert_path, key_path)
            cfg.set("panel.tls.certfile", str(cert_path))
            cfg.set("panel.tls.keyfile", str(key_path))
            cfg.save()

    runner = HelperRunner(cfg)
    manager = XrayManager(cfg, factory, runner)
    wg_manager = WireGuardManager(cfg, factory, runner)
    xray_ok, xray_msg = manager.apply()
    wg_ok, wg_msg = wg_manager.apply()

    scheme = "https" if cfg.get("panel.tls.enabled") else "http"
    print("SMHPANEL_INIT_OK")
    print(f"SMHPANEL_PANEL_URL={scheme}://{cfg.get('panel.public_host')}:{cfg.get('panel.port')}")
    print(f"SMHPANEL_ADMIN_USER={args.admin_user}")
    if created_admin:
        print(f"SMHPANEL_ADMIN_PASSWORD={generated_password}")
    else:
        print("SMHPANEL_ADMIN_PASSWORD=(unchanged)")
    print(f"SMHPANEL_DB={cfg.paths()['db']}")
    print(f"SMHPANEL_XRAY_APPLY={'ok' if xray_ok else 'error'}: {xray_msg}")
    print(f"SMHPANEL_WG_APPLY={'ok' if wg_ok else 'error'}: {wg_msg}")
    return 0


def cmd_status(args) -> int:
    cfg = load_config(args.config)
    engine = make_engine(cfg.paths()["db"])
    init_db(engine)
    factory = make_session_factory(engine)
    runner = HelperRunner(cfg)
    manager = XrayManager(cfg, factory, runner)
    data = snapshot(cfg, runner, factory, manager)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


def cmd_reset_admin_password(args) -> int:
    cfg = load_config(args.config)
    engine = make_engine(cfg.paths()["db"])
    init_db(engine)
    factory = make_session_factory(engine)
    password = args.password or random_password(16)
    with factory() as session:
        admin = session.query(Admin).filter(Admin.username == args.user).first()
        if admin is None:
            print(f"admin '{args.user}' not found")
            return 1
        admin.password_hash = hash_password(password)
        session.commit()
    print(f"SMHPANEL_ADMIN_USER={args.user}")
    print(f"SMHPANEL_ADMIN_PASSWORD={password}")
    return 0


def cmd_backup(args) -> int:
    cfg = load_config(args.config)
    data = create_backup(cfg)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f"backup written: {out} ({len(data)} bytes)")
    return 0


def cmd_restore(args) -> int:
    if not args.yes:
        print("refusing to restore without --yes (this overwrites live data)")
        return 1
    cfg = load_config(args.config)
    paths = cfg.paths()
    mapping = {
        "smhpanel.db": Path(paths["db"]),
        "config.json": Path(cfg.path) if cfg.path else None,
        "xray-config.json": Path(paths["xray_config"]),
    }
    with tarfile.open(args.infile, "r:gz") as tar:
        for member in tar.getmembers():
            if member.name in mapping and mapping[member.name] is not None:
                target = mapping[member.name]
                target.parent.mkdir(parents=True, exist_ok=True)
                source = tar.extractfile(member)
                if source is not None:
                    target.write_bytes(source.read())
                    print(f"restored: {target}")
    print("restore complete; restart the panel service to pick up changes")
    return 0


def cmd_version(_args) -> int:
    print(f"SMH Panel {__version__}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="smhpanel", description="SMH Panel CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="initialise config, database and admin user")
    p_init.add_argument("--config", default=None)
    p_init.add_argument("--admin-user", default="admin")
    p_init.add_argument("--admin-pass", default=None)
    p_init.add_argument("--public-host", default=None)
    p_init.add_argument("--panel-port", default=None)
    p_init.add_argument("--no-tls", action="store_true")
    p_init.add_argument("--no-wireguard", action="store_true")
    p_init.add_argument("--wg-port", default=None)
    p_init.add_argument("--wg-subnet", default=None)
    p_init.add_argument("--non-interactive", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_status = sub.add_parser("status", help="print a status snapshot")
    p_status.add_argument("--config", default=None)
    p_status.set_defaults(func=cmd_status)

    p_reset = sub.add_parser("reset-admin-password")
    p_reset.add_argument("--config", default=None)
    p_reset.add_argument("--user", default="admin")
    p_reset.add_argument("--password", default=None)
    p_reset.set_defaults(func=cmd_reset_admin_password)

    p_backup = sub.add_parser("backup")
    p_backup.add_argument("--config", default=None)
    p_backup.add_argument("--out", required=True)
    p_backup.set_defaults(func=cmd_backup)

    p_restore = sub.add_parser("restore")
    p_restore.add_argument("--config", default=None)
    p_restore.add_argument("--in", dest="infile", required=True)
    p_restore.add_argument("--yes", action="store_true")
    p_restore.set_defaults(func=cmd_restore)

    p_version = sub.add_parser("version")
    p_version.set_defaults(func=cmd_version)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
