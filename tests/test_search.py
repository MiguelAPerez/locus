import pytest


@pytest.fixture
def seeded_space(client, mock_embeddings):
    client.post("/spaces", json={"name": "search"})
    client.post("/spaces/search/documents", data={"text": "The mitochondria is the powerhouse of the cell."})
    return "search"


def test_search_returns_results(client, seeded_space, mock_embeddings):
    r = client.get("/spaces/search/search?q=cellular+energy&k=1")
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "cellular energy"
    assert body["space"] == "search"
    assert isinstance(body["results"], list)


def test_search_with_full_text(client, seeded_space, mock_embeddings):
    r = client.get("/spaces/search/search?q=cell&k=1&full=true")
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) >= 1
    assert "full_text" in results[0]


def test_search_unknown_space(client, mock_embeddings):
    r = client.get("/spaces/ghost/search?q=hello")
    assert r.status_code == 404


def test_search_missing_query(client):
    client.post("/spaces", json={"name": "empty"})
    r = client.get("/spaces/empty/search")
    assert r.status_code == 422
