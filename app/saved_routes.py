"""Saved routes API (spec 005): bearer-auth CRUD over the routes repository.

Every endpoint resolves ``holder_id`` from the ``Authorization: Bearer`` token
via ``auth.hash_token`` + the repositories layer, so a holder can only ever
see and mutate their own saved routes (AC-1, AC-2, AC-6).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.auth import hash_token
from app.db import get_connection
from app.repositories import routes as routes_repo

router = APIRouter(prefix="/saved-routes", tags=["saved-routes"])

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Missing or invalid bearer token",
    headers={"WWW-Authenticate": "Bearer"},
)

# Candidate resolver names on the prefs repository, tried in order.
_TOKEN_RESOLVERS: tuple[str, ...] = (
    "get_holder_id_by_token_hash",
    "holder_id_for_token_hash",
    "resolve_holder_id",
    "get_holder_id",
)

_LOOKUP_SQL = "SELECT holder_id FROM tokens WHERE token_hash = %s"


def _lookup_holder_id(token_hash: str) -> str | None:
    """Resolve holder_id for a token hash via repositories, else direct lookup."""
    for name in _TOKEN_RESOLVERS:
        candidate: Callable[[str], Any] | None = getattr(
            routes_repo, name, None
        ) or getattr(_prefs_repo(), name, None)
        if candidate is not None:
            holder_id = candidate(token_hash)
            return str(holder_id) if holder_id else None
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(_LOOKUP_SQL, (token_hash,))
        row = cur.fetchone()
    return str(row[0]) if row else None


def _prefs_repo() -> Any:
    from app.repositories import prefs

    return prefs


def bearer_holder(
    authorization: str | None = Header(default=None),
) -> str:
    """FastAPI dependency: bearer token -> holder_id (401 when invalid)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _UNAUTHORIZED
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise _UNAUTHORIZED
    holder_id = _lookup_holder_id(hash_token(token))
    if not holder_id:
        raise _UNAUTHORIZED
    return holder_id


class SavedRoutePayload(BaseModel):
    request: dict[str, Any]
    response: dict[str, Any]


@router.post("", status_code=status.HTTP_201_CREATED)
def save_route(
    payload: SavedRoutePayload,
    holder_id: str = Depends(bearer_holder),
) -> dict[str, Any]:
    """Save (upsert) a route for the authenticated holder."""
    route_id = str(uuid.uuid4())
    return routes_repo.save_route(
        holder_id, route_id, payload.request, payload.response
    )


@router.get("")
def list_saved_routes(
    holder_id: str = Depends(bearer_holder),
) -> list[dict[str, Any]]:
    """List the authenticated holder's saved routes only."""
    return routes_repo.list_routes(holder_id)


class PrefsPayload(BaseModel):
    default_preference: dict[str, Any] | None = None


@router.get("/prefs")
def get_saved_route_prefs(
    holder_id: str = Depends(bearer_holder),
) -> dict[str, Any]:
    """Return the authenticated holder's saved preferences (AC-6)."""
    prefs = _prefs_repo().get_prefs(holder_id)
    if prefs is None:
        return {"holder_id": holder_id, "default_preference": None}
    return prefs


@router.put("/prefs")
def update_saved_route_prefs(
    payload: PrefsPayload,
    holder_id: str = Depends(bearer_holder),
) -> dict[str, Any]:
    """Upsert the authenticated holder's saved preferences (AC-6)."""
    return _prefs_repo().update_prefs(holder_id, payload.model_dump())


@router.get("/{route_id}")
def recall_saved_route(
    route_id: str,
    holder_id: str = Depends(bearer_holder),
) -> dict[str, Any]:
    """Recall one saved route; 404 when missing or owned by another holder."""
    route = routes_repo.recall_route(holder_id, route_id)
    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Saved route not found"
        )
    return route


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_route(
    route_id: str,
    holder_id: str = Depends(bearer_holder),
) -> None:
    """Delete one saved route; 404 when missing or owned by another holder."""
    if not routes_repo.delete_route(holder_id, route_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Saved route not found"
        )
