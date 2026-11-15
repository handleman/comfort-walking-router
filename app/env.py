"""Load the repo `.env` for the app (keys, tokens, DATABASE_URL).

`app/config.py` and `app/db.py` read `os.environ` at import, and the swarm's
`make` targets export `DATABASE_URL` themselves, but a `MAPBOX_TOKEN` that the
operator put in `.env` never reached the app: "the token is in place" and a 422
from the provider were both true (2026-11-15). python-dotenv does not override
an existing variable, so tests and explicit exports still win.
"""

from __future__ import annotations

from pathlib import Path

try:  # python-dotenv is a runtime dependency of the swarm venv, optional here
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # pragma: no cover - a clean checkout without dotenv
    pass
