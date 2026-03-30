import sqlite3
import os
import re
import uuid
import json
from datetime import datetime, timezone

_SPACE_NAME_RE = re.compile(r'^[a-z0-9_-]{1,64}$')

DB_PATH: str = ""  # overridden in tests; resolved lazily in _path()


def _path() -> str:
    if DB_PATH:
        return DB_PATH
    return os.path.join(os.getenv("DATA_DIR", "./data"), "auth.db")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(_path()) or ".", exist_ok=True)
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS spaces (
                name TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (name, owner_id),
                FOREIGN KEY (owner_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS collections (
                name TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                spaces TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                PRIMARY KEY (name, owner_id),
                FOREIGN KEY (owner_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                key_hash TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                user_id TEXT NOT NULL,
                allowed_spaces TEXT NOT NULL DEFAULT '[]',
                allowed_collections TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash, created_at) VALUES (?,?,?,?)",
            ("guest", "guest", "", now),
        )
        conn.commit()


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(username: str, password_hash: str) -> str:
    uid = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at) VALUES (?,?,?,?)",
                (uid, username, password_hash, now),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"User '{username}' already exists")
    return uid


def get_user_by_username(username: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(uid: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return dict(row) if row else None


# ── Spaces registry ───────────────────────────────────────────────────────────

def register_space(name: str, owner_id: str):
    now = datetime.now(timezone.utc).isoformat()
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO spaces (name, owner_id, created_at) VALUES (?,?,?)",
                (name, owner_id, now),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"Space '{name}' already exists")


def unregister_space(name: str, owner_id: str):
    with _conn() as conn:
        conn.execute("DELETE FROM spaces WHERE name=? AND owner_id=?", (name, owner_id))
        conn.commit()


def space_owned_by(name: str, owner_id: str) -> bool:
    with _conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM spaces WHERE name=? AND owner_id=?", (name, owner_id)
        ).fetchone()
    return row is not None


def get_space_owner(name: str) -> str | None:
    """Return any owner_id for a space name, or None if no user owns it.
    Used only to distinguish 404 (no owner) from 403 (owned by someone else).
    Do not use for access decisions — use space_owned_by() instead."""
    with _conn() as conn:
        row = conn.execute("SELECT owner_id FROM spaces WHERE name=? LIMIT 1", (name,)).fetchone()
    return row["owner_id"] if row else None


def list_spaces_for_user(owner_id: str) -> list[str]:
    with _conn() as conn:
        rows = conn.execute("SELECT name FROM spaces WHERE owner_id=?", (owner_id,)).fetchall()
    return [r["name"] for r in rows]


def sync_guest_spaces(disk_spaces: list[str]):
    """Register any on-disk guest spaces that are missing from the DB registry."""
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        for name in disk_spaces:
            if not _SPACE_NAME_RE.match(name):
                continue
            conn.execute(
                "INSERT OR IGNORE INTO spaces (name, owner_id, created_at) VALUES (?,?,?)",
                (name, "guest", now),
            )
        conn.commit()


# ── Collections ───────────────────────────────────────────────────────────────

def create_collection(name: str, owner_id: str):
    if _get_collection_row(name, owner_id):
        raise ValueError(f"Collection '{name}' already exists")
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO collections (name, owner_id, spaces, created_at) VALUES (?,?,?,?)",
            (name, owner_id, "[]", now),
        )
        conn.commit()


def _get_collection_row(name: str, owner_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM collections WHERE name=? AND owner_id=?", (name, owner_id)
        ).fetchone()
    return dict(row) if row else None


def get_collection(name: str, owner_id: str) -> dict:
    row = _get_collection_row(name, owner_id)
    if not row:
        raise KeyError(name)
    return {"name": row["name"], "owner_id": row["owner_id"], "spaces": json.loads(row["spaces"])}


def list_collections_for_user(owner_id: str) -> list[str]:
    with _conn() as conn:
        rows = conn.execute("SELECT name FROM collections WHERE owner_id=?", (owner_id,)).fetchall()
    return [r["name"] for r in rows]


def delete_collection(name: str, owner_id: str):
    if not _get_collection_row(name, owner_id):
        raise KeyError(name)
    with _conn() as conn:
        conn.execute("DELETE FROM collections WHERE name=? AND owner_id=?", (name, owner_id))
        conn.commit()


def collection_add_space(collection: str, space: str, owner_id: str):
    row = _get_collection_row(collection, owner_id)
    if not row:
        raise KeyError(collection)
    spaces = json.loads(row["spaces"])
    if space not in spaces:
        spaces.append(space)
        with _conn() as conn:
            conn.execute(
                "UPDATE collections SET spaces=? WHERE name=? AND owner_id=?",
                (json.dumps(spaces), collection, owner_id),
            )
            conn.commit()


def collection_remove_space(collection: str, space: str, owner_id: str):
    row = _get_collection_row(collection, owner_id)
    if not row:
        raise KeyError(collection)
    spaces = [s for s in json.loads(row["spaces"]) if s != space]
    with _conn() as conn:
        conn.execute(
            "UPDATE collections SET spaces=? WHERE name=? AND owner_id=?",
            (json.dumps(spaces), collection, owner_id),
        )
        conn.commit()


# ── API Keys ──────────────────────────────────────────────────────────────────

def create_api_key(
    user_id: str,
    name: str,
    key_hash: str,
    key_prefix: str,
    allowed_spaces: list[str],
    allowed_collections: list[str],
) -> str:
    kid = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO api_keys (id, name, key_hash, key_prefix, user_id, allowed_spaces, allowed_collections, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (kid, name, key_hash, key_prefix, user_id, json.dumps(allowed_spaces), json.dumps(allowed_collections), now),
        )
        conn.commit()
    return kid


def list_api_keys(user_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM api_keys WHERE user_id=?", (user_id,)).fetchall()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "key_prefix": r["key_prefix"],
            "allowed_spaces": json.loads(r["allowed_spaces"]),
            "allowed_collections": json.loads(r["allowed_collections"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def get_api_key_by_hash(key_hash: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM api_keys WHERE key_hash=?", (key_hash,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "allowed_spaces": json.loads(row["allowed_spaces"]),
        "allowed_collections": json.loads(row["allowed_collections"]),
    }


def delete_api_key(key_id: str, user_id: str):
    with _conn() as conn:
        conn.execute("DELETE FROM api_keys WHERE id=? AND user_id=?", (key_id, user_id))
        conn.commit()
