import pytest
from app import db


@pytest.fixture(autouse=True)
def _seed_user(tmp_data_dir):
    db.create_user("alice", "pw")


def _uid():
    return db.get_user_by_username("alice")["id"]


def test_create_and_list_collection(client):
    uid = _uid()
    from app import collections as col
    col.create_collection("research", uid)
    assert "research" in col.list_collections(uid)


def test_get_collection(client):
    uid = _uid()
    from app import collections as col
    col.create_collection("research", uid)
    c = col.get_collection("research", uid)
    assert c["name"] == "research"
    assert c["spaces"] == []


def test_get_collection_wrong_owner_raises(client):
    uid = _uid()
    db.create_user("bob", "pw")
    bob_id = db.get_user_by_username("bob")["id"]
    from app import collections as col
    col.create_collection("research", uid)
    with pytest.raises(KeyError):
        col.get_collection("research", bob_id)


def test_delete_collection(client):
    uid = _uid()
    from app import collections as col
    col.create_collection("research", uid)
    col.delete_collection("research", uid)
    assert "research" not in col.list_collections(uid)


def test_add_remove_space(client):
    uid = _uid()
    from app import collections as col
    col.create_collection("research", uid)
    col.add_space("research", "papers", uid)
    assert "papers" in col.get_collection("research", uid)["spaces"]
    col.remove_space("research", "papers", uid)
    assert "papers" not in col.get_collection("research", uid)["spaces"]
