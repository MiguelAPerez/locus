import json
import os
import re

DATA_DIR = os.getenv("DATA_DIR", "./data")
_COLLECTIONS_FILE = os.path.join(DATA_DIR, "collections.json")


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", name.strip().lower())


def _load() -> dict:
    if not os.path.exists(_COLLECTIONS_FILE):
        return {}
    with open(_COLLECTIONS_FILE) as f:
        return json.load(f)


def _save(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_COLLECTIONS_FILE, "w") as f:
        json.dump(data, f)


def list_collections() -> list[str]:
    return list(_load().keys())


def get_collection(name: str) -> dict:
    data = _load()
    if name not in data:
        raise KeyError(name)
    return {"name": name, "spaces": data[name]["spaces"]}


def create_collection(name: str) -> str:
    name = _normalize(name)
    data = _load()
    if name in data:
        raise ValueError(f"Collection '{name}' already exists")
    data[name] = {"spaces": []}
    _save(data)
    return name


def delete_collection(name: str):
    data = _load()
    if name not in data:
        raise KeyError(name)
    del data[name]
    _save(data)


def add_space(collection: str, space: str):
    data = _load()
    if collection not in data:
        raise KeyError(collection)
    if space not in data[collection]["spaces"]:
        data[collection]["spaces"].append(space)
        _save(data)


def remove_space(collection: str, space: str):
    data = _load()
    if collection not in data:
        raise KeyError(collection)
    data[collection]["spaces"] = [s for s in data[collection]["spaces"] if s != space]
    _save(data)
