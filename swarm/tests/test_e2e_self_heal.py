"""Self-healing e2e (027): triage, roster, weakening guard and the phase stops."""

from __future__ import annotations

import json
import types
from pathlib import Path

from swarm import e2e_guard, e2e_triage, inner

BAD_TAIL = """Running 4 tests using 4 workers

  ✘  1 [chromium] › e2e/walk-mode.spec.ts:17:1 › walk mode shows a marker at the origin
  ✓  2 [chromium] › e2e/walk-mode.spec.ts:31:1 › drift
  1) e2e/walk-mode.spec.ts:17:1
   Error: locator.click: Timeout 5000ms exceeded.
    - waiting for locator('button.walk-start')
"""

ASSERT_TAIL = """  ✘  1 [chromium] › e2e/search.spec.ts:5:1 › shows the route
  1) e2e/search.spec.ts:5:1
   Error: expect(received).toContainText(expected)
   Expected substring: "Arrived!"
"""


def _exec(tail: str, *, exit_code: int = 1, digest: str = "h") -> dict:
    return {
        "agent": "QA Gatekeeper",
        "argv": ["npm", "--prefix", "frontend", "run", "test:e2e"],
        "exit": exit_code,
        "tail": tail,
        "changed_after": digest,
        "at": "2026-11-15T00:00:00",
        "duration_ms": 5,
    }


# ---- T1: triage -----------------------------------------------------------


def test_the_line_reporter_is_parsed_into_titles_and_files():
    failed = e2e_triage.failing_tests([_exec(BAD_TAIL)])
    assert [f.title for f in failed] == ["walk mode shows a marker at the origin"]
    assert failed[0].file == "e2e/walk-mode.spec.ts"
    assert failed[0].line == 17


def test_a_locator_timeout_is_drift_and_a_failed_assertion_is_impl():
    drift, _ = e2e_triage.classify_run([_exec(BAD_TAIL)])
    assert drift[0].cls == "drift"
    impl, _ = e2e_triage.classify_run([_exec(ASSERT_TAIL)])
    assert impl[0].cls == "impl"


def test_an_environment_error_wins_over_every_other_signal():
    tail = "  1) e2e/x.spec.ts:1:1\n  Error: connect ECONNREFUSED 127.0.0.1:8000\n"
    failed, _ = e2e_triage.classify_run([_exec(tail)])
    assert {f.cls for f in failed} == {"env"}


def test_a_missing_spec_is_coverage():
    failed = e2e_triage.classify_run(
        [_exec(BAD_TAIL)], spec_exists={"e2e/walk-mode.spec.ts": False}
    )[0]
    assert failed[0].cls == "coverage"


def test_a_retry_pass_is_flaky_and_never_repaired():
    failed, _ = e2e_triage.classify_run([_exec(BAD_TAIL)], fixture_ok=False)
    assert failed[0].cls == "env"
    flaky = e2e_triage.classify(
        e2e_triage.failing_tests([_exec(BAD_TAIL)]), retried_pass=True
    )
    assert flaky[0].cls == "flaky"


def test_an_unparseable_run_is_unclassified_not_guessed():
    failed, _ = e2e_triage.classify_run([_exec("something broke")])
    assert failed == []
    assert e2e_triage.primary_class(failed) == ""


def test_the_digest_is_bounded_and_names_each_failure():
    failed = e2e_triage.classify_run([_exec(BAD_TAIL)])[0]
    text = e2e_triage.digest(failed, BAD_TAIL, max_chars=80)
    assert "e2e/walk-mode.spec.ts:17" in text
    assert "[drift]" in text
    assert len(text) < 400


# ---- T2: the inner roster -------------------------------------------------


def test_the_roster_is_written_in_the_queue_format(tmp_path: Path):
    failed = e2e_triage.classify_run([_exec(BAD_TAIL)])[0]
    written = inner.write_roster(
        tmp_path, spec_id="007", task_id="T10", failed=failed, acs=("AC-1",)
    )
    assert written.cls == "drift"
    assert (tmp_path / "inner" / "spec.md").is_file()
    assert (tmp_path / "inner" / "plan.md").is_file()
    tasks = inner.load_roster(tmp_path)
    assert [t.id for t in tasks] == ["T1"]
    assert tasks[0].ac_refs == ("AC-1",)
    assert "walk-mode.spec.ts:17" in tasks[0].brief


def test_more_failures_than_the_budget_is_a_typed_stop(tmp_path: Path):
    failed = e2e_triage.classify_run([_exec(BAD_TAIL)])[0]
    many = failed * (inner.MAX_TASKS + 1)
    roster = inner.write_roster(tmp_path, spec_id="007", task_id="T10", failed=many)
    assert len(roster.tasks) == inner.MAX_TASKS


def test_a_repair_scope_stays_in_the_e2e_tree():
    assert inner.scope_for("drift", ("app/",)) == ("frontend/e2e/",)
    assert inner.scope_for("coverage", ("app/",)) == ("frontend/e2e/",)
    assert inner.scope_for("impl", ("app/",)) == ("app/",)


# ---- T5: the weakening guard ---------------------------------------------


def test_renaming_a_locator_is_allowed():
    before = {"e2e/x.spec.ts": e2e_guard.spec_facts("test('a', async () => expect(p.locator('#old')).toBeVisible())")}
    after = {"e2e/x.spec.ts": e2e_guard.spec_facts("test('a', async () => expect(p.locator('#new')).toBeVisible())")}
    assert e2e_guard.weakened(before, after) == []


def test_skipping_or_dropping_an_assertion_is_refused():
    before = {"e2e/x.spec.ts": e2e_guard.spec_facts("test('a', async () => expect(x).toBeVisible())")}
    skipped = {"e2e/x.spec.ts": e2e_guard.spec_facts("test.skip('a', async () => {})")}
    assert e2e_guard.weakened(before, skipped)
    removed = {"e2e/x.spec.ts": e2e_guard.spec_facts("test('b', async () => expect(x).toBeVisible())")}
    assert any("removed test" in p for p in e2e_guard.weakened(before, removed))


def test_a_deleted_spec_file_is_refused():
    before = {"e2e/x.spec.ts": e2e_guard.spec_facts("test('a', async () => {})")}
    assert "disappeared" in e2e_guard.weakened(before, {})[0]


# ---- T4/T6/T7: the phase --------------------------------------------------


def _flow_stub(tmp_path: Path, monkeypatch) -> tuple[types.SimpleNamespace, list[str]]:
    from swarm import evidence, flow

    log = tmp_path / "shell_log.jsonl"
    evidence.append_execution(
        log,
        agent="QA Gatekeeper",
        argv=["npm", "--prefix", "frontend", "run", "test:e2e"],
        exit_code=1,
        duration_ms=5,
        changed_after="h",
        tail=BAD_TAIL,
    )
    spec = tmp_path / "specs" / "007-x"
    spec.mkdir(parents=True)
    (spec / "tasks.md").write_text(
        "- [ ] T1 (AC-1): wire walk mode, acceptance frontend/e2e/walk-mode.spec.ts\n"
    )
    monkeypatch.setattr(flow, "REPO_ROOT", tmp_path)
    calls: list[str] = []
    stub = types.SimpleNamespace(
        run_dir=tmp_path,
        _spec_dir="007-x",
        _task_id="T1",
        _baseline={},
        _in_scope_paths=lambda paths: list(paths),
        state=flow.SwarmState(spec_dir="007-x", task_id="T1"),
        _kickoff=lambda build, role="", step="": calls.append(role),
        _review=lambda task, summary, role="qa": calls.append("qa"),
        _revert_paths=lambda paths, reason="": calls.append("revert") or list(paths),
    )
    stub._e2e_self_heal = types.MethodType(flow.SwarmFlow._e2e_self_heal, stub)
    return stub, calls


def _with_specs(tmp_path: Path, *names: str) -> None:
    for name in names:
        path = tmp_path / "frontend" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test('a', async () => expect(x).toBeVisible())\n")


def test_an_environment_failure_stops_without_editing_a_test(tmp_path, monkeypatch):
    stub, calls = _flow_stub(tmp_path, monkeypatch)
    _with_specs(tmp_path, "e2e/x.spec.ts")
    log = tmp_path / "shell_log.jsonl"
    log.write_text(
        json.dumps(
            {
                "agent": "QA Gatekeeper",
                "argv": ["npm", "--prefix", "frontend", "run", "test:e2e"],
                "exit": 1,
                "tail": "  1) e2e/x.spec.ts:1:1\n  Error: connect ECONNREFUSED\n",
                "changed_after": "h",
                "at": "x",
                "duration_ms": 1,
            }
        )
        + "\n"
    )
    assert stub._e2e_self_heal() is False
    assert stub.state.e2e_self_heal["stop"] == "e2e_env"
    assert calls == [], "no crew may run for an environment failure"


def test_an_implementation_failure_is_left_to_the_code_loop(tmp_path, monkeypatch):
    stub, calls = _flow_stub(tmp_path, monkeypatch)
    _with_specs(tmp_path, "e2e/search.spec.ts")
    log = tmp_path / "shell_log.jsonl"
    log.write_text(
        json.dumps(
            {
                "agent": "QA Gatekeeper",
                "argv": ["npm", "--prefix", "frontend", "run", "test:e2e"],
                "exit": 1,
                "tail": ASSERT_TAIL,
                "changed_after": "h",
                "at": "x",
                "duration_ms": 1,
            }
        )
        + "\n"
    )
    assert stub._e2e_self_heal() is False
    assert stub.state.e2e_self_heal["stop"].startswith("impl")
    assert calls == []


def test_the_phase_is_off_with_the_env_switch(tmp_path, monkeypatch):
    stub, calls = _flow_stub(tmp_path, monkeypatch)
    monkeypatch.setenv("SWARM_E2E_SELF_HEAL", "0")
    assert stub._e2e_self_heal() is False
    assert "off" in stub.state.e2e_self_heal["stop"]
    assert calls == []


def test_a_weakened_repair_is_reverted_and_stops(tmp_path, monkeypatch):
    stub, calls = _flow_stub(tmp_path, monkeypatch)
    spec = tmp_path / "frontend" / "e2e"
    spec.mkdir(parents=True)
    (spec / "walk-mode.spec.ts").write_text(
        "test('walk mode shows a marker at the origin', async () => {\n"
        "  await expect(page.locator('button.walk-start')).toBeVisible()\n"
        "})\n"
    )

    def weakening(build, role="", step=""):
        calls.append(role)
        (spec / "walk-mode.spec.ts").write_text(
            "test('walk mode shows a marker at the origin', async () => {})\n"
        )

    stub._kickoff = weakening
    assert stub._e2e_self_heal() is False
    state = stub.state.e2e_self_heal
    assert state["stop"] == "e2e_weakened"
    assert any("assertions dropped" in p for p in state["weakened"])
    assert "revert" in calls


def test_a_repair_that_makes_the_suite_pass_heals_the_run(tmp_path, monkeypatch):
    from swarm import evidence

    stub, calls = _flow_stub(tmp_path, monkeypatch)
    _with_specs(tmp_path, "e2e/walk-mode.spec.ts")
    log = tmp_path / "shell_log.jsonl"

    def review(task, summary, role="qa"):
        calls.append("qa")
        # QA re-ran the suite after the repair: green at the current delta.
        evidence.append_execution(
            log,
            agent="QA Gatekeeper",
            argv=["npm", "--prefix", "frontend", "run", "test:e2e"],
            exit_code=0,
            duration_ms=5,
            changed_after="h",
            tail="  4 passed (1.3s)",
        )

    stub._review = review
    healed = stub._e2e_self_heal()
    state = stub.state.e2e_self_heal
    assert healed is True, state
    assert state["stop"] == ""
    assert state["rounds"] == 1
    assert state["class"] == "drift"
    assert calls == ["e2e:repair1", "qa"]
