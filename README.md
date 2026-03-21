# Locus

**Semantic dataspace manager.** Create isolated spaces, ingest documents, and search them with natural language — all through a simple REST API or the built-in web UI.

Locus pairs with any [Ollama](https://ollama.com) instance for local embeddings, stores vectors in [ChromaDB](https://www.trychroma.com/), and keeps raw assets on disk. No cloud dependencies.

---

## Features

- **Dataspaces** — isolated namespaces, each with its own vector index and file store
- **Semantic search** — cosine similarity over Ollama embeddings
- **Full document fetch** — retrieve the original ingested text by ID
- **File or text ingest** — POST plain text or upload `.txt`, `.md`, `.csv`, `.json` files
- **Web UI** — dark-themed single-page interface served at `/`
- **Curl-friendly** — every operation is a plain HTTP call, no SDK required
- **Containerized** — single Docker image, connects to your existing Ollama instance

---

## Quick start

### Docker (recommended)

```bash
cp .env.example .env
# Edit .env to point OLLAMA_URL at your Ollama instance

docker compose up --build -d
```

Open [http://localhost:8000](http://localhost:8000) for the UI, or jump straight to the API.

### Local (dev)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export OLLAMA_URL=http://localhost:11434
export DATA_DIR=./data

uvicorn app.main:app --reload
```

---

## Configuration

All configuration is via environment variables (or `.env`):

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://host.docker.internal:11434` | URL of your Ollama instance |
| `EMBED_MODEL` | `nomic-embed-text` | Model name for embeddings |
| `DATA_DIR` | `/data` | Root directory for spaces and assets |
| `LOCUS_PORT` | `8000` | Host port (Docker only) |

Make sure the embedding model is already pulled in your Ollama instance:

```bash
ollama pull nomic-embed-text
```

---

## API reference

### Spaces

```
POST   /spaces              Create a new dataspace
GET    /spaces              List all dataspaces
DELETE /spaces/{space}      Delete a space and all its data
```

### Documents

```
POST   /spaces/{space}/documents              Ingest text or a file
GET    /spaces/{space}/documents              List documents in a space
GET    /spaces/{space}/documents/{id}         Fetch full document text
DELETE /spaces/{space}/documents/{id}         Delete a document
```

### Search

```
GET /spaces/{space}/search?q=...&k=5&full=false
```

| Param | Default | Description |
|---|---|---|
| `q` | required | Natural language query |
| `k` | `5` | Number of results (1–50) |
| `full` | `false` | Include full document text alongside each chunk |

### Other

```
GET /health     Service health check
GET /           Web UI
GET /docs       Auto-generated OpenAPI docs (FastAPI)
```

---

## Example curl session

```bash
BASE=http://localhost:8000

# Create a space
curl -s -X POST $BASE/spaces \
  -H 'Content-Type: application/json' \
  -d '{"name": "research"}' | jq

# Ingest text
curl -s -X POST $BASE/spaces/research/documents \
  -F "text=The mitochondria is the powerhouse of the cell." \
  -F "source=biology-101" | jq

# Upload a file
curl -s -X POST $BASE/spaces/research/documents \
  -F "file=@notes.txt" | jq

# Semantic search
curl -s "$BASE/spaces/research/search?q=cellular+energy&k=3" | jq

# Fetch full document
curl -s "$BASE/spaces/research/documents/{doc_id}" | jq

# List spaces
curl -s $BASE/spaces | jq

# Delete a space
curl -s -X DELETE $BASE/spaces/research | jq
```

---

## Project structure

```
.
├── app/
│   ├── main.py          # FastAPI app and all routes
│   ├── embeddings.py    # Ollama embedding client
│   ├── store.py         # ChromaDB vector store wrapper
│   ├── spaces.py        # File I/O, chunking, space management
│   └── static/
│       └── index.html   # Web UI
├── docs/
│   └── architecture.md  # System design and data flow
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

---

## License

MIT
