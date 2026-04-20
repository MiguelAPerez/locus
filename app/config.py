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


def get_chunk_size() -> int:
    try:
        return int(os.getenv("CHUNK_SIZE", "256"))
    except ValueError:
        return 256


def get_chunk_overlap() -> int:
    try:
        return int(os.getenv("CHUNK_OVERLAP", "32"))
    except ValueError:
        return 32


def get_max_chunk_chars() -> int:
    try:
        return int(os.getenv("MAX_CHUNK_CHARS", "4000"))
    except ValueError:
        return 4000


def get_max_word_chars() -> int:
    try:
        return int(os.getenv("MAX_WORD_CHARS", "200"))
    except ValueError:
        return 200


def get_max_bulk_files() -> int:
    val = os.getenv("MAX_BULK_FILES", "50")
    try:
        return int(val)
    except ValueError:
        return 50


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


def auth_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "false").lower() == "true"


def registration_enabled() -> bool:
    return os.getenv("REGISTRATION_ENABLED", "false").lower() == "true"


def session_hours() -> int:
    try:
        return int(os.getenv("SESSION_HOURS", "24"))
    except ValueError:
        return 24


def get_initial_admin_username() -> str | None:
    return os.getenv("INITIAL_ADMIN_USERNAME")


def get_initial_admin_password() -> str | None:
    return os.getenv("INITIAL_ADMIN_PASSWORD")
