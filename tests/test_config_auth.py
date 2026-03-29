import os
import pytest


def test_auth_enabled_defaults_false(monkeypatch):
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    import importlib
    import app.config as cfg
    importlib.reload(cfg)
    assert cfg.auth_enabled() is False


def test_auth_enabled_true(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    import importlib
    import app.config as cfg
    importlib.reload(cfg)
    assert cfg.auth_enabled() is True


def test_registration_enabled_defaults_false(monkeypatch):
    monkeypatch.delenv("REGISTRATION_ENABLED", raising=False)
    import importlib
    import app.config as cfg
    importlib.reload(cfg)
    assert cfg.registration_enabled() is False


def test_session_hours_defaults_24(monkeypatch):
    monkeypatch.delenv("SESSION_HOURS", raising=False)
    import importlib
    import app.config as cfg
    importlib.reload(cfg)
    assert cfg.session_hours() == 24
