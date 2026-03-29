from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from typing import Optional
from collections import deque
import json
import time
import os

from . import embeddings, store, spaces, config, extractors, collections as col, db
from .auth import get_current_user, CurrentUser
from .routes.auth import router as auth_router

app = FastAPI(title="Locus", description="Semantic dataspace manager", version="1.0.0")
app.include_router(auth_router)

_request_log: deque = deque(maxlen=200)
_log_seq = 0


@app.on_event("startup")
def startup():
    db.init_db()
    spaces.migrate_flat_spaces()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    ms = round((time.time() - start) * 1000)

    if request.url.path == "/logs":
        return response

    detail = None
    if response.status_code >= 400:
        body = b"".join([chunk async for chunk in response.body_iterator])
        try:
            detail = json.loads(body).get("detail")
        except Exception:
            detail = body.decode("utf-8", errors="replace")[:300]
        response = Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    global _log_seq
    _log_seq += 1
    _request_log.appendleft({
        "seq": _log_seq,
        "ts": time.strftime("%H:%M:%S"),
        "method": request.method,
        "path": str(request.url.path),
        "status": response.status_code,
        "ms": ms,
        "detail": detail,
    })
    return response


# -- Models --------------------------------------------------------------------

class SpaceCreate(BaseModel):
    name: str

class CollectionCreate(BaseModel):
    name: str

class IngestResponse(BaseModel):
    doc_id: str
    space: str
    chunk_count: int

class SettingsUpdate(BaseModel):
    ollama_url: Optional[str] = None
    embed_model: Optional[str] = None


# -- Ownership helper ----------------------------------------------------------

def _assert_space_access(space: str, user: CurrentUser):
    owner = db.get_space_owner(space)
    if owner is None:
        raise HTTPException(404, f"Space '{space}' not found")
    if owner != user.id:
        raise HTTPException(403, "Access denied")
    if user.allowed_spaces and space not in user.allowed_spaces:
        raise HTTPException(403, "API key does not grant access to this space")


# -- Spaces -------------------------------------------------------------------

@app.get("/spaces")
def list_spaces(user: CurrentUser = Depends(get_current_user)):
    return {"spaces": db.list_spaces_for_user(user.id)}


@app.post("/spaces", status_code=201)
def create_space(body: SpaceCreate, user: CurrentUser = Depends(get_current_user)):
    name = body.name.strip().lower().replace(" ", "_")
    if spaces.space_exists(name, username=user.username):
        raise HTTPException(400, f"Space '{name}' already exists")
    spaces.create_space(name, username=user.username)
    db.register_space(name, user.id)
    return {"space": name, "status": "created"}


@app.delete("/spaces/{space}", status_code=200)
def delete_space(space: str, user: CurrentUser = Depends(get_current_user)):
    _assert_space_access(space, user)
    store.delete_space(space, username=user.username)
    spaces.delete_space_dir(space, username=user.username)
    db.unregister_space(space)
    return {"space": space, "status": "deleted"}


# -- Documents ----------------------------------------------------------------

@app.get("/spaces/{space}/documents")
def list_documents(space: str, user: CurrentUser = Depends(get_current_user)):
    _assert_space_access(space, user)
    return {"documents": store.list_documents(space, username=user.username)}


@app.post("/spaces/{space}/documents", status_code=201)
async def ingest_document(
    space: str,
    text: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user: CurrentUser = Depends(get_current_user),
):
    _assert_space_access(space, user)
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

    doc_id = spaces.new_doc_id()
    chunks = spaces.chunk_text(text)

    try:
        vectors = await embeddings.embed_batch(chunks)
    except Exception as e:
        raise HTTPException(502, f"Ollama embedding failed: {e}")

    doc_type = extractors.doc_type(filename or "", (file.content_type or "") if file else "")
    meta = {"doc_id": doc_id, "source": source or "manual", "filename": filename or "", "doc_type": doc_type}
    chunk_metas = [{**meta, "chunk_index": i} for i in range(len(chunks))]

    store.upsert(space, doc_id, chunks, vectors, chunk_metas, username=user.username)
    await spaces.save_document(space, doc_id, text, meta, username=user.username)
    if file_content and doc_type != "text":
        await spaces.save_original_file(space, doc_id, file_content, filename, username=user.username)

    return IngestResponse(doc_id=doc_id, space=space, chunk_count=len(chunks))


@app.get("/spaces/{space}/documents/{doc_id}")
async def get_document(space: str, doc_id: str, user: CurrentUser = Depends(get_current_user)):
    _assert_space_access(space, user)
    doc = await spaces.load_document(space, doc_id, username=user.username)
    if not doc:
        raise HTTPException(404, f"Document '{doc_id}' not found")
    return doc


@app.delete("/spaces/{space}/documents/{doc_id}")
def delete_document(space: str, doc_id: str, user: CurrentUser = Depends(get_current_user)):
    _assert_space_access(space, user)
    store.delete_document(space, doc_id, username=user.username)
    spaces.delete_document_files(space, doc_id, username=user.username)
    return {"doc_id": doc_id, "status": "deleted"}


# -- Search -------------------------------------------------------------------

@app.get("/spaces/{space}/search")
async def search(
    space: str,
    q: str = Query(..., description="Search query"),
    k: int = Query(5, ge=1, le=50),
    full: bool = Query(False),
    user: CurrentUser = Depends(get_current_user),
):
    _assert_space_access(space, user)

    try:
        vector = await embeddings.embed(q)
    except Exception as e:
        raise HTTPException(502, f"Ollama embedding failed: {e}")

    results = store.search(space, vector, k=k, username=user.username)

    if full:
        for r in results:
            doc = await spaces.load_document(space, r["doc_id"], username=user.username)
            r["full_text"] = doc["text"] if doc else None

    return {"query": q, "space": space, "results": results}


# -- Collections --------------------------------------------------------------

@app.get("/collections")
def list_collections(user: CurrentUser = Depends(get_current_user)):
    return {"collections": col.list_collections(user.id)}


@app.post("/collections", status_code=201)
def create_collection(body: CollectionCreate, user: CurrentUser = Depends(get_current_user)):
    try:
        name = col.create_collection(body.name, user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"collection": name, "status": "created"}


@app.get("/collections/{name}")
def get_collection(name: str, user: CurrentUser = Depends(get_current_user)):
    try:
        return col.get_collection(name, user.id)
    except KeyError:
        raise HTTPException(404, f"Collection '{name}' not found")


@app.delete("/collections/{name}", status_code=200)
def delete_collection(name: str, user: CurrentUser = Depends(get_current_user)):
    try:
        col.delete_collection(name, user.id)
    except KeyError:
        raise HTTPException(404, f"Collection '{name}' not found")
    return {"collection": name, "status": "deleted"}


@app.post("/collections/{name}/spaces/{space}", status_code=200)
def add_space_to_collection(name: str, space: str, user: CurrentUser = Depends(get_current_user)):
    _assert_space_access(space, user)
    try:
        col.add_space(name, space, user.id)
    except KeyError:
        raise HTTPException(404, f"Collection '{name}' not found")
    return col.get_collection(name, user.id)


@app.delete("/collections/{name}/spaces/{space}", status_code=200)
def remove_space_from_collection(name: str, space: str, user: CurrentUser = Depends(get_current_user)):
    try:
        col.remove_space(name, space, user.id)
    except KeyError:
        raise HTTPException(404, f"Collection '{name}' not found")
    return col.get_collection(name, user.id)


@app.get("/collections/{name}/search")
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

    member_spaces = [s for s in collection["spaces"] if spaces.space_exists(s, username=user.username)]
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
            doc = await spaces.load_document(r["space"], r["doc_id"], username=user.username)
            r["full_text"] = doc["text"] if doc else None

    return {"query": q, "collection": name, "results": merged}


# -- Settings -----------------------------------------------------------------

@app.get("/settings")
def get_settings():
    return config.get_settings()


@app.post("/settings")
def update_settings(body: SettingsUpdate):
    current = config.get_settings()
    url = body.ollama_url if body.ollama_url is not None and not current["ollama_url"]["readonly"] else None
    model = body.embed_model if body.embed_model is not None and not current["embed_model"]["readonly"] else None
    if url is not None or model is not None:
        config.save_settings(url, model)
    return config.get_settings()


# -- Health -------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "service": "locus"}


# -- Logs ---------------------------------------------------------------------

@app.get("/logs")
def get_logs():
    return {"logs": list(_request_log)}

@app.delete("/logs", status_code=204)
def clear_logs():
    _request_log.clear()


# -- Static UI ----------------------------------------------------------------

_static = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static):
    app.mount("/static", StaticFiles(directory=_static), name="static")

    @app.get("/")
    def ui():
        return FileResponse(os.path.join(_static, "index.html"))
