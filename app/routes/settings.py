from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from collections import deque

from app import config
from app.auth import get_current_user, CurrentUser

router = APIRouter(tags=["settings"])

_request_log: deque = deque(maxlen=200)
_log_seq: int = 0


class SettingsUpdate(BaseModel):
    ollama_url: Optional[str] = None
    embed_model: Optional[str] = None


@router.get("/settings")
def get_settings(_: CurrentUser = Depends(get_current_user)):
    return config.get_settings()


@router.post("/settings")
def update_settings(body: SettingsUpdate, user: CurrentUser = Depends(get_current_user)):
    if user.is_api_key:
        raise HTTPException(403, "API keys cannot modify settings; use a session token")
    current = config.get_settings()
    url = body.ollama_url if body.ollama_url is not None and not current["ollama_url"]["readonly"] else None
    model = body.embed_model if body.embed_model is not None and not current["embed_model"]["readonly"] else None
    if url is not None or model is not None:
        config.save_settings(url, model)
    return config.get_settings()


@router.get("/health")
def health():
    return {"status": "ok", "service": "locus"}


@router.get("/logs")
def get_logs(_: CurrentUser = Depends(get_current_user)):
    return {"logs": list(_request_log)}


@router.delete("/logs", status_code=204)
def clear_logs(_: CurrentUser = Depends(get_current_user)):
    _request_log.clear()


def record_request(method: str, path: str, status: int, ms: int, detail: str | None):
    global _log_seq
    _log_seq += 1
    _request_log.appendleft({
        "seq": _log_seq,
        "ts": __import__("time").strftime("%H:%M:%S"),
        "method": method,
        "path": path,
        "status": status,
        "ms": ms,
        "detail": detail,
    })
