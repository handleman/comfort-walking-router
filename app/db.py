import os

DATABASE_URL = os.getenv("DATABASE_URL")


def sqlalchemy_url() -> str:
    """The DATABASE_URL in SQLAlchemy form (`postgresql+psycopg://`).

    SQLAlchemy 2 maps a bare `postgresql://` to psycopg2, which this project does
    not install (it uses psycopg 3). Alembic and the tests go through here.
    """
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured; cannot connect")
    if DATABASE_URL.startswith("postgresql://"):
        return "postgresql+psycopg://" + DATABASE_URL.removeprefix("postgresql://")
    return DATABASE_URL


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured; cannot connect")
    # Imported lazily: alembic/psycopg are runtime deps that are not installed
    # in every environment (tests skip when DATABASE_URL is unset).
    import psycopg  # type: ignore[import-not-found]

    return psycopg.connect(DATABASE_URL)


def run_migrations():
    """Upgrade the schema to head.

    The scripts live in `app/migrations/` and there is no `alembic.ini` in the
    repo, so the config is built in code (as `tests/test_migrations.py` does).
    The old `Config("alembic.ini")` raised "No 'script_location' key" the first
    time it was run against a real database (2026-11-15).
    """
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured; cannot run migrations")
    from pathlib import Path

    import alembic.command  # type: ignore[import-not-found]
    import alembic.config  # type: ignore[import-not-found]

    config = alembic.config.Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    config.set_main_option("sqlalchemy.url", sqlalchemy_url())
    alembic.command.upgrade(config, "head")
