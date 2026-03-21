# Locus — Architecture

## Overview

Locus is a single-process Python service. It has no internal queues, workers, or databases beyond what is embedded directly in the process. Each dataspace is a self-contained unit on disk — you can copy, backup, or delete a space by operating on its directory.

---

## Component map

```
┌─────────────────────────────────────────────────────┐
│                    Client                           │
│          (curl / browser / any HTTP client)         │
└────────────────────────┬────────────────────────────┘
                         │ HTTP
                         ▼
┌─────────────────────────────────────────────────────┐
│                   FastAPI app                       │
│                   app/main.py                       │
│                                                     │
│  POST /spaces/{s}/documents   GET /spaces/{s}/search│
│  GET  /spaces/{s}/documents   DELETE /spaces/...    │
└──────────┬──────────────┬──────────────┬────────────┘
           │              │              │
           ▼              ▼              ▼
    ┌────────────┐  ┌──────────┐  ┌───────────────┐
    │ spaces.py  │  │ store.py │  │embeddings.py  │
    │            │  │          │  │               │
    │ File I/O   │  │ ChromaDB │  │ Ollama HTTP   │
    │ Chunking   │  │ (embedded│  │ client        │
    │ Space dirs │  │  per     │  │               │
    └─────┬──────┘  │  space)  │  └──────┬────────┘
          │         └────┬─────┘         │
          ▼              ▼               ▼
   ┌─────────────────────────┐   ┌──────────────────┐
   │  /data/{space}/         │   │  Ollama (external)│
   │  ├── assets/            │   │                  │
   │  │   ├── {id}.txt       │   │  POST /api/      │
   │  │   └── {id}.json      │   │       embeddings │
   │  └── chroma/            │   └──────────────────┘
   │      └── (vector index) │
   └─────────────────────────┘
```

---

## Data model

### Dataspace

A dataspace is a named namespace represented as a directory under `DATA_DIR`:

```
/data/{space_name}/
├── assets/          # Raw document storage
│   ├── {doc_id}.txt     # Original text
│   └── {doc_id}.json    # Document metadata
└── chroma/          # ChromaDB persistent client for this space
```

Each space gets its own ChromaDB `PersistentClient` instance. There is no shared vector index across spaces.

### Document

When a document is ingested:

1. It is assigned a random hex `doc_id` (UUID4, no hyphens)
2. The full original text is written to `assets/{doc_id}.txt`
3. Metadata (source, filename, doc_id) is written to `assets/{doc_id}.json`
4. The text is split into overlapping chunks (default: 512 words, 64-word overlap)
5. Each chunk is embedded via Ollama
6. Chunks + embeddings are upserted into ChromaDB with IDs of the form `{doc_id}__chunk{n}`

This means a single document can produce many vectors, but they all share a `doc_id` in their metadata, allowing grouping and deletion.

### Vector record (ChromaDB)

Each chunk stored in ChromaDB carries:

```json
{
  "id": "{doc_id}__chunk{n}",
  "document": "chunk text...",
  "embedding": [...],
  "metadata": {
    "doc_id": "abc123...",
    "source": "manual",
    "filename": "notes.txt",
    "chunk_index": 0
  }
}
```

---

## Request flows

### Ingest

```
Client POST /spaces/{space}/documents
  │
  ├─ Validate space exists
  ├─ Decode text (from form field or uploaded file)
  ├─ Generate doc_id
  ├─ Chunk text  →  [chunk_0, chunk_1, ..., chunk_n]
  ├─ Embed each chunk via Ollama  →  [vec_0, vec_1, ..., vec_n]
  ├─ Upsert chunks + vectors into ChromaDB (space collection)
  └─ Write raw text + metadata to disk
       → 201 { doc_id, space, chunk_count }
```

### Search

```
Client GET /spaces/{space}/search?q=...&k=5&full=false
  │
  ├─ Validate space exists
  ├─ Embed query string via Ollama  →  query_vector
  ├─ ChromaDB cosine similarity query  →  top-k chunks
  ├─ (optional) Load full doc text from disk for each result
  └─ Return ranked results with score, chunk text, metadata
```

### Fetch document

```
Client GET /spaces/{space}/documents/{doc_id}
  │
  └─ Read {doc_id}.txt + {doc_id}.json from assets/
       → { doc_id, text, metadata }
```

---

## Design decisions

### Embedded ChromaDB, not a server

ChromaDB is used in embedded (`PersistentClient`) mode — it runs inside the Locus process with no separate service. One client instance is created per request (keyed to the space's chroma directory). This keeps deployment simple: one container, one volume.

The trade-off is that concurrent writes to the same space are not safe under high load. For the intended use case (personal/team tooling, not public-facing high-throughput ingestion) this is acceptable.

### Per-space vector collections

Each space gets its own ChromaDB collection rather than a shared collection with space-level filtering. This provides hard isolation (deleting a space truly removes all its vectors), simpler queries (no cross-space leakage risk), and avoids performance degradation as the total document count grows.

### External Ollama

Locus does not bundle or manage an Ollama instance. It connects to one via HTTP. This keeps the container small, lets you reuse a shared Ollama instance across multiple tools, and avoids model re-downloads when the container restarts.

The embedding URL and model are configurable via `OLLAMA_URL` and `EMBED_MODEL` environment variables.

### Chunking strategy

Text is split by word count with a sliding window (default 512 words, 64-word overlap). Overlap ensures that sentences spanning a chunk boundary are not lost. This is a simple, dependency-free approach. For structured data (PDFs, HTML) a more sophisticated splitter may produce better retrieval — that's a natural extension point in `spaces.py`.

### No authentication

Locus has no built-in auth. It is designed to run on a trusted network (localhost or a private container network). If you need access control, put a reverse proxy (nginx, Caddy, Traefik) in front of it.

---

## Extension points

| What | Where |
|---|---|
| Different chunking strategy (sentence, paragraph, token-based) | `spaces.py → chunk_text()` |
| Support non-text files (PDF, HTML) | `app/main.py → ingest_document()` — decode before calling `chunk_text` |
| Swap embedding provider (OpenAI, Cohere, etc.) | `app/embeddings.py` — same interface, different HTTP call |
| Persistent space metadata (creation time, description) | Add a `space.json` alongside the `assets/` and `chroma/` dirs |
| Multi-user spaces with auth | Reverse proxy layer; space naming convention for namespacing |
