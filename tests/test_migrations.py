"""Migration tests (spec 005-saved-routes, task T2, AC-3).

These tests exercise the real database via DATABASE_URL and are skipped
when it is not configured, mirroring tests/test_db.py.
"""

import os
import re
from pathlib import Path

import pytest

import app.db

skipif_no_db = pytest.mark.skipif(
    os.getenv("DATABASE_URL") is None, reason="DATABASE_URL not set"
)

VERSIONS_DIR = Path(app.db.__file__).parent / "migrations" / "versions"

# Minimal column expectations; only checked for tables that exist.
EXPECTED_COLUMNS = {
    "routes": {"id"},
    "user_preferences": {"user_id"},
    "weather_cache": {"key"},
}


def _expected_tables():
    """Table names declared via create_table(...) in migration versions."""
    tables = set()
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        tables |= set(
            re.findall(r"create_table\(\s*['\"]([^'\"]+)['\"]", path.read_text())
        )
    return tables


def _inspector():
    from sqlalchemy import create_engine, inspect

    return inspect(create_engine(app.db.DATABASE_URL))


def _user_tables(inspector):
    return set(inspector.get_table_names())


def _alembic_config():
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(VERSIONS_DIR.parent))
    cfg.set_main_option("sqlalchemy.url", app.db.DATABASE_URL)
    return cfg


@pytest.fixture()
def clean_db():
    from alembic import command

    command.downgrade(_alembic_config(), "base")
    yield
    command.downgrade(_alembic_config(), "base")


@skipif_no_db
def test_upgrade_creates_all_tables(clean_db):
    from alembic import command

    inspector = _inspector()
    assert not (_expected_tables() & _user_tables(inspector))

    command.upgrade(_alembic_config(), "head")

    assert _expected_tables() <= _user_tables(_inspector())


@skipif_no_db
def test_downgrade_drops_all_tables(clean_db):
    from alembic import command

    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    assert _expected_tables() <= _user_tables(_inspector())

    command.downgrade(cfg, "base")

    assert not (_expected_tables() & _user_tables(_inspector()))


@skipif_no_db
def test_tables_have_expected_columns(clean_db):
    from alembic import command

    command.upgrade(_alembic_config(), "head")

    inspector = _inspector()
    for table in _expected_tables():
        columns = {col["name"] for col in inspector.get_columns(table)}
        assert columns, f"table {table} has no columns"
        for expected in EXPECTED_COLUMNS.get(table, set()):
            assert expected in columns, f"table {table} missing column {expected}"
