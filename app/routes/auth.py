import re
import secrets
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app import db, auth, config

_USERNAME_RE = re.compile(r'^[a-z0-9_-]{1,32}$')

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ApiKeyRequest(BaseModel):
    name: str
    allowed_spaces: list[str] = Field(default_factory=list)
    allowed_collections: list[str] = Field(default_factory=list)


def _require_auth_enabled():
    if not config.auth_enabled():
        raise HTTPException(404, "Auth is not enabled")


@router.get("/status")
def auth_status():
    return {
        "auth_enabled": config.auth_enabled(),
        "registration_enabled": config.registration_enabled(),
    }


@router.post("/register", status_code=201)
def register(body: RegisterRequest, _: None = Depends(_require_auth_enabled)):
    if not config.registration_enabled():
        raise HTTPException(403, "Registration is disabled")
    username = body.username.strip().lower()
    if not _USERNAME_RE.match(username):
        raise HTTPException(400, "Username must be 1-32 characters: letters, digits, _ or -")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    try:
        uid = db.create_user(username, auth.hash_password(body.password))
    except ValueError:
        raise HTTPException(409, f"Username '{username}' already taken")
    return {"id": uid, "username": username}


@router.post("/login")
def login(body: LoginRequest, _: None = Depends(_require_auth_enabled)):
    user = db.get_user_by_username(body.username.strip().lower())
    if not user or not auth.verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid username or password")
    token = auth.create_jwt(user["id"], user["username"])
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me(current_user: auth.CurrentUser = Depends(auth.get_current_user), _: None = Depends(_require_auth_enabled)):
    return {"id": current_user.id, "username": current_user.username}


def _jwt_only(current_user: auth.CurrentUser = Depends(auth.get_current_user), _: None = Depends(_require_auth_enabled)) -> auth.CurrentUser:
    """Reject API key auth on sensitive key-management endpoints."""
    if current_user.is_api_key:
        raise HTTPException(403, "API keys cannot manage other API keys; use a session token")
    return current_user


@router.get("/keys")
def list_keys(current_user: auth.CurrentUser = Depends(_jwt_only)):
    return {"keys": db.list_api_keys(current_user.id)}


@router.post("/keys", status_code=201)
def create_key(body: ApiKeyRequest, current_user: auth.CurrentUser = Depends(_jwt_only)):
    raw_key = f"lcs_{secrets.token_hex(32)}"
    key_hash = auth.hash_api_key(raw_key)
    key_prefix = raw_key[:12]
    kid = db.create_api_key(
        current_user.id,
        body.name,
        key_hash,
        key_prefix,
        body.allowed_spaces,
        body.allowed_collections,
    )
    return {"id": kid, "key": raw_key, "key_prefix": key_prefix}


@router.delete("/keys/{key_id}", status_code=204)
def delete_key(key_id: str, current_user: auth.CurrentUser = Depends(_jwt_only)):
    db.delete_api_key(key_id, current_user.id)
