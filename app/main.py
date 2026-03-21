from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os

from . import embeddings, store, spaces

app = FastAPI(title="Locus", description="Semantic dataspace manager", version="1.0.0")

# ── Models ────────────────────────────────────────────────────────────────────

class SpaceCreate(BaseModel):
    name: str

class IngestResponse(BaseModel):
    doc_id: str
    space: str
    chunk_count: int

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

# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "locus"}

# ── Static UI ─────────────────────────────────────────────────────────────────

_static = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static):
    app.mount("/static", StaticFiles(directory=_static), name="static")

    @app.get("/")
    def ui():
        return FileResponse(os.path.join(_static, "index.html"))
