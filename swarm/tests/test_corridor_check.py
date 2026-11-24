"""050: the corridor-check probe is deterministic when the fetch is injected."""

from __future__ import annotations

from swarm import corridor_check


def test_probe_reports_the_serving_mirror():
    calls: list[str] = []

    def fake_fetch(url, query=None):
        calls.append(url)
        if url == corridor_check.MIRRORS[0]:
            raise RuntimeError("502 all query workers are busy")
        return [{"geometry": {"type": "LineString"}, "properties": {"highway": "footway"}}]

    result = corridor_check.probe(fetch=fake_fetch)

    assert result["corridor"] is True
    assert result["serving_mirror"] == corridor_check.MIRRORS[1]
    assert result["mirrors"][0]["ok"] is False
    assert result["mirrors"][1]["ok"] is True
    # Stops at the first mirror that answers.
    assert calls == list(corridor_check.MIRRORS[:2])


def test_probe_all_mirrors_failing_is_a_data_gap():
    def fake_fetch(url, query=None):
        raise TimeoutError(f"timed out: {url}")

    result = corridor_check.probe(fetch=fake_fetch)

    assert result["corridor"] is False
    assert result["serving_mirror"] is None
    assert [m["mirror"] for m in result["mirrors"]] == list(corridor_check.MIRRORS)
    assert all(m["ok"] is False for m in result["mirrors"])


def test_probe_prefers_the_first_healthy_mirror():
    def fake_fetch(url, query=None):
        return [{"geometry": {"type": "LineString"}, "properties": {}}]

    result = corridor_check.probe(fetch=fake_fetch)

    assert result["serving_mirror"] == corridor_check.MIRRORS[0]
    assert len(result["mirrors"]) == 1  # stopped after the first success
