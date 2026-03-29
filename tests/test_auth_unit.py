import pytest
import os
from app import auth, db


@pytest.fixture(autouse=True)
def patch_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "auth.db"))
    db.init_db()


def test_hash_and_verify_password():
    h = auth.hash_password("secret")
    assert auth.verify_password("secret", h)
    assert not auth.verify_password("wrong", h)


def test_hash_api_key():
    key = "lcs_abc123"
    h = auth.hash_api_key(key)
    assert auth.hash_api_key(key) == h  # deterministic (sha256)
    assert h != key


def test_create_and_decode_jwt():
    token = auth.create_jwt("user-id-1", "alice")
    payload = auth.decode_jwt(token)
    assert payload["sub"] == "user-id-1"
    assert payload["username"] == "alice"


def test_decode_invalid_jwt_raises():
    with pytest.raises(Exception):
        auth.decode_jwt("not.a.token")


def test_get_current_user_guest_when_auth_disabled(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    from fastapi.testclient import TestClient
    from fastapi import FastAPI, Depends
    from app.auth import get_current_user, CurrentUser

    app = FastAPI()

    @app.get("/me")
    def me(user: CurrentUser = Depends(get_current_user)):
        return {"username": user.username}

    c = TestClient(app)
    r = c.get("/me")
    assert r.status_code == 200
    assert r.json()["username"] == "guest"


def test_get_current_user_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    from fastapi.testclient import TestClient
    from fastapi import FastAPI, Depends
    from app.auth import get_current_user, CurrentUser

    app = FastAPI()

    @app.get("/me")
    def me(user: CurrentUser = Depends(get_current_user)):
        return {"username": user.username}

    c = TestClient(app, raise_server_exceptions=False)
    r = c.get("/me")
    assert r.status_code == 401
