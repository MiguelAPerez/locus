import os
import json


def _settings_path() -> str:
    return os.path.join(os.getenv("DATA_DIR", "./data"), "settings.json")


def _load_saved() -> dict:
    path = _settings_path()
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def get_ollama_url() -> str:
    env = os.getenv("OLLAMA_URL")
    if env:
        return env
    return _load_saved().get("ollama_url", "http://localhost:11434")


def get_embed_model() -> str:
    env = os.getenv("EMBED_MODEL")
    if env:
        return env
    return _load_saved().get("embed_model", "nomic-embed-text")


def get_max_upload_bytes() -> int:
    val = os.getenv("MAX_UPLOAD_MB", "100")
    try:
        return int(val) * 1024 * 1024
    except ValueError:
        return 100 * 1024 * 1024


def get_settings() -> dict:
    saved = _load_saved()
    return {
        "ollama_url": {
            "value": get_ollama_url(),
            "source": "env" if os.getenv("OLLAMA_URL") else ("saved" if "ollama_url" in saved else "default"),
            "readonly": bool(os.getenv("OLLAMA_URL")),
        },
        "embed_model": {
            "value": get_embed_model(),
            "source": "env" if os.getenv("EMBED_MODEL") else ("saved" if "embed_model" in saved else "default"),
            "readonly": bool(os.getenv("EMBED_MODEL")),
        },
    }


def save_settings(ollama_url: str | None, embed_model: str | None):
    saved = _load_saved()
    if ollama_url is not None:
        saved["ollama_url"] = ollama_url
    if embed_model is not None:
        saved["embed_model"] = embed_model
    path = _settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(saved, f)
