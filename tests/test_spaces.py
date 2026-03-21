def test_list_spaces_empty(client):
    r = client.get("/spaces")
    assert r.status_code == 200
    assert r.json() == {"spaces": []}


def test_create_space(client):
    r = client.post("/spaces", json={"name": "research"})
    assert r.status_code == 201
    assert r.json() == {"space": "research", "status": "created"}


def test_create_space_normalizes_name(client):
    r = client.post("/spaces", json={"name": "My Space"})
    assert r.status_code == 201
    assert r.json()["space"] == "my_space"


def test_create_duplicate_space(client):
    client.post("/spaces", json={"name": "research"})
    r = client.post("/spaces", json={"name": "research"})
    assert r.status_code == 400


def test_list_spaces_after_create(client):
    client.post("/spaces", json={"name": "alpha"})
    client.post("/spaces", json={"name": "beta"})
    r = client.get("/spaces")
    assert set(r.json()["spaces"]) == {"alpha", "beta"}


def test_delete_space(client):
    client.post("/spaces", json={"name": "temp"})
    r = client.delete("/spaces/temp")
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"
    assert "temp" not in client.get("/spaces").json()["spaces"]


def test_delete_nonexistent_space(client):
    r = client.delete("/spaces/ghost")
    assert r.status_code == 404
