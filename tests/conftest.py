import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

FAKE_VECTOR = [0.1] * 768


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import app.spaces as spaces_mod
    import app.store as store_mod
    monkeypatch.setattr(spaces_mod, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(store_mod, "DATA_DIR", str(tmp_path))
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
