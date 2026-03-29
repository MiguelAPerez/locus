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


def test_space_path_defaults_to_guest(tmp_data_dir):
    import app.spaces as s
    path = s._space_dir("notes")
    assert path == str(tmp_data_dir / "guest" / "notes")


def test_space_path_with_username(tmp_data_dir):
    import app.spaces as s
    path = s._space_dir("notes", username="alice")
    assert path == str(tmp_data_dir / "alice" / "notes")


def test_create_space_under_username(tmp_data_dir):
    import app.spaces as s
    s.create_space("notes", username="alice")
    assert (tmp_data_dir / "alice" / "notes" / "assets").is_dir()


def test_space_exists_with_username(tmp_data_dir):
    import app.spaces as s
    s.create_space("notes", username="alice")
    assert s.space_exists("notes", username="alice")
    assert not s.space_exists("notes", username="bob")


def test_migrate_flat_spaces(tmp_data_dir):
    import app.spaces as s
    # Create flat legacy dirs (must contain chroma/ to be recognised as spaces)
    (tmp_data_dir / "old_space" / "chroma").mkdir(parents=True)
    (tmp_data_dir / "another" / "chroma").mkdir(parents=True)
    s.migrate_flat_spaces()
    assert (tmp_data_dir / "guest" / "old_space").is_dir()
    assert (tmp_data_dir / "guest" / "another").is_dir()
    assert not (tmp_data_dir / "old_space").exists()
    assert not (tmp_data_dir / "another").exists()
