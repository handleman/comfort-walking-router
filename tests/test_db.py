import os

import pytest

import app.db

skipif_no_db = pytest.mark.skipif(
    os.getenv("DATABASE_URL") is None, reason="DATABASE_URL not set"
)


@skipif_no_db
def test_get_connection_requires_url(monkeypatch):
    monkeypatch.setattr(app.db, "DATABASE_URL", None)
    with pytest.raises(RuntimeError):
        app.db.get_connection()


@skipif_no_db
def test_run_migrations_requires_url(monkeypatch):
    monkeypatch.setattr(app.db, "DATABASE_URL", None)
    with pytest.raises(RuntimeError):
        app.db.run_migrations()
