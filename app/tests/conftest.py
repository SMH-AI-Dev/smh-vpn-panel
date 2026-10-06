"""Shared pytest fixtures."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

os.environ["SMHPANEL_NO_WORKERS"] = "1"

from smhpanel.config import AppConfig  # noqa: E402
from smhpanel.db import init_db, make_engine, make_session_factory  # noqa: E402
from smhpanel.models import Admin  # noqa: E402
from smhpanel.security import hash_password  # noqa: E402


@pytest.fixture()
def app_env(tmp_path):
    cfg = AppConfig(
        {
            "panel": {
                "title": "Test Panel",
                "port": 2099,
                "public_host": "203.0.113.10",
                "tls": {"enabled": False},
            },
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
                "data_dir": str(tmp_path / "data"),
                "db": str(tmp_path / "data" / "test.db"),
                "xray_config": str(tmp_path / "data" / "xray.json"),
                "xray_binary": "",
                "certs": str(tmp_path / "data" / "certs"),
                "helpers": str(tmp_path / "data" / "helpers"),
            },
            "runtime": {"dev_mode": True, "workers": False},
            "security": {"secret_key": "test-secret-key-0123456789abcdef0123456789", "session_ttl_hours": 24},
        }
    )

    engine = make_engine(cfg.paths()["db"])
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        session.add(
            Admin(
                username="admin",
                password_hash=hash_password("test-password-123"),
            )
        )
        session.commit()
    return cfg, factory


@pytest.fixture()
def client(app_env):
    from fastapi.testclient import TestClient

    from smhpanel.main import create_app

    cfg, _factory = app_env
    app = create_app(cfg)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_client(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-password-123"},
    )
    assert response.status_code == 200, response.text
    csrf = response.json()["csrf_token"]
    client.headers.update({"x-csrf-token": csrf})
    return client
