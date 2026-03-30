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
    expires_hours: int | None = None  # None = never expires, 0 invalid, positive = hours until expiry


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


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
    return {
        "id": current_user.id,
        "username": current_user.username,
        "is_admin": current_user.is_admin,
        "is_api_key": current_user.is_api_key,
    }


def _jwt_only(current_user: auth.CurrentUser = Depends(auth.get_current_user), _: None = Depends(_require_auth_enabled)) -> auth.CurrentUser:
    """Reject API key auth on sensitive key-management endpoints."""
    if current_user.is_api_key:
        raise HTTPException(403, "API keys cannot manage other API keys; use a session token")
    return current_user


def _require_admin(current_user: auth.CurrentUser = Depends(auth.get_current_user), _: None = Depends(_require_auth_enabled)) -> auth.CurrentUser:
    if current_user.is_api_key:
        raise HTTPException(403, "API keys cannot perform admin actions; use a session token")
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")
    return current_user


# ── API Keys ──────────────────────────────────────────────────────────────────

@router.get("/keys")
def list_keys(current_user: auth.CurrentUser = Depends(_jwt_only)):
    return {"keys": db.list_api_keys(current_user.id)}


@router.post("/keys", status_code=201)
def create_key(body: ApiKeyRequest, current_user: auth.CurrentUser = Depends(_jwt_only)):
    if body.expires_hours is not None and body.expires_hours <= 0:
        raise HTTPException(400, "expires_hours must be a positive integer or null for no expiry")
    raw_key = f"lcs_{secrets.token_hex(32)}"
    key_hash = auth.hash_api_key(raw_key)
    key_prefix = raw_key[:12]
    expires_at = None
    if body.expires_hours:
        from datetime import datetime, timedelta, timezone
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=body.expires_hours)).isoformat()
    kid = db.create_api_key(
        current_user.id,
        body.name,
        key_hash,
        key_prefix,
        body.allowed_spaces,
        body.allowed_collections,
        expires_at,
    )
    return {"id": kid, "key": raw_key, "key_prefix": key_prefix, "expires_at": expires_at}


@router.delete("/keys/{key_id}", status_code=204)
def delete_key(key_id: str, current_user: auth.CurrentUser = Depends(_jwt_only)):
    db.delete_api_key(key_id, current_user.id)


# ── Password management ───────────────────────────────────────────────────────

@router.post("/change-password", status_code=204)
def change_password(body: ChangePasswordRequest, current_user: auth.CurrentUser = Depends(_jwt_only)):
    user = db.get_user_by_id(current_user.id)
    if not auth.verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    db.update_password(current_user.id, auth.hash_password(body.new_password))


@router.post("/reset-password", status_code=204)
def reset_password(body: ResetPasswordRequest):
    """Exchange a one-time reset token for a new password. No session required."""
    if not config.auth_enabled():
        raise HTTPException(404, "Auth is not enabled")
    user_id = auth.validate_password_reset_token(body.token)
    if not db.get_user_by_id(user_id):
        raise HTTPException(400, "Invalid reset token")
    if len(body.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    db.update_password(user_id, auth.hash_password(body.new_password))


# ── User management (admin only) ──────────────────────────────────────────────

@router.get("/users")
def list_users(admin: auth.CurrentUser = Depends(_require_admin)):
    return {"users": db.list_all_users()}


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, admin: auth.CurrentUser = Depends(_require_admin)):
    if user_id == admin.id:
        raise HTTPException(400, "Cannot delete your own account")
    if user_id == "guest":
        raise HTTPException(400, "Cannot delete the guest user")
    if not db.get_user_by_id(user_id):
        raise HTTPException(404, "User not found")
    db.delete_user(user_id)


@router.post("/users/{user_id}/reset-password")
def admin_reset_password(user_id: str, admin: auth.CurrentUser = Depends(_require_admin)):
    if user_id == "guest":
        raise HTTPException(400, "Cannot reset guest user password")
    if not db.get_user_by_id(user_id):
        raise HTTPException(404, "User not found")
    token = auth.create_password_reset_token(user_id)
    return {"reset_token": token}


@router.post("/users/{user_id}/promote", status_code=204)
def promote_user(user_id: str, admin: auth.CurrentUser = Depends(_require_admin)):
    if user_id == "guest":
        raise HTTPException(400, "Cannot promote guest user")
    if not db.get_user_by_id(user_id):
        raise HTTPException(404, "User not found")
    db.set_admin(user_id, True)


@router.post("/users/{user_id}/demote", status_code=204)
def demote_user(user_id: str, admin: auth.CurrentUser = Depends(_require_admin)):
    if user_id == admin.id:
        raise HTTPException(400, "Cannot demote yourself")
    if not db.get_user_by_id(user_id):
        raise HTTPException(404, "User not found")
    db.set_admin(user_id, False)
