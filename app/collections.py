import re
from . import db


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", name.strip().lower())


def list_collections(owner_id: str) -> list[str]:
    return db.list_collections_for_user(owner_id)


def get_collection(name: str, owner_id: str) -> dict:
    col = db.get_collection(name)
    if col["owner_id"] != owner_id:
        raise KeyError(name)
    return {"name": col["name"], "spaces": col["spaces"]}


def create_collection(name: str, owner_id: str) -> str:
    name = _normalize(name)
    db.create_collection(name, owner_id)
    return name


def delete_collection(name: str, owner_id: str):
    col = db.get_collection(name)
    if col["owner_id"] != owner_id:
        raise KeyError(name)
    db.delete_collection(name)


def add_space(collection: str, space: str, owner_id: str):
    col = db.get_collection(collection)
    if col["owner_id"] != owner_id:
        raise KeyError(collection)
    db.collection_add_space(collection, space)


def remove_space(collection: str, space: str, owner_id: str):
    col = db.get_collection(collection)
    if col["owner_id"] != owner_id:
        raise KeyError(collection)
    db.collection_remove_space(collection, space)
