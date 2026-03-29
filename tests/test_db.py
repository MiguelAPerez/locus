import pytest
import os
from app import db


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "auth.db"))
    db.init_db()


def test_guest_user_seeded():
    user = db.get_user_by_username("guest")
    assert user is not None
    assert user["id"] == "guest"


def test_create_and_get_user():
    uid = db.create_user("alice", "hashed_pw")
    user = db.get_user_by_username("alice")
    assert user["id"] == uid
    assert user["username"] == "alice"


def test_create_duplicate_user_raises():
    db.create_user("bob", "pw1")
    with pytest.raises(ValueError, match="already exists"):
        db.create_user("bob", "pw2")


def test_register_and_list_space():
    db.create_user("alice", "pw")
    uid = db.get_user_by_username("alice")["id"]
    db.register_space("notes", uid)
    spaces = db.list_spaces_for_user(uid)
    assert "notes" in spaces


def test_register_duplicate_space_raises():
    db.create_user("alice", "pw")
    uid = db.get_user_by_username("alice")["id"]
    db.register_space("notes", uid)
    with pytest.raises(ValueError, match="already exists"):
        db.register_space("notes", uid)


def test_delete_space():
    db.create_user("alice", "pw")
    uid = db.get_user_by_username("alice")["id"]
    db.register_space("notes", uid)
    db.unregister_space("notes")
    assert "notes" not in db.list_spaces_for_user(uid)


def test_space_owner():
    db.create_user("alice", "pw")
    uid = db.get_user_by_username("alice")["id"]
    db.register_space("notes", uid)
    assert db.get_space_owner("notes") == uid


def test_create_and_get_collection():
    db.create_user("alice", "pw")
    uid = db.get_user_by_username("alice")["id"]
    db.create_collection("research", uid)
    col = db.get_collection("research")
    assert col["name"] == "research"
    assert col["owner_id"] == uid
    assert col["spaces"] == []


def test_collection_add_remove_space():
    db.create_user("alice", "pw")
    uid = db.get_user_by_username("alice")["id"]
    db.create_collection("research", uid)
    db.collection_add_space("research", "papers")
    assert "papers" in db.get_collection("research")["spaces"]
    db.collection_remove_space("research", "papers")
    assert "papers" not in db.get_collection("research")["spaces"]


def test_create_and_list_api_key():
    db.create_user("alice", "pw")
    uid = db.get_user_by_username("alice")["id"]
    kid = db.create_api_key(uid, "my-key", "hashed_secret", "lcs_abcd", [], [])
    keys = db.list_api_keys(uid)
    assert any(k["id"] == kid for k in keys)


def test_delete_api_key():
    db.create_user("alice", "pw")
    uid = db.get_user_by_username("alice")["id"]
    kid = db.create_api_key(uid, "my-key", "hashed_secret", "lcs_abcd", [], [])
    db.delete_api_key(kid, uid)
    assert not any(k["id"] == kid for k in db.list_api_keys(uid))
