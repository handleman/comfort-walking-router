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
    """Run migrations against the database using a psycopg connection."""
    import psycopg  # type: ignore[import-not-found]

    with psycopg.connect(_get_url()) as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table="alembic_version",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
