from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from app import embeddings, store, spaces as sp, collections as col
from app.auth import get_current_user, CurrentUser
from app.routes.spaces import assert_space_access

router = APIRouter(tags=["collections"])


class CollectionCreate(BaseModel):
    name: str


@router.get("/collections")
def list_collections(user: CurrentUser = Depends(get_current_user)):
    collections = col.list_collections(user.id)
    if user.allowed_collections:
        collections = [c for c in collections if c in user.allowed_collections]
    return {"collections": collections}


@router.post("/collections", status_code=201)
def create_collection(body: CollectionCreate, user: CurrentUser = Depends(get_current_user)):
    if user.allowed_collections:
        raise HTTPException(403, "API key does not permit creating collections")
    try:
        name = col.create_collection(body.name, user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"collection": name, "status": "created"}


@router.get("/collections/{name}")
def get_collection(name: str, user: CurrentUser = Depends(get_current_user)):
    if user.allowed_collections and name not in user.allowed_collections:
        raise HTTPException(403, "API key does not grant access to this collection")
    try:
        return col.get_collection(name, user.id)
    except KeyError:
        raise HTTPException(404, f"Collection '{name}' not found")


@router.delete("/collections/{name}", status_code=200)
def delete_collection(name: str, user: CurrentUser = Depends(get_current_user)):
    if user.allowed_collections and name not in user.allowed_collections:
        raise HTTPException(403, "API key does not grant access to this collection")
    try:
        col.delete_collection(name, user.id)
    except KeyError:
        raise HTTPException(404, f"Collection '{name}' not found")
    return {"collection": name, "status": "deleted"}


@router.post("/collections/{name}/spaces/{space}", status_code=200)
def add_space_to_collection(name: str, space: str, user: CurrentUser = Depends(get_current_user)):
    if user.allowed_collections and name not in user.allowed_collections:
        raise HTTPException(403, "API key does not grant access to this collection")
    assert_space_access(space, user)
    try:
        col.add_space(name, space, user.id)
    except KeyError:
        raise HTTPException(404, f"Collection '{name}' not found")
    return col.get_collection(name, user.id)


@router.delete("/collections/{name}/spaces/{space}", status_code=200)
def remove_space_from_collection(name: str, space: str, user: CurrentUser = Depends(get_current_user)):
    if user.allowed_collections and name not in user.allowed_collections:
        raise HTTPException(403, "API key does not grant access to this collection")
    try:
        col.remove_space(name, space, user.id)
    except KeyError:
        raise HTTPException(404, f"Collection '{name}' not found")
    return col.get_collection(name, user.id)


@router.get("/collections/{name}/search")
async def search_collection(
    name: str,
    q: str = Query(..., description="Search query"),
    k: int = Query(5, ge=1, le=50),
    full: bool = Query(False),
    user: CurrentUser = Depends(get_current_user),
):
    try:
        collection = col.get_collection(name, user.id)
    except KeyError:
        raise HTTPException(404, f"Collection '{name}' not found")

    if user.allowed_collections and name not in user.allowed_collections:
        raise HTTPException(403, "API key does not grant access to this collection")

    member_spaces = [s for s in collection["spaces"] if sp.space_exists(s, username=user.username)]
    if user.allowed_spaces:
        member_spaces = [s for s in member_spaces if s in user.allowed_spaces]
    if not member_spaces:
        raise HTTPException(400, "Collection has no valid spaces to search")

    try:
        vector = await embeddings.embed(q)
    except Exception as e:
        raise HTTPException(502, f"Ollama embedding failed: {e}")

    merged = []
    for space_name in member_spaces:
        results = store.search(space_name, vector, k=k, username=user.username)
        for r in results:
            r["space"] = space_name
        merged.extend(results)

    merged.sort(key=lambda r: r["score"], reverse=True)
    merged = merged[:k]

    if full:
        for r in merged:
            doc = await sp.load_document(r["space"], r["doc_id"], username=user.username)
            r["full_text"] = doc["text"] if doc else None

    return {"query": q, "collection": name, "results": merged}
