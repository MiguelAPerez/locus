import secrets
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app import db, auth, config

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ApiKeyRequest(BaseModel):
    name: str
    allowed_spaces: list[str] = []
    allowed_collections: list[str] = []


@router.get("/status")
def auth_status():
    return {
        "auth_enabled": config.auth_enabled(),
        "registration_enabled": config.registration_enabled(),
    }


@router.post("/register", status_code=201)
def register(body: RegisterRequest):
    if not config.registration_enabled():
        raise HTTPException(403, "Registration is disabled")
    username = body.username.strip().lower()
    if not username or len(body.password) < 8:
        raise HTTPException(400, "Username required and password must be at least 8 characters")
    try:
        uid = db.create_user(username, auth.hash_password(body.password))
    except ValueError:
        raise HTTPException(409, f"Username '{username}' already taken")
    return {"id": uid, "username": username}


@router.post("/login")
def login(body: LoginRequest):
    user = db.get_user_by_username(body.username.strip().lower())
    if not user or not auth.verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid username or password")
    token = auth.create_jwt(user["id"], user["username"])
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me(current_user: auth.CurrentUser = Depends(auth.get_current_user)):
    return {"id": current_user.id, "username": current_user.username}


@router.get("/keys")
def list_keys(current_user: auth.CurrentUser = Depends(auth.get_current_user)):
    return {"keys": db.list_api_keys(current_user.id)}


@router.post("/keys", status_code=201)
def create_key(body: ApiKeyRequest, current_user: auth.CurrentUser = Depends(auth.get_current_user)):
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
def delete_key(key_id: str, current_user: auth.CurrentUser = Depends(auth.get_current_user)):
    db.delete_api_key(key_id, current_user.id)
