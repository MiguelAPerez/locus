import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

FAKE_VECTOR = [0.1] * 768


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("OLLAMA_URL", "")
    monkeypatch.setenv("EMBED_MODEL", "")
    # Disable auth and bootstrap by default; auth tests opt-in via their own fixtures
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "")
    import app.spaces as spaces_mod
    import app.store as store_mod
    import app.db as db_mod
    monkeypatch.setattr(spaces_mod, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(store_mod, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(db_mod, "DB_PATH", str(tmp_path / "auth.db"))
    store_mod._clients.clear()
    db_mod.init_db()
    return tmp_path


@pytest.fixture
def mock_embeddings():
    with (
        patch("app.embeddings.embed", new_callable=AsyncMock, return_value=FAKE_VECTOR),
        patch("app.embeddings.embed_batch", new_callable=AsyncMock, return_value=[FAKE_VECTOR]),
    ):
        yield


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)
