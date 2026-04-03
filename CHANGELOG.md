## v0.4.0 (2026-04-03)

### Feat

- **auth**: add optional per-user auth system (#4)
- **collections**: group spaces and search across them (#3)

## v0.3.1 (2026-03-21)

### Fix

- ensure /data volume is writable at container startup

## v0.3.0 (2026-03-21)

### Feat

- **parse**: add PDF, image, and audio support with extraction and transcription (#2)
- **logs**: add request logging and logs panel in UI
- **settings**: add API and UI for configuring Ollama URL and embed model

### Fix

- handle empty file uploads and cache chroma clients
- **store**: cache chromadb clients to avoid reloading collections

### Refactor

- **ui**: migrate CSS to Tailwind via standalone CLI (#1)

## v0.2.0 (2026-03-20)

### Feat

- add tests, CI/CD workflows, and commitizen release cycle
