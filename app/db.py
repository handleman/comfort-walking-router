import os

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured; cannot connect")
    # Imported lazily: alembic/psycopg are runtime deps that are not installed
    # in every environment (tests skip when DATABASE_URL is unset).
    import psycopg  # type: ignore[import-not-found]

    return psycopg.connect(DATABASE_URL)


def run_migrations():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured; cannot run migrations")
    import alembic.command  # type: ignore[import-not-found]
    import alembic.config  # type: ignore[import-not-found]

    config = alembic.config.Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    alembic.command.upgrade(config, "head")
