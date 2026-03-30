import os
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Request, HTTPException

from . import db, config

def _secret() -> str:
    secret = os.getenv("SECRET_KEY", "")
    if not secret:
        if config.auth_enabled():
            raise RuntimeError("SECRET_KEY env var must be set when AUTH_ENABLED=true")
        return "dev-secret-not-used-when-auth-disabled"
    return secret


@dataclass
class CurrentUser:
    id: str
    username: str
    allowed_spaces: list[str] = field(default_factory=list)
    allowed_collections: list[str] = field(default_factory=list)
    is_api_key: bool = False
    is_admin: bool = False


GUEST = CurrentUser(id="guest", username="guest")


# ── Crypto helpers ────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_jwt(user_id: str, username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=config.session_hours())
    payload = {"sub": user_id, "username": username, "exp": exp}
    return jwt.encode(payload, _secret(), algorithm="HS256")


def create_password_reset_token(user_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=15)
    payload = {"sub": user_id, "scope": "pwd_reset", "exp": exp}
    return jwt.encode(payload, _secret(), algorithm="HS256")


def validate_password_reset_token(token: str) -> str:
    """Returns user_id or raises HTTPException."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Reset token has expired")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    if payload.get("scope") != "pwd_reset":
        raise HTTPException(status_code=400, detail="Invalid reset token")
    return payload["sub"]


def decode_jwt(token: str) -> dict:
    return jwt.decode(token, _secret(), algorithms=["HS256"])


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def get_current_user(request: Request) -> CurrentUser:
    if not config.auth_enabled():
        return GUEST

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header[len("Bearer "):]

    if token.startswith("lcs_"):
        return _validate_api_key(token)

    return _validate_jwt(token)


def _validate_jwt(token: str) -> CurrentUser:
    try:
        payload = decode_jwt(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return CurrentUser(id=user["id"], username=user["username"], is_admin=bool(user.get("is_admin")))


def _validate_api_key(raw_key: str) -> CurrentUser:
    key_hash = hash_api_key(raw_key)
    key_row = db.get_api_key_by_hash(key_hash)
    if not key_row:
        raise HTTPException(status_code=401, detail="Invalid API key")

    user = db.get_user_by_id(key_row["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return CurrentUser(
        id=user["id"],
        username=user["username"],
        allowed_spaces=key_row["allowed_spaces"],
        allowed_collections=key_row["allowed_collections"],
        is_api_key=True,
    )
