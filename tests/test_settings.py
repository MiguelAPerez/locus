import pytest


def test_get_settings_defaults(client):
    r = client.get("/settings")
    assert r.status_code == 200
    body = r.json()
    assert "ollama_url" in body
    assert "embed_model" in body
    assert body["ollama_url"]["source"] == "default"
    assert body["embed_model"]["source"] == "default"
    assert body["ollama_url"]["readonly"] is False
    assert body["embed_model"]["readonly"] is False


def test_save_and_read_settings(client):
    r = client.post("/settings", json={"ollama_url": "http://myhost:11434", "embed_model": "mxbai-embed-large"})
    assert r.status_code == 200
    body = r.json()
    assert body["ollama_url"]["value"] == "http://myhost:11434"
    assert body["ollama_url"]["source"] == "saved"
    assert body["embed_model"]["value"] == "mxbai-embed-large"
    assert body["embed_model"]["source"] == "saved"

    # persisted across a fresh GET
    r2 = client.get("/settings")
    assert r2.json()["ollama_url"]["value"] == "http://myhost:11434"


def test_env_vars_take_priority_and_are_readonly(client, monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://env-host:11434")
    monkeypatch.setenv("EMBED_MODEL", "env-model")

    r = client.get("/settings")
    body = r.json()
    assert body["ollama_url"]["value"] == "http://env-host:11434"
    assert body["ollama_url"]["source"] == "env"
    assert body["ollama_url"]["readonly"] is True
    assert body["embed_model"]["readonly"] is True


def test_post_settings_ignores_readonly_fields(client, monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://env-host:11434")

    r = client.post("/settings", json={"ollama_url": "http://should-be-ignored:11434", "embed_model": "new-model"})
    body = r.json()
    # env var value is unchanged
    assert body["ollama_url"]["value"] == "http://env-host:11434"
    # non-env field is updated
    assert body["embed_model"]["value"] == "new-model"
