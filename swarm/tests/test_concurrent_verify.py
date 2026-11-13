"""Concurrent verifier∥QA tests (022 T4): only the read-only pass overlaps."""

from __future__ import annotations

import time
import types
from pathlib import Path

from swarm import verify
from swarm.flow import SwarmFlow


def test_the_flag_is_off_by_default_and_accepts_truthy():
    assert verify.concurrent_enabled({}) is False
    assert verify.concurrent_enabled({"SWARM_VERIFY_CONCURRENT": "1"}) is True
    assert verify.concurrent_enabled({"SWARM_VERIFY_CONCURRENT": "true"}) is True
    assert verify.concurrent_enabled({"SWARM_VERIFY_CONCURRENT": "0"}) is False


def _stub(*, precheck=None, phase=None, order=None, sleep=0.0):
    state = types.SimpleNamespace(verifier={})
    events = order if order is not None else []
    stub = types.SimpleNamespace(
        state=state,
        _pre_qa_style=lambda: events.append("style"),
    )

    def _pre(task, kick):
        time.sleep(sleep)
        events.append("precheck")
        if precheck is None:
            return {"verdict": "pass", "blocked": False}
        if isinstance(precheck, Exception):
            raise precheck
        return precheck

    def _phase(task, kick):
        events.append("corrections")
        return True if phase is None else phase

    stub._verify_precheck = _pre
    stub._verify_phase = _phase
    stub._verify_concurrently = types.MethodType(SwarmFlow._verify_concurrently, stub)
    return stub


def test_qa_and_the_verifier_overlap_in_time():
    order: list[str] = []
    stub = _stub(sleep=0.2, order=order)

    def review():
        time.sleep(0.2)
        order.append("review")
        return True

    started = time.monotonic()
    reviewed, ok = stub._verify_concurrently(None, None, review)
    elapsed = time.monotonic() - started
    assert reviewed is True and ok is True
    assert elapsed < 0.35  # max, not sum
    assert set(order) == {"style", "precheck", "review"}


def test_corrections_run_after_qa_when_the_precheck_blocks():
    order: list[str] = []
    stub = _stub(precheck={"verdict": "blocked", "blocked": True}, order=order)

    def review():
        order.append("review")
        return True

    reviewed, ok = stub._verify_concurrently(None, None, review)
    assert (reviewed, ok) == (True, True)
    assert order.index("review") < order.index("corrections")
    assert stub.state.verifier["blocked"] is True


def test_a_verifier_crash_is_advisory_not_a_run_failure():
    stub = _stub(precheck=RuntimeError("transport down"))
    reviewed, ok = stub._verify_concurrently(None, None, lambda: True)
    assert (reviewed, ok) == (True, True)
    assert stub.state.verifier["verdict"] == "error"
    assert "transport down" in stub.state.verifier["note"]


def test_the_flow_only_overlaps_when_enabled_and_corrections_stay_sequential():
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert "_verify.enabled() and _verify.concurrent_enabled()" in source
    assert "self._verify_concurrently(" in source
    # formatting runs before the thread starts
    assert "self._pre_qa_style()\n        thread = threading.Thread" in source
