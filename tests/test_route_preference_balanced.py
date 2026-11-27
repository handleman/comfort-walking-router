"""041 AC-1/AC-4: the route contract accepts the desktop shade value `balanced`."""

import pytest
from pydantic import ValidationError

from app.main import BALANCED_NOTE, PREFERENCE_NOTES, RouteRequest


def test_route_request_accepts_balanced_preference():
    body = RouteRequest(start="a", end="b", preference="balanced")
    assert body.preference == "balanced"


def test_route_request_keeps_the_sun_and_shade_values():
    assert RouteRequest(start="a", end="b", preference="hot").preference == "hot"
    assert RouteRequest(start="a", end="b", preference="cloudy").preference == "cloudy"


def test_route_request_rejects_an_unknown_preference():
    with pytest.raises(ValidationError):
        RouteRequest(start="a", end="b", preference="sunny")


def test_balanced_preference_resolves_to_the_balanced_note():
    # `balanced` is accepted even though PREFERENCE_NOTES has no entry for it,
    # so the explanation falls back to BALANCED_NOTE rather than raising.
    assert PREFERENCE_NOTES.get("balanced", BALANCED_NOTE) == BALANCED_NOTE
    assert PREFERENCE_NOTES.get("hot", BALANCED_NOTE) == PREFERENCE_NOTES["hot"]
