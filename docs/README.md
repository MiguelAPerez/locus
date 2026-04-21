
# Locus Documentation

## Project structure

```markdown
.
├── app/
│   ├── main.py          # FastAPI app and all routes
│   ├── embeddings.py    # Ollama embedding client
│   ├── extractors.py    # PDF, image OCR, and audio transcription
│   ├── store.py         # ChromaDB vector store wrapper
│   ├── spaces.py        # File I/O, chunking, space management
│   └── static/
│       └── index.html   # Web UI
├── tests/               # pytest test suite
├── .github/workflows/
│   ├── ci.yml           # Run tests on push / PR
│   └── release.yml      # Build & push Docker image on tag
├── docs/
│   ├── architecture.md  # System design and data flow
│   └── auth.md          # Auth setup and API reference
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml       # Commitizen config & version
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

## Development

### Local (dev)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export OLLAMA_URL=http://localhost:11434
export DATA_DIR=./data

uvicorn app.main:app --reload
```

### Running tests

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v --cov=app
```

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

# Bulk upload multiple files
curl -s -X POST $BASE/spaces/research/documents/bulk \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.txt" \
  -F "source=batch-upload" | jq

# Semantic search
curl -s "$BASE/spaces/research/search?q=cellular+energy&k=3" | jq

# Fetch full document
curl -s "$BASE/spaces/research/documents/{doc_id}" | jq

# List spaces
curl -s $BASE/spaces | jq

# Delete a space
curl -s -X DELETE $BASE/spaces/research | jq

# Create a collection and add spaces to it
curl -s -X POST $BASE/collections \
  -H 'Content-Type: application/json' \
  -d '{"name": "science"}' | jq

curl -s -X POST $BASE/collections/science/spaces/research | jq

# Search across all spaces in the collection
curl -s "$BASE/collections/science/search?q=cellular+energy&k=3" | jq
```

---

### Releases

Releases are driven by [Commitizen](https://commitizen-tools.github.io/commitizen/) using conventional commits.

```bash
# bump version, update CHANGELOG, create tag
cz bump

# push the tag to trigger the release workflow
git push origin main --tags
```

The release workflow builds and pushes the Docker image to `ghcr.io/miguelaperez/locus:<tag>` and `ghcr.io/miguelaperez/locus:latest`.

---
