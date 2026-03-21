# Contributing to Locus

Thanks for your interest in contributing. Locus is intentionally small — the goal is to keep it simple, so please consider whether a change adds real value before opening a PR. Our intent is to keep an open source and self-hosted tool that anyone can understand and modify without needing to learn a complex codebase or architecture.

---

## Getting started

### Prerequisites

- Python 3.12+
- An Ollama instance with an embedding model pulled (e.g. `nomic-embed-text`)
- Docker + Docker Compose (optional, for integration testing)

### Local setup

```bash
git clone <repo-url>
cd datasources-manager

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export OLLAMA_URL=http://localhost:11434
export DATA_DIR=./data

uvicorn app.main:app --reload
```

The API is at `http://localhost:8000` and the auto-generated OpenAPI docs at `http://localhost:8000/docs`.

---

## Project layout

| File | Responsibility |
|---|---|
| `app/main.py` | Route definitions only — keep business logic out |
| `app/embeddings.py` | Ollama HTTP client — one concern: get vectors |
| `app/store.py` | ChromaDB interactions — upsert, search, delete |
| `app/spaces.py` | File I/O, text chunking, space directory management |
| `app/static/index.html` | Self-contained UI — no build step, no frameworks |

---

## Guidelines

### Keep it simple

Locus is a tool, not a platform. Avoid adding abstractions for hypothetical future needs. If you can solve the problem with less code, do that.

### One module, one concern

Each file has a single responsibility. Don't reach across layers — routes call spaces/store/embeddings, not each other.

### No new dependencies without discussion

The dependency list is short on purpose. If you think a new package is necessary, open an issue first.

### API changes need backward compatibility

If you're changing an existing endpoint's shape (request or response), it must remain compatible with existing curl calls. Deprecations go through a discussion first.

### UI changes

The UI lives in a single `index.html` with no build tooling. Keep it that way. Vanilla JS and CSS only.

---

## Submitting changes

1. Fork the repo and create a branch from `main`
2. Make your change — keep commits focused and descriptive
3. Test manually with curl or the UI against a real Ollama instance
4. Open a pull request with a clear description of what and why

### PR checklist

- [ ] Works end-to-end with `docker compose up`
- [ ] New endpoints documented in `README.md`
- [ ] No new dependencies added without justification
- [ ] `app/static/index.html` still works without a build step

---

## Reporting issues

Open a GitHub issue with:
- What you expected to happen
- What actually happened
- The curl command or steps to reproduce
- Locus version / commit hash

---

## Code style

- Python: follow PEP 8, use type hints where they aid clarity
- No linter config is enforced — just keep it readable
- Async where I/O is involved, sync otherwise
