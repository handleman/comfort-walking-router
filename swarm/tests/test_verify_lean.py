"""Lean verifier tests (022 T5): docs-only small diffs may skip; nothing else."""

from __future__ import annotations

from pathlib import Path

from swarm import verify


def test_the_flag_is_off_by_default_and_accepts_truthy():
    assert verify.lean_enabled({}) is False
    assert verify.lean_enabled({"SWARM_VERIFY_LEAN": "1"}) is True
    assert verify.lean_enabled({"SWARM_VERIFY_LEAN": "true"}) is True
    assert verify.lean_enabled({"SWARM_VERIFY_LEAN": "0"}) is False


def test_a_small_docs_only_delta_is_low_risk():
    assert verify.low_risk(["docs/runbooks/overnight-runs.md"], "10\t2\tdocs/x.md") is True
    assert verify.low_risk(["README.md"], "3\t1\tREADME.md") is True


def test_tests_are_never_low_risk():
    """A test with a wrong expectation is the 014-T7 class the verifier owns."""
    assert verify.low_risk(["tests/test_x.py"], "1\t1\ttests/test_x.py") is False
    assert verify.low_risk(["frontend/src/x.test.ts"], "1\t1\tx") is False


def test_implementation_paths_are_never_low_risk():
    assert verify.low_risk(["app/main.py"], "1\t1\tapp/main.py") is False
    assert verify.low_risk(["frontend/src/App.svelte"], "1\t1\tx") is False


def test_a_big_or_wide_docs_delta_is_not_low_risk():
    assert verify.low_risk(["docs/a.md", "docs/b.md", "docs/c.md", "docs/d.md", "docs/e.md"]) is False
    assert verify.low_risk(["docs/a.md"], "150\t100\tdocs/a.md") is False
    assert verify.low_risk([]) is False


def test_the_flow_skips_and_records_the_reason():
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert "verify.lean_enabled() and self._lean_delta()" in source
    assert '"verdict": "skipped"' in source
    assert "skipped_reason" in source
