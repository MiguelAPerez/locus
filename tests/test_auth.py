import pytest
from fastapi.testclient import TestClient
from app import db


@pytest.fixture(autouse=True)
def enable_auth(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("REGISTRATION_ENABLED", "true")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")


@pytest.fixture
def auth_client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def _register(client, username="alice", password="password123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def _login(client, username="alice", password="password123"):
    return client.post("/auth/login", json={"username": username, "password": password})


def _token(client, username="alice"):
    _register(client, username)
    r = _login(client, username)
    return r.json()["access_token"]


def test_register_success(auth_client):
    r = _register(auth_client)
    assert r.status_code == 201
    assert r.json()["username"] == "alice"


def test_register_duplicate_fails(auth_client):
    _register(auth_client)
    r = _register(auth_client)
    assert r.status_code == 409


def test_register_blocked_when_disabled(monkeypatch, auth_client):
    monkeypatch.setenv("REGISTRATION_ENABLED", "false")
    r = _register(auth_client)
    assert r.status_code == 403


def test_login_success(auth_client):
    _register(auth_client)
    r = _login(auth_client)
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_wrong_password(auth_client):
    _register(auth_client)
    r = _login(auth_client, password="wrong")
    assert r.status_code == 401


def test_me_returns_current_user(auth_client):
    token = _token(auth_client)
    r = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


def test_me_requires_auth(auth_client):
    r = auth_client.get("/auth/me")
    assert r.status_code == 401


def test_create_and_list_api_key(auth_client):
    token = _token(auth_client)
    headers = {"Authorization": f"Bearer {token}"}
    r = auth_client.post(
        "/auth/keys",
        json={"name": "my-key", "allowed_spaces": [], "allowed_collections": []},
        headers=headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["key"].startswith("lcs_")
    assert "id" in data

    r2 = auth_client.get("/auth/keys", headers=headers)
    assert r2.status_code == 200
    keys = r2.json()["keys"]
    assert any(k["name"] == "my-key" for k in keys)
    assert not any("key_hash" in k for k in keys)


def test_delete_api_key(auth_client):
    token = _token(auth_client)
    headers = {"Authorization": f"Bearer {token}"}
    r = auth_client.post(
        "/auth/keys",
        json={"name": "my-key", "allowed_spaces": [], "allowed_collections": []},
        headers=headers,
    )
    kid = r.json()["id"]
    r2 = auth_client.delete(f"/auth/keys/{kid}", headers=headers)
    assert r2.status_code == 204


def test_api_key_authenticates(auth_client):
    token = _token(auth_client)
    headers = {"Authorization": f"Bearer {token}"}
    r = auth_client.post(
        "/auth/keys",
        json={"name": "k", "allowed_spaces": [], "allowed_collections": []},
        headers=headers,
    )
    raw_key = r.json()["key"]
    r2 = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {raw_key}"})
    assert r2.status_code == 200
    assert r2.json()["username"] == "alice"


def test_space_isolated_between_users(auth_client):
    token_a = _token(auth_client, "alice")
    token_b = _token(auth_client, "bob")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    r = auth_client.post("/spaces", json={"name": "private"}, headers=headers_a)
    assert r.status_code == 201

    r2 = auth_client.get("/spaces", headers=headers_b)
    assert "private" not in r2.json()["spaces"]


def test_cannot_access_other_users_space(auth_client):
    token_a = _token(auth_client, "alice")
    token_b = _token(auth_client, "bob")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    auth_client.post("/spaces", json={"name": "secret"}, headers=headers_a)

    r = auth_client.get("/spaces/secret/documents", headers=headers_b)
    assert r.status_code == 403


def test_api_key_space_scope_enforced(auth_client):
    token = _token(auth_client)
    headers = {"Authorization": f"Bearer {token}"}

    auth_client.post("/spaces", json={"name": "allowed"}, headers=headers)
    auth_client.post("/spaces", json={"name": "blocked"}, headers=headers)

    r = auth_client.post(
        "/auth/keys",
        json={"name": "scoped", "allowed_spaces": ["allowed"], "allowed_collections": []},
        headers=headers,
    )
    raw_key = r.json()["key"]
    key_headers = {"Authorization": f"Bearer {raw_key}"}

    r2 = auth_client.get("/spaces/allowed/documents", headers=key_headers)
    assert r2.status_code == 200

    r3 = auth_client.get("/spaces/blocked/documents", headers=key_headers)
    assert r3.status_code == 403
