import os
import uuid
import json
import aiofiles

DATA_DIR = os.getenv("DATA_DIR", "./data")


def _space_dir(space: str) -> str:
    return os.path.join(DATA_DIR, space)


def _assets_dir(space: str) -> str:
    return os.path.join(_space_dir(space), "assets")


def _meta_path(space: str, doc_id: str) -> str:
    return os.path.join(_assets_dir(space), f"{doc_id}.json")


def _raw_path(space: str, doc_id: str) -> str:
    return os.path.join(_assets_dir(space), f"{doc_id}.txt")


def space_exists(space: str) -> bool:
    return os.path.isdir(_space_dir(space))


def list_spaces() -> list[str]:
    if not os.path.isdir(DATA_DIR):
        return []
    return [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))]


def create_space(space: str):
    os.makedirs(_assets_dir(space), exist_ok=True)


def delete_space_dir(space: str):
    import shutil
    path = _space_dir(space)
    if os.path.isdir(path):
        shutil.rmtree(path)


def new_doc_id() -> str:
    return uuid.uuid4().hex


def chunk_text(text: str, size: int = 512, overlap: int = 64) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunk = " ".join(words[i : i + size])
        chunks.append(chunk)
        i += size - overlap
    return chunks or [text]


async def save_document(space: str, doc_id: str, text: str, meta: dict):
    os.makedirs(_assets_dir(space), exist_ok=True)
    async with aiofiles.open(_raw_path(space, doc_id), "w") as f:
        await f.write(text)
    async with aiofiles.open(_meta_path(space, doc_id), "w") as f:
        await f.write(json.dumps(meta))


async def load_document(space: str, doc_id: str) -> dict | None:
    raw = _raw_path(space, doc_id)
    meta = _meta_path(space, doc_id)
    if not os.path.exists(raw):
        return None
    async with aiofiles.open(raw) as f:
        text = await f.read()
    async with aiofiles.open(meta) as f:
        metadata = json.loads(await f.read())
    return {"doc_id": doc_id, "text": text, "metadata": metadata}


def delete_document_files(space: str, doc_id: str):
    for path in [_raw_path(space, doc_id), _meta_path(space, doc_id)]:
        if os.path.exists(path):
            os.remove(path)
