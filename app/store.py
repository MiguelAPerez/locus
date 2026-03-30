import chromadb
import os

DATA_DIR = os.getenv("DATA_DIR", "./data")
GUEST_USER = "guest"

_clients: dict[str, chromadb.ClientAPI] = {}


def _client(space: str, username: str = GUEST_USER) -> chromadb.ClientAPI:
    key = f"{username}/{space}"
    if key not in _clients:
        path = os.path.join(DATA_DIR, username, space, "chroma")
        os.makedirs(path, exist_ok=True)
        _clients[key] = chromadb.PersistentClient(path=path)
    return _clients[key]


def get_or_create_collection(space: str, username: str = GUEST_USER) -> chromadb.Collection:
    return _client(space, username).get_or_create_collection(
        name=space,
        metadata={"hnsw:space": "cosine"},
    )


def upsert(space: str, doc_id: str, chunks: list[str], embeddings: list[list[float]], metadatas: list[dict], username: str = GUEST_USER):
    col = get_or_create_collection(space, username)
    ids = [f"{doc_id}__chunk{i}" for i in range(len(chunks))]
    col.upsert(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)


def search(space: str, query_embedding: list[float], k: int = 5, username: str = GUEST_USER) -> list[dict]:
    col = get_or_create_collection(space, username)
    results = col.query(query_embeddings=[query_embedding], n_results=k, include=["documents", "metadatas", "distances"])
    out = []
    for i in range(len(results["ids"][0])):
        out.append({
            "chunk_id": results["ids"][0][i],
            "doc_id": results["metadatas"][0][i].get("doc_id"),
            "text": results["documents"][0][i],
            "score": round(1 - results["distances"][0][i], 4),
            "metadata": results["metadatas"][0][i],
        })
    return out


def delete_document(space: str, doc_id: str, username: str = GUEST_USER):
    col = get_or_create_collection(space, username)
    existing = col.get(where={"doc_id": {"$eq": doc_id}})
    if existing["ids"]:
        col.delete(ids=existing["ids"])


def delete_space(space: str, username: str = GUEST_USER):
    key = f"{username}/{space}"
    client = _client(space, username)
    try:
        client.delete_collection(space)
    except Exception:
        pass
    _clients.pop(key, None)


def list_documents(space: str, username: str = GUEST_USER) -> list[dict]:
    col = get_or_create_collection(space, username)
    results = col.get(include=["metadatas"])
    seen = {}
    for meta in results["metadatas"]:
        doc_id = meta.get("doc_id")
        if doc_id and doc_id not in seen:
            seen[doc_id] = {
                "doc_id": doc_id,
                "filename": meta.get("filename"),
                "source": meta.get("source"),
                "doc_type": meta.get("doc_type", "text"),
            }
    return list(seen.values())
