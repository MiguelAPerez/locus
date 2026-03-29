import os
import uuid
import json
import shutil
import glob
import aiofiles

DATA_DIR = os.getenv("DATA_DIR", "./data")
GUEST_USER = "guest"


def _space_dir(space: str, username: str = GUEST_USER) -> str:
    return os.path.join(DATA_DIR, username, space)


def _assets_dir(space: str, username: str = GUEST_USER) -> str:
    return os.path.join(_space_dir(space, username), "assets")


def _meta_path(space: str, doc_id: str, username: str = GUEST_USER) -> str:
    return os.path.join(_assets_dir(space, username), f"{doc_id}.json")


def _raw_path(space: str, doc_id: str, username: str = GUEST_USER) -> str:
    return os.path.join(_assets_dir(space, username), f"{doc_id}.txt")


def space_exists(space: str, username: str = GUEST_USER) -> bool:
    return os.path.isdir(_space_dir(space, username))


def list_spaces(username: str = GUEST_USER) -> list[str]:
    user_dir = os.path.join(DATA_DIR, username)
    if not os.path.isdir(user_dir):
        return []
    return [d for d in os.listdir(user_dir) if os.path.isdir(os.path.join(user_dir, d))]


def create_space(space: str, username: str = GUEST_USER):
    os.makedirs(_assets_dir(space, username), exist_ok=True)


def delete_space_dir(space: str, username: str = GUEST_USER):
    path = _space_dir(space, username)
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


async def save_document(space: str, doc_id: str, text: str, meta: dict, username: str = GUEST_USER):
    os.makedirs(_assets_dir(space, username), exist_ok=True)
    async with aiofiles.open(_raw_path(space, doc_id, username), "w") as f:
        await f.write(text)
    async with aiofiles.open(_meta_path(space, doc_id, username), "w") as f:
        await f.write(json.dumps(meta))


async def load_document(space: str, doc_id: str, username: str = GUEST_USER) -> dict | None:
    raw = _raw_path(space, doc_id, username)
    meta = _meta_path(space, doc_id, username)
    if not os.path.exists(raw):
        return None
    async with aiofiles.open(raw) as f:
        text = await f.read()
    async with aiofiles.open(meta) as f:
        metadata = json.loads(await f.read())
    return {"doc_id": doc_id, "text": text, "metadata": metadata}


async def save_original_file(space: str, doc_id: str, content: bytes, filename: str, username: str = GUEST_USER):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    path = os.path.join(_assets_dir(space, username), f"{doc_id}.{ext}")
    async with aiofiles.open(path, "wb") as f:
        await f.write(content)


def delete_document_files(space: str, doc_id: str, username: str = GUEST_USER):
    pattern = os.path.join(_assets_dir(space, username), f"{doc_id}.*")
    for path in glob.glob(pattern):
        os.remove(path)


def migrate_flat_spaces():
    """Move legacy flat space dirs into guest/ subdirectory."""
    if not os.path.isdir(DATA_DIR):
        return
    guest_dir = os.path.join(DATA_DIR, GUEST_USER)
    os.makedirs(guest_dir, exist_ok=True)
    skip = {GUEST_USER, "auth.db", "settings.json", "collections.json"}
    for entry in os.listdir(DATA_DIR):
        if entry in skip:
            continue
        src = os.path.join(DATA_DIR, entry)
        if os.path.isdir(src):
            dest = os.path.join(guest_dir, entry)
            if not os.path.exists(dest):
                shutil.move(src, dest)
