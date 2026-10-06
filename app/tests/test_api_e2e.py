"""End-to-end API tests against the dev-mode app."""
from __future__ import annotations

import base64
import json
from pathlib import Path


def _login(client) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-password-123"},
    )
    assert response.status_code == 200, response.text
    client.headers.update({"x-csrf-token": response.json()["csrf_token"]})


def test_full_flow(app_env, client):
    cfg, _factory = app_env
    _login(client)

    # 1. create VLESS+Reality inbound
    response = client.post(
        "/api/inbounds",
        json={"protocol": "vless", "port": 2443, "security": "reality", "network": "tcp"},
    )
    assert response.status_code == 200, response.text
    inbound = response.json()
    assert inbound["tag"] == "vless-2443"
    assert inbound["params"]["reality_public"]
    assert "reality_private" not in inbound["params"]
    assert inbound["apply_error"] is None
    inbound_id = inbound["id"]

    # xray config is written in dev mode
    xray_conf = json.loads(
        Path(cfg.paths()["xray_config"]).read_text(encoding="utf-8")
    )
    assert "vless-2443" in [i["tag"] for i in xray_conf["inbounds"]]

    # 2. reality is rejected for vmess
    response = client.post(
        "/api/inbounds",
        json={"protocol": "vmess", "port": 8081, "security": "reality"},
    )
    assert response.status_code == 400

    # 3. create VMess+WS inbound
    response = client.post(
        "/api/inbounds", json={"protocol": "vmess", "port": 8080, "network": "ws"}
    )
    assert response.status_code == 200, response.text
    ws_id = response.json()["id"]

    # 4. add clients
    response = client.post(
        "/api/clients",
        json={"inbound_id": inbound_id, "name": "Alice", "quota_gb": 50},
    )
    assert response.status_code == 200, response.text
    alice = response.json()
    assert alice["credential"] and alice["sub_token"]
    alice_id = alice["id"]

    response = client.post(
        "/api/clients", json={"inbound_id": ws_id, "name": "Bob"}
    )
    assert response.status_code == 200
    bob_id = response.json()["id"]

    # 5. links
    response = client.get(f"/api/clients/{alice_id}/links")
    assert response.status_code == 200
    links = response.json()
    assert links["links"][0].startswith("vless://")
    assert "/sub/" in links["subscription_url"]

    # 6. subscription (public, no auth)
    sub_token = alice["sub_token"]
    response = client.get(f"/sub/{sub_token}")
    assert response.status_code == 200
    decoded = base64.b64decode(response.text).decode("utf-8")
    assert decoded == links["links"][0]
    raw = client.get(f"/sub/{sub_token}?format=raw")
    assert raw.text.strip() == links["links"][0]
    assert client.get("/sub/does-not-exist").status_code == 404

    # 7. QR code
    response = client.get(f"/api/clients/{alice_id}/qr.png")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content[:4] == b"\x89PNG"

    # 8. settings
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert response.json()["panel"]["public_host"] == "203.0.113.10"
    response = client.patch(
        "/api/settings", json={"patch": {"panel": {"title": "Renamed"}}}
    )
    assert response.status_code == 200
    assert "panel.title" in response.json()["applied"]
    assert client.get("/api/settings").json()["panel"]["title"] == "Renamed"
    # unknown setting is rejected
    assert (
        client.patch(
            "/api/settings", json={"patch": {"panel": {"hax": "x"}}}
        ).status_code
        == 400
    )

    # 9. system status + logs
    response = client.get("/api/system/status")
    assert response.status_code == 200
    assert response.json()["dev_mode"] is True
    assert "xray" in response.json()["services"]
    assert client.get("/api/system/logs").status_code == 200

    # 10. disable / enable client
    response = client.post(f"/api/clients/{alice_id}/enable", json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    response = client.post(f"/api/clients/{alice_id}/enable", json={"enabled": True})
    assert response.status_code == 200
    assert response.json()["enabled"] is True

    # 11. delete
    assert client.delete(f"/api/clients/{bob_id}").status_code == 200
    assert client.delete(f"/api/inbounds/{ws_id}").status_code == 200

    # 12. WireGuard flow
    response = client.post(
        "/api/inbounds", json={"protocol": "wireguard", "port": 51821}
    )
    assert response.status_code == 200, response.text
    wg_id = response.json()["id"]
    response = client.post(
        "/api/clients", json={"inbound_id": wg_id, "name": "Phone"}
    )
    assert response.status_code == 200, response.text
    phone = response.json()
    assert phone["extra"].get("wg_ip") == "10.66.66.2"
    assert "wg_private" not in phone["extra"]

    wg_links = client.get(f"/api/clients/{phone['id']}/links").json()
    assert wg_links["wg_conf"] and "Endpoint" in wg_links["wg_conf"]
    qr = client.get(f"/api/clients/{phone['id']}/qr.png?target=link")
    assert qr.status_code == 200 and qr.content[:4] == b"\x89PNG"

    # 13. audit log recorded actions
    actions = [row["action"] for row in client.get("/api/system/logs").json()]
    assert "inbound.create" in actions
    assert "client.create" in actions
    assert "auth.login" in actions
