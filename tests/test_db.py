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
    db.unregister_space("notes", uid)
    assert "notes" not in db.list_spaces_for_user(uid)


def test_space_owned_by():
    db.create_user("alice", "pw")
    uid = db.get_user_by_username("alice")["id"]
    db.register_space("notes", uid)
    assert db.space_owned_by("notes", uid) is True
    assert db.space_owned_by("notes", "other-uid") is False


def test_create_and_get_collection():
    db.create_user("alice", "pw")
    uid = db.get_user_by_username("alice")["id"]
    db.create_collection("research", uid)
    col = db.get_collection("research", uid)
    assert col["name"] == "research"
    assert col["owner_id"] == uid
    assert col["spaces"] == []


def test_collection_add_remove_space():
    db.create_user("alice", "pw")
    uid = db.get_user_by_username("alice")["id"]
    db.create_collection("research", uid)
    db.collection_add_space("research", "papers", uid)
    assert "papers" in db.get_collection("research", uid)["spaces"]
    db.collection_remove_space("research", "papers", uid)
    assert "papers" not in db.get_collection("research", uid)["spaces"]


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


def test_first_user_is_admin():
    uid = db.create_user("alice", "pw")
    user = db.get_user_by_id(uid)
    assert user["is_admin"] == 1


def test_second_user_is_not_admin():
    db.create_user("alice", "pw")
    uid2 = db.create_user("bob", "pw")
    user = db.get_user_by_id(uid2)
    assert user["is_admin"] == 0


def test_set_admin():
    uid = db.create_user("alice", "pw")
    db.set_admin(uid, True)
    assert db.get_user_by_id(uid)["is_admin"] == 1
    db.set_admin(uid, False)
    assert db.get_user_by_id(uid)["is_admin"] == 0


def test_list_all_users_excludes_guest():
    db.create_user("alice", "pw")
    db.create_user("bob", "pw")
    users = db.list_all_users()
    assert len(users) == 2
    assert all(u["id"] != "guest" for u in users)


def test_update_password():
    uid = db.create_user("alice", "old_hash")
    db.update_password(uid, "new_hash")
    user = db.get_user_by_id(uid)
    assert user["password_hash"] == "new_hash"


def test_delete_user_cascades():
    uid = db.create_user("alice", "pw")
    db.register_space("notes", uid)
    db.create_collection("research", uid)
    db.create_api_key(uid, "k", "h", "lcs_", [], [])
    db.delete_user(uid)
    assert db.get_user_by_id(uid) is None
    assert db.list_spaces_for_user(uid) == []
    assert db.list_api_keys(uid) == []
