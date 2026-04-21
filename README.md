# Locus

[![CI](https://github.com/MiguelAPerez/locus/actions/workflows/ci.yml/badge.svg)](https://github.com/MiguelAPerez/locus/actions/workflows/ci.yml)
[![Release](https://github.com/MiguelAPerez/locus/actions/workflows/release.yml/badge.svg)](https://github.com/MiguelAPerez/locus/actions/workflows/release.yml)

**Semantic dataspace manager.** Create isolated spaces, ingest documents, and search them with natural language — all through a simple REST API or the built-in web UI.

Locus pairs with any [Ollama](https://ollama.com) instance for local embeddings, stores vectors in [ChromaDB](https://www.trychroma.com/), and keeps raw assets on disk. No cloud dependencies.

![Locus UI](docs/imgs/page.png)

---

## Features

- **Dataspaces** — isolated namespaces, each with its own vector index and file store
- **Semantic search** — cosine similarity over Ollama embeddings
- **Full document fetch** — retrieve the original ingested text by ID
- **File or text ingest** — POST plain text or upload `.txt`, `.md`, `.csv`, `.json`, `.pdf`, images, and audio files
- **PDF extraction** — text layer extracted via pypdf
- **Image OCR** — text extracted from images via Tesseract
- **Audio transcription** — speech-to-text via Whisper (runs locally)
- **Collections** — group spaces and search across all of them with a single query
- **Optional auth** — per-user login, API keys, and admin controls (disabled by default)
- **Web UI** — dark-themed single-page interface served at `/`
- **Curl-friendly** — every operation is a plain HTTP call, no SDK required
- **Containerized** — single Docker image, connects to your existing Ollama instance

---

## Quick start

### Pull from registry (recommended)

Pre-built images are published to the GitHub Container Registry on every release:

```bash
docker pull ghcr.io/miguelaperez/locus:latest
```

```bash
docker run -d \
  --name locus \
  -p 8000:8000 \
  -e OLLAMA_URL=http://host.docker.internal:11434 \ # Point to your Ollama instance
  -e EMBED_MODEL=nomic-embed-text \ # Default embedding model name
  -v locus_data:/data \
  ghcr.io/miguelaperez/locus:latest
```

### Build locally

```bash
cp .env.example .env
# Edit .env to point OLLAMA_URL at your Ollama instance

docker compose up --build -d
```

Open [http://localhost:8000](http://localhost:8000) for the UI, or jump straight to the API.

> **Note:** For local development, view more [here](docs/README.md).

---

## Configuration

All configuration is via environment variables (or `.env`):

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://host.docker.internal:11434` | URL of your Ollama instance |
| `EMBED_MODEL` | `nomic-embed-text` | Model name for embeddings |
| `DATA_DIR` | `/data` | Root directory for spaces and assets |
| `MAX_UPLOAD_MB` | `100` | Maximum file upload size in megabytes |
| `MAX_BULK_FILES` | `50` | Maximum number of files per bulk upload request |
| `CHUNK_SIZE` | `256` | Words per chunk when splitting documents for embedding |
| `CHUNK_OVERLAP` | `32` | Overlapping words between consecutive chunks |
| `MAX_CHUNK_CHARS` | `4000` | Hard character cap per chunk (guards against token limit overflows) |
| `MAX_WORD_CHARS` | `200` | Truncates individual tokens before chunking (handles minified code, base64, etc.) |
| `LOCUS_PORT` | `8000` | Host port (Docker only) |

Auth is disabled by default — all requests run as a built-in `guest` user. See [docs/auth.md](docs/auth.md) to enable per-user login, API keys, and admin controls.

### Recommended configuration

The default `nomic-embed-text` model works well for prose but has an 8K token context window that can cause failures on numeric-heavy files (JSON weight arrays, minified code). For better coverage:

| Model | Size | Context | Best for |
|---|---|---|---|
| `qwen3-embedding:4b` | 2.5 GB | 40K tokens | Best balance — recommended |
| `qwen3-embedding:0.6b` | 639 MB | 32K tokens | Lightweight, good for smaller machines |
| `nomic-embed-text` | ~274 MB | 8K tokens | Default, fine for prose-only workloads |

**For `qwen3-embedding:4b` or `:0.6b`, use larger chunks** to take advantage of the wider context window:

```bash
EMBED_MODEL=qwen3-embedding:4b
CHUNK_SIZE=512
MAX_CHUNK_CHARS=8000
```

> **Note:** Changing `EMBED_MODEL` requires wiping and rebuilding all existing embeddings — vectors from different models are incompatible. Delete the space and re-sync all documents to rebuild with the new model.

---

## API reference

### Spaces

```markdown
POST   /spaces              Create a new dataspace
GET    /spaces              List all dataspaces
DELETE /spaces/{space}      Delete a space and all its data
```

### Collections

```markdown
POST   /collections                           Create a new collection
GET    /collections                           List all collections
GET    /collections/{name}                    Get collection details (member spaces)
DELETE /collections/{name}                    Delete a collection
POST   /collections/{name}/spaces/{space}     Add a space to a collection
DELETE /collections/{name}/spaces/{space}     Remove a space from a collection
```

```
GET /collections/{name}/search?q=...&k=5&full=false
```

| Param | Default | Description |
|---|---|---|
| `q` | required | Search query (regex pattern when `mode=regex`) |
| `k` | `5` | Number of results (1–500) |
| `mode` | `semantic` | Search mode: `semantic` or `regex` |
| `full` | `false` | Include full document text alongside each chunk |

### Documents

```markdown
POST   /spaces/{space}/documents              Ingest text or a file
POST   /spaces/{space}/documents/bulk         Bulk ingest multiple files
GET    /spaces/{space}/documents              List documents in a space
GET    /spaces/{space}/documents/{id}         Fetch full document text
DELETE /spaces/{space}/documents/{id}         Delete a document
```

#### Bulk ingest

`POST /spaces/{space}/documents/bulk` — upload multiple files in a single request. All files are processed even if some fail; per-file status is returned for each.

**Request** (`multipart/form-data`):

| Field | Required | Description |
|---|---|---|
| `files` | yes | One or more files to ingest |
| `source` | no | Metadata string applied to all files |

**Response**:

```json
{
  "space": "myspace",
  "results": [
    {"filename": "doc1.pdf", "doc_id": "abc123", "chunk_count": 12, "error": null},
    {"filename": "empty.txt", "doc_id": null, "chunk_count": null, "error": "File is empty"}
  ],
  "succeeded": 1,
  "failed": 1
}
```

**Limits** (both configurable via env):

- Max files per request: `MAX_BULK_FILES` (default **50**) — requests over this limit are rejected with HTTP 400
- Max size per file: `MAX_UPLOAD_MB` (default **100 MB**) — oversized files are skipped with a per-file error in `results`

All files within limits are always processed even if some fail; per-file status is in `results[].error`.

### Search

```markdown
GET /spaces/{space}/search?q=...&k=5&full=false
```

| Param | Default | Description |
|---|---|---|
| `q` | required | Search query (regex pattern when `mode=regex`) |
| `k` | `5` | Number of results (1–500) |
| `mode` | `semantic` | Search mode: `semantic` or `regex` |
| `full` | `false` | Include full document text alongside each chunk |

### Other

```markdown
GET /health     Service health check
GET /           Web UI
GET /docs       Auto-generated OpenAPI docs (FastAPI)
```

> **Note:** For detailed examples calls using `curl` see [docs/README.md](docs/README.md).

---

## Contributing

We're currently in early development and not accepting external contributions, but if you're interested in contributing or have ideas to share, please open an issue or reach out!

## License

MIT
