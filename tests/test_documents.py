import io
import pytest


@pytest.fixture
def space(client):
    client.post("/spaces", json={"name": "docs"})
    return "docs"


def test_ingest_text(client, space, mock_embeddings):
    r = client.post(f"/spaces/{space}/documents", data={"text": "Hello world", "source": "test"})
    assert r.status_code == 201
    body = r.json()
    assert body["space"] == space
    assert body["chunk_count"] >= 1
    assert "doc_id" in body


def test_ingest_file(client, space, mock_embeddings):
    content = b"File content for testing."
    r = client.post(
        f"/spaces/{space}/documents",
        files={"file": ("test.txt", io.BytesIO(content), "text/plain")},
    )
    assert r.status_code == 201
    assert r.json()["chunk_count"] >= 1


def test_ingest_no_content(client, space):
    r = client.post(f"/spaces/{space}/documents", data={})
    assert r.status_code == 400


def test_ingest_unknown_space(client, mock_embeddings):
    r = client.post("/spaces/ghost/documents", data={"text": "hello"})
    assert r.status_code == 404


def test_list_documents(client, space, mock_embeddings):
    client.post(f"/spaces/{space}/documents", data={"text": "Doc one"})
    client.post(f"/spaces/{space}/documents", data={"text": "Doc two"})
    r = client.get(f"/spaces/{space}/documents")
    assert r.status_code == 200
    assert len(r.json()["documents"]) == 2


def test_get_document(client, space, mock_embeddings):
    ingest = client.post(f"/spaces/{space}/documents", data={"text": "Retrieve me"})
    doc_id = ingest.json()["doc_id"]
    r = client.get(f"/spaces/{space}/documents/{doc_id}")
    assert r.status_code == 200
    assert r.json()["text"] == "Retrieve me"
    assert r.json()["doc_id"] == doc_id


def test_get_document_not_found(client, space):
    r = client.get(f"/spaces/{space}/documents/nonexistent")
    assert r.status_code == 404


def test_delete_document(client, space, mock_embeddings):
    ingest = client.post(f"/spaces/{space}/documents", data={"text": "Delete me"})
    doc_id = ingest.json()["doc_id"]
    r = client.delete(f"/spaces/{space}/documents/{doc_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"
