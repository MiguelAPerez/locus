# Plan: Space Collections

## Context

Locus currently treats every space as a fully isolated island — search is scoped to exactly one space. Users need a way to group related spaces into **collections** so they can search across multiple spaces in a single query, and manage those groups without destroying the underlying spaces.

---

## Approach

Collections are stored as a simple JSON file (`/data/collections.json`) — consistent with how `settings.json` already works. No SQL, no migrations. A new `collections.py` module handles the file I/O, and new API routes expose CRUD + cross-space search. The frontend sidebar gains a Collections section alongside the existing Spaces list.

---

## Data Model

**`/data/collections.json`**
```json
{
  "my_research": {
    "spaces": ["papers", "notes", "web_clips"]
  },
  "work": {
    "spaces": ["meetings", "docs"]
  }
}
```

---

## Files to Create / Modify

| File | Change |
|------|--------|
| `app/collections.py` | **New** — file I/O + business logic |
| `app/main.py` | Add 7 new routes |
| `app/static/index.html` | Add Collections UI to sidebar + workspace |
| `tests/test_collections.py` | **New** — route tests |

---

## Backend: `app/collections.py` (new)

```python
COLLECTIONS_FILE = DATA_DIR / "collections.json"

def load_collections() -> dict
def save_collections(data: dict) -> None
def list_collections() -> list[str]
def get_collection(name: str) -> dict          # raises KeyError if missing
def create_collection(name: str) -> None       # raises ValueError if exists
def delete_collection(name: str) -> None
def add_space(collection: str, space: str) -> None
def remove_space(collection: str, space: str) -> None
```

Normalize collection names the same way spaces are normalized (lowercase, underscores). Reuse the `normalize_name()` logic already in `app/spaces.py`.

---

## Backend: New Routes in `app/main.py`

```
GET    /collections                           → list all collections
POST   /collections            {name}         → create collection
GET    /collections/{name}                    → get collection (name + spaces list)
DELETE /collections/{name}                    → delete collection (not the spaces)
POST   /collections/{name}/spaces/{space}     → add space to collection
DELETE /collections/{name}/spaces/{space}     → remove space from collection
GET    /collections/{name}/search?q=&k=&full= → cross-space search
```

### Cross-Space Search Logic

1. Validate collection exists; validate it has at least 1 space
2. Call `embed(q)` **once**
3. For each space in the collection, call `store.search(space, embedding, k)` — collect all results, annotate each with `"space": space_name`
4. Sort merged list by `score` descending
5. Return top `k` results

Each result object gets a `"space"` field added:
```json
{
  "chunk_id": "abc__chunk0",
  "doc_id": "abc",
  "text": "...",
  "score": 0.92,
  "space": "papers",
  "metadata": {...}
}
```

If `full=true`, fetch full document text from each result's space (reuse existing `spaces.load_document()` logic).

---

## Frontend: `app/static/index.html`

### Sidebar

Add a **Collections** section below the Spaces list. Same visual pattern: list of items with delete (✕) buttons, plus an input + button to create new ones.

```
SPACES
  papers       ✕
  notes        ✕
  [new space ] [+]

COLLECTIONS
  my_research  ✕
  work         ✕
  [new coll  ] [+]
```

### Collection Workspace

When a collection is selected (instead of a space), show a different workspace view with two panels:

**Members panel** — shows which spaces belong to the collection with an [Add space] dropdown (lists existing spaces not yet in the collection) and remove (✕) buttons per member space.

**Search panel** — identical to the existing space search UI, but hits `GET /collections/{name}/search`. Results get an extra tag showing which space the result came from (styled like the existing `doc_type` tags).

A breadcrumb or label at the top makes it clear whether you're in a space or a collection context.

---

## Reuse Opportunities

- `spaces.normalize_name()` — normalize collection names the same way (`app/spaces.py`)
- `store.search()` — already returns the correct result shape; just call it per-space (`app/store.py`)
- `embed()` from `app/embeddings.py` — call once, reuse vector across all spaces
- `spaces.load_document()` — reuse for `full=true` mode per result's space
- Existing space search result rendering in `index.html` — extend rather than duplicate

---

## Tests: `tests/test_collections.py`

- CRUD: create, list, get, delete collection
- Membership: add space, remove space, duplicate add is a no-op or error, remove nonexistent is graceful
- Cross-space search: mock embeddings (reuse `mock_embeddings` fixture), ensure results are merged and sorted, ensure `space` field is present
- Edge cases: search on empty collection returns 400, search on collection with deleted space skips that space gracefully

---

## Verification

1. `pytest tests/test_collections.py -v` — all new tests pass
2. Full test suite: `pytest` — no regressions
3. Manual smoke test:
   - Create 2–3 spaces, ingest different docs in each
   - Create a collection, add those spaces
   - Run a cross-space search, verify results from multiple spaces are returned with `space` field
   - Remove a space from the collection, verify it's excluded from subsequent searches
   - Delete the collection, verify spaces still exist
