"""Tests for configuration accessors."""

import pytest

from app.config import get_mapbox_token


def test_get_mapbox_token_returns_token_when_set(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN", "pk.test-token-123")
    assert get_mapbox_token() == "pk.test-token-123"


def test_get_mapbox_token_raises_when_missing(monkeypatch):
    monkeypatch.delenv("MAPBOX_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="MAPBOX_TOKEN is missing or empty"):
        get_mapbox_token()


def test_get_mapbox_token_raises_when_empty(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN", "")
    with pytest.raises(RuntimeError, match="MAPBOX_TOKEN is missing or empty"):
        get_mapbox_token()
