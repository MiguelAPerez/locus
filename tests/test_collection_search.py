import pytest
from app import db
from app import collections as col


@pytest.fixture
def seeded_collection(client, mock_embeddings):
    """Two spaces each with one document, bundled into a collection."""
    client.post("/spaces", json={"name": "alpha"})
    client.post("/spaces/alpha/documents", data={"text": "The mitochondria is the powerhouse of the cell."})
    client.post("/spaces", json={"name": "beta"})
    client.post("/spaces/beta/documents", data={"text": "Photosynthesis converts sunlight into glucose."})

    uid = db.get_user_by_username("guest")["id"]
    col.create_collection("sci", uid)
    col.add_space("sci", "alpha", uid)
    col.add_space("sci", "beta", uid)
    return "sci"


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------

def test_semantic_search_returns_results(client, seeded_collection, mock_embeddings):
    r = client.get("/collections/sci/search?q=cell&k=5")
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "cell"
    assert body["collection"] == "sci"
    assert isinstance(body["results"], list)
    assert len(body["results"]) > 0


def test_semantic_search_respects_k(client, seeded_collection, mock_embeddings):
    r = client.get("/collections/sci/search?q=biology&k=1")
    assert r.status_code == 200
    assert len(r.json()["results"]) <= 1


def test_semantic_search_includes_space_field(client, seeded_collection, mock_embeddings):
    r = client.get("/collections/sci/search?q=energy&k=5")
    assert r.status_code == 200
    for result in r.json()["results"]:
        assert "space" in result
        assert result["space"] in ("alpha", "beta")


def test_semantic_search_full_text(client, seeded_collection, mock_embeddings):
    r = client.get("/collections/sci/search?q=cell&k=5&full=true")
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) > 0
    for result in results:
        assert "full_text" in result


# ---------------------------------------------------------------------------
# Regex search
# ---------------------------------------------------------------------------

def test_regex_search_returns_matching_results(client, seeded_collection, mock_embeddings):
    r = client.get("/collections/sci/search?q=mitochondria&mode=regex")
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) >= 1
    assert all("mitochondria" in res["text"].lower() for res in results)


def test_regex_search_case_insensitive(client, seeded_collection, mock_embeddings):
    r = client.get("/collections/sci/search?q=PHOTOSYNTHESIS&mode=regex")
    assert r.status_code == 200
    assert len(r.json()["results"]) >= 1


def test_regex_search_respects_k(client, seeded_collection, mock_embeddings):
    r = client.get("/collections/sci/search?q=.%2B&mode=regex&k=1")
    assert r.status_code == 200
    assert len(r.json()["results"]) <= 1


def test_regex_search_no_match_returns_empty(client, seeded_collection, mock_embeddings):
    r = client.get("/collections/sci/search?q=xyzzy_nomatch_9999&mode=regex")
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_regex_search_invalid_pattern_returns_400(client, seeded_collection, mock_embeddings):
    r = client.get("/collections/sci/search?q=%5Binvalid&mode=regex")
    assert r.status_code == 400


def test_regex_search_pattern_too_long_returns_400(client, seeded_collection, mock_embeddings):
    long_pattern = "a" * 501
    r = client.get(f"/collections/sci/search?q={long_pattern}&mode=regex")
    assert r.status_code == 400


def test_regex_search_includes_space_field(client, seeded_collection, mock_embeddings):
    r = client.get("/collections/sci/search?q=.%2B&mode=regex&k=10")
    assert r.status_code == 200
    for result in r.json()["results"]:
        assert "space" in result


# ---------------------------------------------------------------------------
# Invalid mode
# ---------------------------------------------------------------------------

def test_invalid_mode_returns_422(client, seeded_collection, mock_embeddings):
    r = client.get("/collections/sci/search?q=test&mode=fuzzy")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_search_unknown_collection_returns_404(client, mock_embeddings):
    r = client.get("/collections/ghost/search?q=test")
    assert r.status_code == 404


def test_search_missing_query_returns_422(client, seeded_collection):
    r = client.get("/collections/sci/search")
    assert r.status_code == 422


def test_search_collection_with_no_valid_spaces_returns_400(client, mock_embeddings):
    uid = db.get_user_by_username("guest")["id"]
    col.create_collection("empty", uid)
    col.add_space("empty", "nonexistent-space", uid)
    r = client.get("/collections/empty/search?q=test")
    assert r.status_code == 400
