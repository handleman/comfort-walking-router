"""Shared pytest fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _mapbox_token(monkeypatch):
    """Keep the suite hermetic: inject a dummy Mapbox token for every test."""
    monkeypatch.setenv("MAPBOX_TOKEN", "test-dummy-mapbox-token")
