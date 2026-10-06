"""Authentication, CSRF and rate-limit tests."""


def test_health_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["dev_mode"] is True


def test_api_requires_auth(client):
    assert client.get("/api/inbounds").status_code == 401
    assert client.get("/api/clients").status_code == 401
    assert client.post("/api/inbounds", json={}).status_code == 401


def test_login_flow_and_csrf(client):
    bad = client.post(
        "/api/auth/login", json={"username": "admin", "password": "nope"}
    )
    assert bad.status_code == 401

    good = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-password-123"},
    )
    assert good.status_code == 200
    csrf = good.json()["csrf_token"]

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "admin"

    payload = {"protocol": "wireguard", "port": 51899}

    # mutation without CSRF -> 403
    assert client.post("/api/inbounds", json=payload).status_code == 403
    # wrong CSRF -> 403
    assert (
        client.post(
            "/api/inbounds", json=payload, headers={"x-csrf-token": "bad"}
        ).status_code
        == 403
    )
    # correct CSRF -> allowed
    allowed = client.post(
        "/api/inbounds", json=payload, headers={"x-csrf-token": csrf}
    )
    assert allowed.status_code == 200, allowed.text

    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/inbounds").status_code == 401


def test_login_rate_limit(client):
    for _ in range(10):
        response = client.post(
            "/api/auth/login", json={"username": "admin", "password": "wrong"}
        )
        assert response.status_code == 401
    limited = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-password-123"},
    )
    assert limited.status_code == 429
