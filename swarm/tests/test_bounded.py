"""Crew wall-clock bound tests (022): a hung call cannot eat the task."""

from __future__ import annotations

import time

import pytest

from swarm import bounded


def test_a_fast_call_returns_its_value():
    finished, value = bounded.run_bounded(lambda: 42, 1.0)
    assert finished is True and value == 42


def test_a_hung_call_is_reported_as_unfinished():
    started = time.monotonic()
    finished, value = bounded.run_bounded(lambda: time.sleep(5), 0.1)
    assert finished is False and value is None
    assert time.monotonic() - started < 1.0


def test_an_exception_propagates():
    def boom():
        raise RuntimeError("transport down")

    with pytest.raises(RuntimeError):
        bounded.run_bounded(boom, 1.0)


def test_zero_means_no_bound():
    assert bounded.run_bounded(lambda: "ok", 0) == (True, "ok")


def test_the_flow_bounds_a_crew_call():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert "bounded.run_bounded(" in source
    assert "crew exceeded" in source
