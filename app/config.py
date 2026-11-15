"""Configuration accessors for Mapbox routing."""

import os

from . import env as _env  # noqa: F401 - loads .env before the env reads


def get_mapbox_token() -> str:
    """Return the Mapbox access token from the environment.

    Raises:
        RuntimeError: If MAPBOX_TOKEN is missing or empty.
    """
    token = os.environ.get("MAPBOX_TOKEN", "")
    if not token:
        raise RuntimeError(
            "MAPBOX_TOKEN is missing or empty: export MAPBOX_TOKEN "
            "to a valid Mapbox access token before using Mapbox routing."
        )
    return token
