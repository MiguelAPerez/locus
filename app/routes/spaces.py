import re
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Depends
from pydantic import BaseModel
from typing import Optional

from app import embeddings, store, spaces as sp, config, extractors, db
from app.auth import get_current_user, CurrentUser

router = APIRouter(tags=["spaces"])

_SPACE_NAME_RE = re.compile(r'^[a-z0-9_-]{1,64}$')


class SpaceCreate(BaseModel):
    name: str


class IngestResponse(BaseModel):
    doc_id: str
    space: str
    chunk_count: int


def assert_space_access(space: str, user: CurrentUser):
    if db.space_owned_by(space, user.id):
        if user.allowed_spaces and space not in user.allowed_spaces:
            raise HTTPException(403, "API key does not grant access to this space")
        return
    # Not owned by this user — distinguish 404 (doesn't exist) from 403 (owned by someone else)
    if db.get_space_owner(space) is not None:
        raise HTTPException(403, "Access denied")
    raise HTTPException(404, f"Space '{space}' not found")


@router.get("/spaces")
def list_spaces(user: CurrentUser = Depends(get_current_user)):
    spaces = db.list_spaces_for_user(user.id)
    if user.allowed_spaces:
        spaces = [s for s in spaces if s in user.allowed_spaces]
    return {"spaces": spaces}


@router.post("/spaces", status_code=201)
def create_space(body: SpaceCreate, user: CurrentUser = Depends(get_current_user)):
    name = body.name.strip().lower().replace(" ", "_")
    if not _SPACE_NAME_RE.match(name):
        raise HTTPException(400, "Space name must be 1-64 characters: letters, digits, _ or -")
    try:
        db.register_space(name, user.id)
    except ValueError:
        raise HTTPException(400, f"Space '{name}' already exists")
    try:
        sp.create_space(name, username=user.username)
    except Exception:
        db.unregister_space(name, user.id)
        raise HTTPException(500, "Failed to create space directory")
    return {"space": name, "status": "created"}


@router.delete("/spaces/{space}", status_code=200)
def delete_space(space: str, user: CurrentUser = Depends(get_current_user)):
    assert_space_access(space, user)
    store.delete_space(space, username=user.username)
    sp.delete_space_dir(space, username=user.username)
    db.unregister_space(space, user.id)
    return {"space": space, "status": "deleted"}


@router.get("/spaces/{space}/documents")
def list_documents(space: str, user: CurrentUser = Depends(get_current_user)):
    assert_space_access(space, user)
    return {"documents": store.list_documents(space, username=user.username)}


@router.post("/spaces/{space}/documents", status_code=201)
async def ingest_document(
    space: str,
    text: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user: CurrentUser = Depends(get_current_user),
):
    assert_space_access(space, user)
    if not text and not file:
        raise HTTPException(400, "Provide either 'text' or a 'file'")

    filename = None
    file_content = None
    if file:
        file_content = await file.read()
        if not file_content:
            raise HTTPException(400, f"Uploaded file '{file.filename}' is empty")
        max_bytes = config.get_max_upload_bytes()
        if len(file_content) > max_bytes:
            raise HTTPException(413, f"File '{file.filename}' exceeds the {max_bytes // (1024*1024)} MB limit")
        filename = file.filename
        try:
            text = await extractors.extract_text(file_content, filename, file.content_type or "")
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(502, f"Extraction failed for '{filename}': {e}")

    if not text:
        raise HTTPException(400, "No text could be extracted from the provided input")

    doc_id = sp.new_doc_id()
    chunks = sp.chunk_text(text)

    try:
        vectors = await embeddings.embed_batch(chunks)
    except Exception as e:
        raise HTTPException(502, f"Ollama embedding failed: {e}")

    doc_type = extractors.doc_type(filename or "", (file.content_type or "") if file else "")
    meta = {"doc_id": doc_id, "source": source or "manual", "filename": filename or "", "doc_type": doc_type}
    chunk_metas = [{**meta, "chunk_index": i} for i in range(len(chunks))]

    store.upsert(space, doc_id, chunks, vectors, chunk_metas, username=user.username)
    await sp.save_document(space, doc_id, text, meta, username=user.username)
    if file_content and doc_type != "text":
        await sp.save_original_file(space, doc_id, file_content, filename, username=user.username)

    return IngestResponse(doc_id=doc_id, space=space, chunk_count=len(chunks))


@router.get("/spaces/{space}/documents/{doc_id}")
async def get_document(space: str, doc_id: str, user: CurrentUser = Depends(get_current_user)):
    assert_space_access(space, user)
    doc = await sp.load_document(space, doc_id, username=user.username)
    if not doc:
        raise HTTPException(404, f"Document '{doc_id}' not found")
    return doc


@router.delete("/spaces/{space}/documents/{doc_id}")
def delete_document(space: str, doc_id: str, user: CurrentUser = Depends(get_current_user)):
    assert_space_access(space, user)
    store.delete_document(space, doc_id, username=user.username)
    sp.delete_document_files(space, doc_id, username=user.username)
    return {"doc_id": doc_id, "status": "deleted"}


@router.get("/spaces/{space}/search")
async def search(
    space: str,
    q: str = Query(..., description="Search query"),
    k: int = Query(5, ge=1, le=50),
    full: bool = Query(False),
    user: CurrentUser = Depends(get_current_user),
):
    assert_space_access(space, user)

    try:
        vector = await embeddings.embed(q)
    except Exception as e:
        raise HTTPException(502, f"Ollama embedding failed: {e}")

    results = store.search(space, vector, k=k, username=user.username)

    if full:
        for r in results:
            doc = await sp.load_document(space, r["doc_id"], username=user.username)
            r["full_text"] = doc["text"] if doc else None

    return {"query": q, "space": space, "results": results}
