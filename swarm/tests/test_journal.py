"""Durable journal tests (ADR-012 option C)."""

from __future__ import annotations

from pathlib import Path

from swarm.journal import Journal


def _journal(tmp_path: Path) -> Journal:
    return Journal(tmp_path / "journal.db")


def test_append_is_idempotent_by_key(tmp_path: Path):
    j = _journal(tmp_path)
    assert j.append("r1", "step_done", step="step-1", key="step:1", payload={"x": 1}) is True
    assert j.append("r1", "step_done", step="step-1", key="step:1", payload={"x": 2}) is False
    events = j.events("r1")
    assert len(events) == 1 and events[0]["payload"] == {"x": 1}
    # an empty key is a non-idempotent event (NULL, not a shared "")
    assert j.append("r1", "note", payload={"a": 1}) is True
    assert j.append("r1", "note", payload={"a": 2}) is True
    j.close()


def test_claims_leases_and_completion(tmp_path: Path):
    j = _journal(tmp_path)
    j.seed_steps("r1", 2)
    assert j.claim_step("r1", 1, "worker-a") is True
    assert j.claim_step("r1", 1, "worker-b") is False  # a live lease
    assert j.heartbeat("r1", 1, "worker-a") is True
    assert j.heartbeat("r1", 1, "worker-b") is False
    j.complete_step("r1", 1, "step output")
    assert j.claim_step("r1", 1, "worker-b") is False  # done is not re-claimable
    steps = j.steps("r1")
    assert steps[0].status == "done" and steps[1].status == "queued"
    assert j.completed_outputs("r1") == ["step output"]
    j.close()


def test_an_expired_lease_is_claimable(tmp_path: Path):
    j = _journal(tmp_path)
    j.seed_steps("r1", 1)
    assert j.claim_step("r1", 1, "worker-a", ttl=-1) is True
    assert j.claim_step("r1", 1, "worker-b") is True
    j.close()


def test_effects_are_idempotent_and_folded(tmp_path: Path):
    j = _journal(tmp_path)
    assert j.effect("commit:r1:abc") is None
    j.record_effect("commit:r1:abc", "r1", "commit", {"ok": "1", "sha": "deadbeef"})
    assert j.effect("commit:r1:abc") == {"ok": "1", "sha": "deadbeef"}
    j.append("r1", "run_status", key="status:green", payload={"status": "green"})
    fold = j.fold("r1")
    assert fold["status"] == "green"
    assert fold["effects"][0]["key"] == "commit:r1:abc"
    j.close()


def test_runs_are_isolated(tmp_path: Path):
    j = _journal(tmp_path)
    j.seed_steps("r1", 1)
    j.complete_step("r1", 1, "a")
    assert j.completed_outputs("r2") == []
    j.close()


def test_the_flow_uses_the_journal_for_steps_and_commit_effects():
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert "Journal(" in source
    assert "complete_step(" in source
    assert "commit:" in source  # effect key
    assert "record_effect(" in source


def test_the_journal_crosses_threads(tmp_path: Path):
    """CrewAI runs flow listeners in a worker thread; SQLite must not refuse it."""
    import threading

    j = _journal(tmp_path)
    j.seed_steps("r1", 1)
    j.complete_step("r1", 1, "a")
    out: list[list[str]] = []

    def worker() -> None:
        out.append(j.completed_outputs("r1"))

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert out == [["a"]]
    j.close()
