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


# 001 AC-2: /route now asks Overpass for corridor comfort factors. Unit tests
# must never touch the network, so the default is the recorded corridor; a test
# that needs the real code path asks for the `real_corridor` fixture.
from app import comfort as _comfort
from app import fixtures as _fixtures
from app.providers import overpass as _overpass

_REAL_CORRIDOR = _comfort.corridor_data


def _recorded_corridor(geometry, *, margin_m=_comfort.CORRIDOR_MARGIN_M):
    """The recorded corridor: factors plus the fixture's positioned trees."""
    counts = _overpass.count_features(_fixtures.recorded_corridor_elements())
    return {
        "factors": _comfort.factors_from_counts(counts),
        "feature_points": _comfort.feature_points(
            geometry, _fixtures.recorded_corridor_features(geometry)
        ),
    }


@pytest.fixture(autouse=True)
def _no_overpass(monkeypatch):
    # `/route` asks for both halves in one call (028 AC-2); stubbing the pair is
    # what keeps the suite off the network.
    monkeypatch.setattr(_comfort, "corridor_data", _recorded_corridor)


@pytest.fixture
def real_corridor(monkeypatch):
    """Opt back into the real corridor fetch (still network-free when stubbed)."""
    monkeypatch.setattr(_comfort, "corridor_data", _REAL_CORRIDOR)
    return _REAL_CORRIDOR


@pytest.fixture(scope="session", autouse=True)
def _db_schema():
    """A live database starts at head; skipped entirely without DATABASE_URL.

    The repositories assume the tables exist, and the migration tests move the
    schema around; one upgrade here keeps the two stories compatible.
    """
    if not os.getenv("DATABASE_URL"):
        yield
        return
    from app import db

    db.run_migrations()
    yield
