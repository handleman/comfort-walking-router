"""Shared pytest fixtures."""

import os

import pytest

# The app builds its Mapbox provider at import time (`app/main.py`), so the
# token must exist before the first test module is imported — a fixture is
# too late (fixtures run after collection). Set it here, at import time, so
# the suite is hermetic: `make test` works with or without a shell that
# exports MAPBOX_TOKEN.
os.environ.setdefault("MAPBOX_TOKEN", "test-dummy-mapbox-token")


@pytest.fixture(autouse=True)
def _mapbox_token(monkeypatch):
    """Keep the suite hermetic: inject a dummy Mapbox token for every test."""
    monkeypatch.setenv("MAPBOX_TOKEN", "test-dummy-mapbox-token")
