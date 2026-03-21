from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from typing import Optional
from collections import deque
import json
import time
import os

from . import embeddings, store, spaces, config

app = FastAPI(title="Locus", description="Semantic dataspace manager", version="1.0.0")

_request_log: deque = deque(maxlen=200)
_log_seq = 0

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    ms = round((time.time() - start) * 1000)

    if request.url.path == "/logs":
        return response

    detail = None
    if response.status_code >= 400:
        # buffer body to extract error detail, then rebuild response
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

# ── Models ────────────────────────────────────────────────────────────────────

class SpaceCreate(BaseModel):
    name: str

class IngestResponse(BaseModel):
    doc_id: str
    space: str
    chunk_count: int

class SettingsUpdate(BaseModel):
    ollama_url: Optional[str] = None
    embed_model: Optional[str] = None

# ── Spaces ────────────────────────────────────────────────────────────────────

@app.get("/spaces")
def list_spaces():
    return {"spaces": spaces.list_spaces()}


@app.post("/spaces", status_code=201)
def create_space(body: SpaceCreate):
    name = body.name.strip().lower().replace(" ", "_")
    if spaces.space_exists(name):
        raise HTTPException(400, f"Space '{name}' already exists")
    spaces.create_space(name)
    return {"space": name, "status": "created"}


@app.delete("/spaces/{space}", status_code=200)
def delete_space(space: str):
    if not spaces.space_exists(space):
        raise HTTPException(404, f"Space '{space}' not found")
    store.delete_space(space)
    spaces.delete_space_dir(space)
    return {"space": space, "status": "deleted"}

# ── Documents ─────────────────────────────────────────────────────────────────

@app.get("/spaces/{space}/documents")
def list_documents(space: str):
    if not spaces.space_exists(space):
        raise HTTPException(404, f"Space '{space}' not found")
    return {"documents": store.list_documents(space)}


@app.post("/spaces/{space}/documents", status_code=201)
async def ingest_document(
    space: str,
    text: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    if not spaces.space_exists(space):
        raise HTTPException(404, f"Space '{space}' not found")
    if not text and not file:
        raise HTTPException(400, "Provide either 'text' or a 'file'")

    filename = None
    if file:
        content = await file.read()
        if not content:
            raise HTTPException(400, f"Uploaded file '{file.filename}' is empty")
        text = content.decode("utf-8", errors="replace")
        filename = file.filename

    doc_id = spaces.new_doc_id()
    chunks = spaces.chunk_text(text)

    try:
        vectors = await embeddings.embed_batch(chunks)
    except Exception as e:
        raise HTTPException(502, f"Ollama embedding failed: {e}")

    meta = {"doc_id": doc_id, "source": source or "manual", "filename": filename or ""}
    chunk_metas = [{**meta, "chunk_index": i} for i in range(len(chunks))]

    store.upsert(space, doc_id, chunks, vectors, chunk_metas)
    await spaces.save_document(space, doc_id, text, meta)

    return IngestResponse(doc_id=doc_id, space=space, chunk_count=len(chunks))


@app.get("/spaces/{space}/documents/{doc_id}")
async def get_document(space: str, doc_id: str):
    if not spaces.space_exists(space):
        raise HTTPException(404, f"Space '{space}' not found")
    doc = await spaces.load_document(space, doc_id)
    if not doc:
        raise HTTPException(404, f"Document '{doc_id}' not found")
    return doc


@app.delete("/spaces/{space}/documents/{doc_id}")
def delete_document(space: str, doc_id: str):
    if not spaces.space_exists(space):
        raise HTTPException(404, f"Space '{space}' not found")
    store.delete_document(space, doc_id)
    spaces.delete_document_files(space, doc_id)
    return {"doc_id": doc_id, "status": "deleted"}

# ── Search ────────────────────────────────────────────────────────────────────

@app.get("/spaces/{space}/search")
async def search(
    space: str,
    q: str = Query(..., description="Search query"),
    k: int = Query(5, ge=1, le=50),
    full: bool = Query(False, description="Include full document text in results"),
):
    if not spaces.space_exists(space):
        raise HTTPException(404, f"Space '{space}' not found")

    try:
        vector = await embeddings.embed(q)
    except Exception as e:
        raise HTTPException(502, f"Ollama embedding failed: {e}")

    results = store.search(space, vector, k=k)

    if full:
        for r in results:
            doc = await spaces.load_document(space, r["doc_id"])
            r["full_text"] = doc["text"] if doc else None

    return {"query": q, "space": space, "results": results}

# ── Settings ──────────────────────────────────────────────────────────────────

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

# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "locus"}

# ── Logs ──────────────────────────────────────────────────────────────────────

@app.get("/logs")
def get_logs():
    return {"logs": list(_request_log)}

@app.delete("/logs", status_code=204)
def clear_logs():
    _request_log.clear()

# ── Static UI ─────────────────────────────────────────────────────────────────

_static = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static):
    app.mount("/static", StaticFiles(directory=_static), name="static")

    @app.get("/")
    def ui():
        return FileResponse(os.path.join(_static, "index.html"))
