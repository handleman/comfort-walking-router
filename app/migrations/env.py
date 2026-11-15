"""Alembic environment for app migrations.

Reads DATABASE_URL (via app.db) and configures online/offline migration
runs using a psycopg connection.
"""

from alembic import context

import app.db

config = context.config

target_metadata = None  # migrations are hand-written SQL, no autogenerate


def _get_url() -> str:
    url = app.db.DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL is not configured; cannot run migrations")
    return url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection."""
    context.configure(url=_get_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the database using a SQLAlchemy connection.

    Alembic needs a SQLAlchemy `Connection` (it reads `connection.dialect`); a raw
    psycopg connection raised `'Connection' object has no attribute 'dialect'` the
    first time this ran against a real database (2026-11-15).
    """
    from sqlalchemy import create_engine  # type: ignore[import-not-found]

    from app.db import sqlalchemy_url

    engine = create_engine(sqlalchemy_url())
    # `engine.begin()`, not `connect()`: SQLAlchemy 2 does not commit a plain
    # connection on exit, so the DDL (and the version row) were rolled back and
    # `upgrade head` reported success with zero tables (2026-11-15).
    with engine.begin() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table="alembic_version",
        )
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
