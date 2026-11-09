"""Autonomous loop: next-task order + scope-confined autocommit (no LLM, no git)."""

import subprocess

from swarm.flow import _commit_changes, _next_after


def test_next_after_order():
    assert _next_after(["T1", "T2", "T3"], "T1") == "T2"
    assert _next_after(["T1", "T2", "T3"], "T3") is None
    assert _next_after(["T1", "T2"], "T9") is None


class _FakeProc:
    def __init__(self, rc=0, out="ok"):
        self.returncode = rc
        self.stdout = out
        self.stderr = ""


def _fake_git(monkeypatch, changed, calls):
    monkeypatch.setattr("swarm.tools_guarded._git_changed", lambda: changed)

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return _FakeProc()

    monkeypatch.setattr(subprocess, "run", fake_run)


def test_commit_adds_only_scope_files(monkeypatch):
    calls = []
    monkeypatch.setenv("SWARM_MERGE_MODE", "direct")
    _fake_git(monkeypatch, ["app/x.py", "swarm/crew.py", "docs/m.md"], calls)
    rec = _commit_changes("001", "T2", "do things")
    assert rec["commit"].startswith("swarm: 001-T2 green")
    assert rec["push"] == "ok"
    add = calls[0]
    assert add[:3] == ["git", "add", "-A"]
    assert "app/x.py" in add
    assert "swarm/crew.py" not in add
    assert "docs/m.md" not in add


def test_commit_clean_when_nothing_changed(monkeypatch):
    calls = []
    _fake_git(monkeypatch, [], calls)
    rec = _commit_changes("001", "T2", "do things")
    assert rec["commit"].startswith("clean")
    assert calls == []


def test_commit_refuses_env_paths(monkeypatch):
    calls = []
    monkeypatch.setenv("SWARM_SCOPE", "app/,.env")
    _fake_git(monkeypatch, [".env", "app/x.py"], calls)
    rec = _commit_changes("001", "T2", "do things")
    assert rec["commit"].startswith("refused")
    assert calls == []


def test_senior_llm_uses_configured_model(monkeypatch):
    from swarm.llms import senior_llm

    monkeypatch.setenv("SWARM_SENIOR_MODEL", "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free")
    llm = senior_llm()
    assert llm.model == "nvidia/nemotron-3-ultra-550b-a55b:free"  # provider prefix routed off
    assert llm.additional_params.get("extra_body") is None


def test_senior_llm_requires_env(monkeypatch):
    import pytest

    from swarm.llms import senior_llm

    monkeypatch.delenv("SWARM_SENIOR_MODEL", raising=False)
    with pytest.raises(RuntimeError):
        senior_llm()


def test_build_senior_crew_structure():
    from swarm.crew import build_senior_crew
    from swarm.spec_loader import SpecTask

    task = SpecTask(id="T2", ac_refs=("AC-1",), brief="do things")
    crew = build_senior_crew("001", task, "pytest exit=1")
    # 015: QA re-verification is driven by the flow, not embedded in the crew.
    assert [a.role for a in crew.agents] == ["Senior Developer"]
    assert len(crew.tasks) == 1
    assert len(crew.agents[0].tools) >= 4


def test_spec_after_order_and_skips(tmp_path):
    from swarm.flow import _spec_after

    specs = tmp_path / "specs"
    for name, has_tasks in [("001-a", True), ("004-b", True), ("007-c", False), ("009-swarm-harness", True)]:
        d = specs / name
        d.mkdir(parents=True)
        if has_tasks:
            (d / "tasks.md").write_text("x")
    assert _spec_after(tmp_path, "001-a") == "004-b"
    assert _spec_after(tmp_path, "004-b") is None  # 007-c has no tasks, harness excluded
    assert _spec_after(tmp_path, "zzz") is None


def test_escalation_budgets():
    from swarm.crew import DEV_ATTEMPTS, MAX_FIX_ROUNDS, SENIOR_ATTEMPTS

    # 015 tuning, derived from run history (see swarm/README.md "Tuning").
    assert DEV_ATTEMPTS == 2
    assert MAX_FIX_ROUNDS == 3
    assert SENIOR_ATTEMPTS == 2


def test_is_quota_error():
    from swarm.flow import _is_quota_error

    quota = Exception("Error code: 429 - {'error': {'message': 'Rate limit exceeded: free-models-per-day-high-balance.'}}")
    assert _is_quota_error(quota) is True
    assert _is_quota_error(Exception("Provider returned error 429, retry shortly")) is False
    assert _is_quota_error(ValueError("Invalid response from LLM call - None or empty.")) is False


def test_quota_exhausted_is_system_exit():
    from swarm.flow import _QuotaExhausted

    assert issubclass(_QuotaExhausted, SystemExit)


def test_gate_preserves_terminal_status():
    from swarm.flow import SwarmFlow, SwarmState

    class Stub:
        pass

    for terminal in ("quota_exhausted", "crew_error"):
        stub = Stub()
        stub.state = SwarmState(status=terminal, gates={})
        assert SwarmFlow.gate(stub, "whatever") == terminal
    live = Stub()
    live.state = SwarmState(status="crew_done", gates={"pytest -q": 0}, review_verdict="pass")
    assert SwarmFlow.gate(live, "x") == "green"
    blocked = Stub()
    blocked.state = SwarmState(status="crew_done", gates={"pytest -q": 0}, review_verdict="blocked")
    assert SwarmFlow.gate(blocked, "x") == "needs_human"
    unknown = Stub()
    unknown.state = SwarmState(status="crew_done", gates={"pytest -q": 0})
    assert SwarmFlow.gate(unknown, "x") == "needs_human"


def test_step_attempts_budget():
    from swarm.crew import STEP_ATTEMPTS

    # one local/paid try, then the paid retry (routing escalates on attempt 2)
    assert STEP_ATTEMPTS == 2


def test_build_senior_step_crew_structure():
    from swarm.crew import FIX_RULES, build_senior_step_crew
    from swarm.spec_loader import SpecTask

    task = SpecTask(id="T2", ac_refs=("AC-1",), brief="do things")
    crew = build_senior_step_crew("001", task, "STEP 5: do the thing", 5, 6, "crew failed twice")
    assert [a.role for a in crew.agents] == ["Senior Developer"]
    assert len(crew.tasks) == 1
    assert FIX_RULES in crew.tasks[0].description
    assert "crew failed twice" in crew.tasks[0].description


def test_fix_rules_shared_by_fix_and_senior_crews():
    from swarm.crew import FIX_RULES, build_fix_crew, build_senior_crew
    from swarm.spec_loader import SpecTask

    task = SpecTask(id="T2", ac_refs=("AC-1",), brief="do things")
    fix_desc = build_fix_crew("001", task, "ruff exit=1").tasks[0].description
    senior_desc = build_senior_crew("001", task, "ruff exit=1").tasks[0].description
    for text in (fix_desc, senior_desc):
        assert FIX_RULES in text
        assert "QA report" in text or "QA ran the gates" in text


def test_only_qa_runs_gates_in_every_phase():
    from swarm.crew import build_fix_crew, build_step_crew
    from swarm.spec_loader import SpecTask
    from swarm.tools_guarded import ShellTool

    task = SpecTask(id="T2", ac_refs=("AC-1",), brief="do things")

    def shells(crew: object) -> list[ShellTool]:
        tools = crew.agents[0].tools  # type: ignore[attr-defined]
        return [tool for tool in tools if isinstance(tool, ShellTool)]

    step = build_step_crew("001", task, "STEP 1: do it", 1, 1)
    fix = build_fix_crew("001", task, "pytest exit=1", "VERDICT: BLOCKED — no test added")
    for crew in (step, fix):
        assert [shell.allow_gates for shell in shells(crew)] == [False]
    assert "QA ran the gates" in fix.tasks[0].description
    assert "VERDICT: BLOCKED" in fix.tasks[0].description
    assert not any("run the gates" in p.lower() for p in [fix.tasks[0].description])


def _resume_tree(root, runs, specs):
    from pathlib import Path

    root = Path(root)
    for ts, payload in runs.items():
        d = root / "swarm" / "runs" / ts
        d.mkdir(parents=True)
        for name, content in payload.items():
            (d / name).write_text(content)
    for name, tasks_md in specs.items():
        d = root / "specs" / name
        d.mkdir(parents=True)
        if tasks_md is not None:
            (d / "tasks.md").write_text(tasks_md)


def test_resume_red_reruns_same_task(tmp_path):
    import json

    from swarm.flow import _resume_point

    _resume_tree(tmp_path, {"20261011-100000": {"run.json": json.dumps({"spec": "001", "task": "T3", "status": "needs_human"})}}, {})
    assert _resume_point(tmp_path) == ("001", "T3")


def test_resume_killed_run_uses_meta(tmp_path):
    import json

    from swarm.flow import _resume_point

    _resume_tree(tmp_path, {"20261011-100000": {"meta.json": json.dumps({"spec": "001", "task": "T3"})}}, {})
    assert _resume_point(tmp_path) == ("001", "T3")


def test_resume_green_advances_task_and_spec(tmp_path):
    import json

    from swarm.flow import _resume_point

    md = "- [ ] T1 (AC-1): aaa\n- [ ] T2 (AC-1): bbb\n"
    _resume_tree(tmp_path, {"20261011-100000": {"run.json": json.dumps({"spec": "001-x", "task": "T1", "status": "green"})}},
                 {"001-x": md, "004-y": "- [ ] T1 (AC-1): ccc\n"})
    assert _resume_point(tmp_path) == ("001-x", "T2")
    _resume_tree(tmp_path, {"20261011-110000": {"run.json": json.dumps({"spec": "001-x", "task": "T2", "status": "green"})}}, {})
    assert _resume_point(tmp_path) == ("004-y", "T1")


def test_resume_none_when_all_green_or_empty(tmp_path):
    import json

    from swarm.flow import _resume_point

    assert _resume_point(tmp_path) is None
    _resume_tree(tmp_path, {"20261011-100000": {"run.json": json.dumps({"spec": "001-x", "task": "T1", "status": "green"})}},
                 {"001-x": "- [ ] T1 (AC-1): aaa\n"})
    assert _resume_point(tmp_path) is None


def test_resume_green_checked_task_moves_to_next_open(tmp_path):
    import json

    from swarm.flow import _resume_point

    _resume_tree(tmp_path, {"20261011-100000": {"run.json": json.dumps({"spec": "001-x", "task": "T1", "status": "green"})}},
                 {"001-x": "- [x] T1 (AC-1): done\n- [ ] T2 (AC-1): next\n"})
    assert _resume_point(tmp_path) == ("001-x", "T2")


def test_resume_red_checked_task_advances(tmp_path):
    import json

    from swarm.flow import _resume_point

    _resume_tree(tmp_path, {"20261011-100000": {"run.json": json.dumps({"spec": "001-x", "task": "T1", "status": "needs_human"})}},
                 {"001-x": "- [x] T1 (AC-1): done\n- [ ] T2 (AC-1): next\n"})
    assert _resume_point(tmp_path) == ("001-x", "T2")


def test_resume_green_wraps_to_earlier_open_spec(tmp_path):
    import json

    from swarm.flow import _resume_point

    _resume_tree(tmp_path, {"20261011-100000": {"run.json": json.dumps({"spec": "011-z", "task": "T2", "status": "green"})}},
                 {"001-x": "- [ ] T3 (AC-2): reopened\n", "011-z": "- [x] T2 (AC-1): done\n"})
    assert _resume_point(tmp_path) == ("001-x", "T3")


def test_gate_commands_support_newlines_and_deduping():
    from swarm.flow import gate_commands

    assert gate_commands({"SWARM_GATE_COMMANDS": "make check\nmake test"}) == [
        "make check",
        "make test",
    ]


def test_resolve_steps_rejects_garbage():
    from swarm.flow import _resolve_steps

    assert _resolve_steps("STEP 1: do x\nSTEP 2: do y") == ["do x", "do y"]
    assert _resolve_steps("<tool_call> ls -la </tool_call>") == []
    assert _resolve_steps("") == []


def test_plan_attempts_budget():
    from swarm.crew import PLAN_ATTEMPTS

    assert PLAN_ATTEMPTS == 2


def test_reviewer_blocks_noop():
    from swarm.crew import build_review_crew
    from swarm.spec_loader import SpecTask

    task = SpecTask(id="T3", ac_refs=("AC-2",), brief="do things")
    desc = build_review_crew("001", task, "all done").tasks[0].description
    assert "BLOCKED (no-op)" in desc
    assert "git status --short" in desc


def test_reviewer_verdict_uses_declared_line_only():
    from swarm.flow import reviewer_verdict

    assert reviewer_verdict("pytest exit=0\nVERDICT: PASS") == "pass"
    assert reviewer_verdict("ruff exit=0\n**VERDICT: BLOCKED**") == "blocked"
    assert reviewer_verdict("gates red\nVERDICT: PASS\nVERDICT: BLOCKED") == "blocked"
    assert reviewer_verdict("PASS\nBLOCKED") == "blocked"  # standalone final word
    assert reviewer_verdict("all good") == "unknown"
    # 006-T5 regression: reasoning mentions the word, but no verdict was declared.
    thought = "Thought: if no changes were made, the verdict should be BLOCKED. Let me run git status."
    assert reviewer_verdict(thought) == "unknown"
    assert reviewer_verdict("VERDICT: PASS because the diff adds the test") == "pass"


def test_resolve_steps_rejects_over_budget():
    from swarm.flow import _resolve_steps

    nine = "\n".join(f"STEP {i}: app/x.py — edit {i}" for i in range(1, 10))
    assert _resolve_steps(nine) == []


def test_run_delta_ignores_preexisting_dirty_files(tmp_path, monkeypatch):
    import swarm.tools_guarded as tg

    (tmp_path / "app").mkdir()
    human = tmp_path / "app" / "human.py"
    owned = tmp_path / "app" / "owned.py"
    human.write_text("human edit")
    monkeypatch.setattr(tg, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(tg, "_git_changed", lambda: ["app/human.py"])

    baseline = tg.snapshot_worktree()
    owned.write_text("new work")
    (tmp_path / "app" / "human.py").write_text("human edit")
    monkeypatch.setattr(tg, "_git_changed", lambda: ["app/human.py", "app/owned.py"])
    assert tg.run_delta(baseline) == ["app/owned.py"]

    (tmp_path / "app" / "human.py").write_text("human edit v2")
    assert tg.run_delta(baseline) == ["app/human.py", "app/owned.py"]


def test_in_scope_changes_filters_secrets_and_out_of_scope(tmp_path, monkeypatch):
    import swarm.tools_guarded as tg

    monkeypatch.setattr(tg, "REPO_ROOT", tmp_path)
    changed = ["app/x.py", "swarm/crew.py", ".env", "tests/test_x.py"]
    assert tg.in_scope_changes(changed) == ["app/x.py", "tests/test_x.py"]
    assert tg.scope_violations(changed) == ["swarm/crew.py", ".env"]


def test_commit_can_use_explicit_run_delta(monkeypatch):
    calls = []
    monkeypatch.setenv("SWARM_MERGE_MODE", "direct")
    monkeypatch.setattr("swarm.tools_guarded._git_changed", lambda: ["swarm/human.py"])
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: calls.append(list(args)) or _FakeProc())
    rec = _commit_changes("001", "T2", "do things", paths=["app/x.py"])
    assert rec["ok"] == "1"
    assert calls[0] == ["git", "add", "-A", "--", "app/x.py"]


def test_push_failure_is_not_ok(monkeypatch):
    monkeypatch.setenv("SWARM_MERGE_MODE", "direct")

    class _PushFail(_FakeProc):
        def __init__(self, args):
            super().__init__(rc=1 if args[:2] == ["git", "push"] else 0, out="rejected")

    monkeypatch.setattr("swarm.tools_guarded._git_changed", list)
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: _PushFail(list(args)))
    rec = _commit_changes("001", "T2", "do things", paths=["app/x.py"])
    assert rec["commit"].startswith("swarm: 001-T2 green")
    assert rec["push"].startswith("failed")
    assert rec["ok"] == "0"


def test_plan_cache_invalidates_on_spec_change(tmp_path, monkeypatch):
    from swarm import flow

    spec = tmp_path / "specs" / "012-x"
    spec.mkdir(parents=True)
    (spec / "spec.md").write_text("spec v1")
    (spec / "plan.md").write_text("plan")
    (spec / "tasks.md").write_text("- [ ] T1 (AC-1): x\n")
    monkeypatch.setattr(flow, "REPO_ROOT", tmp_path)

    h1 = flow.plan_source_hash("012-x")
    cache = tmp_path / "plan.md"
    flow.write_cached_plan(cache, "STEP 1: app/x.py — do it", h1)
    assert flow.read_cached_plan(cache, h1) == "STEP 1: app/x.py — do it"

    (spec / "spec.md").write_text("spec v2")
    h2 = flow.plan_source_hash("012-x")
    assert h1 != h2
    assert flow.read_cached_plan(cache, h2) == ""


def test_legacy_plan_cache_without_header_is_ignored(tmp_path):
    from swarm import flow

    legacy = tmp_path / "plan.md"
    legacy.write_text("STEP 1: app/x.py — do it")
    assert flow.read_cached_plan(legacy, "0" * 64) == ""


def test_approval_ledger_roundtrip(tmp_path, monkeypatch):
    from swarm import flow

    monkeypatch.setattr(flow, "REPO_ROOT", tmp_path)
    assert flow.approval_granted("001-x", "T1") is False
    path = flow.grant_approval("001-x", "T1")
    assert path.is_file()
    assert flow.approval_granted("001-x", "T1") is True

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "approved.json").write_text('{"approved": true}')
    assert flow.approval_granted("other", "T9", run_dir) is True


def test_unique_run_ids(tmp_path, monkeypatch):
    from swarm import flow

    monkeypatch.setattr(flow, "REPO_ROOT", tmp_path)
    first = flow._unique_run_id()
    second = flow._unique_run_id()
    assert first != second
    assert first[:15] == second[:15]  # timestamp prefix stays sortable


def test_run_delta_detects_deletion_of_clean_tracked_file(tmp_path, monkeypatch):
    import swarm.tools_guarded as tg

    (tmp_path / "app").mkdir()
    monkeypatch.setattr(tg, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(tg, "_git_changed", list)
    baseline = tg.snapshot_worktree()  # clean: nothing dirty
    (tmp_path / "app" / "gone.py").write_text("tracked content")
    monkeypatch.setattr(tg, "_git_changed", lambda: ["app/gone.py"])
    assert tg.run_delta(baseline) == ["app/gone.py"]
    (tmp_path / "app" / "gone.py").unlink()
    assert tg.run_delta(baseline) == ["app/gone.py"]  # deletion is still a run change


def test_approval_key_normalizes_spec_prefix(tmp_path, monkeypatch):
    from swarm import flow

    spec = tmp_path / "specs" / "001-example-app"
    spec.mkdir(parents=True)
    (spec / "tasks.md").write_text("- [ ] T1 (AC-1): x\n")
    monkeypatch.setattr(flow, "REPO_ROOT", tmp_path)
    assert flow.approval_path("001", "T1") == flow.approval_path("001-example-app", "T1")


def test_run_lock_is_exclusive(tmp_path):
    from swarm.flow import RunLock

    lock_a = RunLock(tmp_path / ".lock")
    lock_b = RunLock(tmp_path / ".lock")
    assert lock_a.acquire() is True
    assert lock_b.acquire() is False
    lock_a.release()
    assert lock_b.acquire() is True
    lock_b.release()


def _save_run_stub(tmp_path, monkeypatch, *, review="pass", changed=("app/x.py",), require=False, commit_rec=None):
    import json
    import time
    from typing import ClassVar

    import swarm.tools_guarded as tg
    from swarm import flow

    spec = tmp_path / "specs" / "001-x"
    spec.mkdir(parents=True)
    (spec / "tasks.md").write_text("- [ ] T1 (AC-1): do x\n")
    monkeypatch.setattr(flow, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(tg, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(tg, "run_delta", lambda baseline: list(changed))
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    class Stub:
        state = flow.SwarmState(
            spec_dir="001-x",
            task_id="T1",
            gates={"pytest -q": 0},
            review_verdict=review,
        )
        _spec_dir = "001-x"
        _task_id = "T1"
        _require_approval = require
        _commit = True
        _baseline: ClassVar[dict] = {}
        _started_monotonic = time.monotonic()
        _max_tokens = 2_000_000
        _max_cost = 0.05
        _max_seconds = 14400
        _max_cost_task = 0.05
        _max_seconds_task = 900
        _usage_by_role: ClassVar[dict] = {}
        _usage_by_step: ClassVar[dict] = {}

        def _commit_green(self, brief, changed, **_kwargs):
            return commit_rec or {"commit": "ok", "push": "ok", "ok": "1"}

        def _run_cost(self):
            return 0.0

        def _teardown_listener(self):
            return None

        def _delete_progress(self):
            return None

        def _task_owned_dirty(self, task):
            return {}

        def _in_scope_dirty(self):
            return []

        def _revert_out_of_scope(self, changed):
            return []

        def _gate_evidence(self, changed, *, agents=None):
            return dict(self.state.gates), "", []

        def _restore_stash(self):
            return None

        def _cleanup(self):
            return None

    # 015: state fields the new save path writes.
    _cleanup_state = ("qa_report", "steps_meta", "skipped_ac", "out_of_scope_reverted", "stashed", "evidence_note")

    stub = Stub()
    stub.run_dir = run_dir
    status = flow.SwarmFlow.save_run(stub, "green")
    payload = json.loads((run_dir / "run.json").read_text())
    return status, payload


def test_save_run_blocks_reviewer_verdict(tmp_path, monkeypatch):
    status, payload = _save_run_stub(tmp_path, monkeypatch, review="blocked")
    assert status == "needs_human"
    assert "reviewer verdict" in payload["review_note"]
    assert "autocommit" not in payload


def test_save_run_records_empty_vacancy_as_green(tmp_path, monkeypatch):
    status, payload = _save_run_stub(tmp_path, monkeypatch, changed=())
    assert status == "green"
    assert payload["vacancy_note"].startswith("no in-scope changes")
    assert payload["autocommit"]["ok"] == "1"
    assert payload["done"]["recorded"] is True


def test_save_run_holds_for_approval(tmp_path, monkeypatch):
    status, payload = _save_run_stub(tmp_path, monkeypatch, require=True)
    assert status == "awaiting_approval"
    assert payload["approval_required"] is True
    assert "autocommit" not in payload


def test_save_run_marks_push_failure_non_green(tmp_path, monkeypatch):
    status, payload = _save_run_stub(
        tmp_path,
        monkeypatch,
        commit_rec={"commit": "ok", "push": "failed: rejected", "ok": "0"},
    )
    assert status == "push_failed"
    assert payload["status"] == "push_failed"


def test_save_run_records_ac_evidence(tmp_path, monkeypatch):
    status, payload = _save_run_stub(tmp_path, monkeypatch)
    assert status == "green"
    assert payload["ac_refs"] == ["AC-1"]
    assert payload["evidence"]["review_verdict"] == "pass"
    assert payload["evidence"]["changed_files"] == ["app/x.py"]
    assert payload["autocommit"]["ok"] == "1"


def test_last_checkpoint_task_reads_latest_run(tmp_path, monkeypatch):
    import json

    from swarm import flow

    runs = tmp_path / "swarm" / "runs"
    held = runs / "20261108-120000-1-aaaa"
    held.mkdir(parents=True)
    (held / "run.json").write_text(json.dumps({"spec": "001-example-app", "task": "T3",
                                               "status": "awaiting_approval"}))
    (runs / "latest").write_text(held.name)
    monkeypatch.setattr(flow, "REPO_ROOT", tmp_path)
    assert flow._last_checkpoint_task(tmp_path) == ("001-example-app", "T3")
    assert flow._last_checkpoint_task(tmp_path / "missing") is None


def test_gate_passes_preflight_failure_through():
    from swarm.flow import SwarmFlow, SwarmState

    class Stub:
        state = SwarmState(status="preflight_failed")
        _interrupted = False

    assert SwarmFlow.gate(Stub(), "x") == "preflight_failed"


def test_record_usage_accumulates_tokens_and_models():
    import types
    from typing import ClassVar

    from swarm.flow import SwarmFlow, SwarmState

    class Out:
        token_usage = types.SimpleNamespace(
            prompt_tokens=10, completion_tokens=5, cached_prompt_tokens=2,
            total_tokens=15, successful_requests=1,
        )

    class Crew:
        agents: ClassVar[list] = [
            types.SimpleNamespace(llm=types.SimpleNamespace(model="ollama/x"))
        ]

    stub = types.SimpleNamespace(state=SwarmState())
    SwarmFlow._record_usage(stub, Crew(), Out())
    SwarmFlow._record_usage(stub, Crew(), Out())
    assert stub.state.prompt_tokens == 20
    assert stub.state.completion_tokens == 10
    assert stub.state.cached_prompt_tokens == 4
    assert stub.state.total_tokens == 30
    assert stub.state.llm_calls == 2
    assert stub.state.models_used == ["ollama/x"]


def test_check_budget_raises_on_token_limit():
    import time as _time
    import types

    import pytest

    from swarm.flow import SwarmFlow, SwarmState, _BudgetExhausted

    stub = types.SimpleNamespace(
        state=SwarmState(total_tokens=11),
        _max_tokens=10,
        _max_cost=0.0,
        _max_seconds=0,
        _started_monotonic=_time.monotonic(),
        _run_cost=lambda: 0.0,
    )
    with pytest.raises(_BudgetExhausted, match="token budget"):
        SwarmFlow._check_budget(stub)


def test_check_budget_raises_on_time_limit():
    import time as _time
    import types

    import pytest

    from swarm.flow import SwarmFlow, SwarmState, _BudgetExhausted

    stub = types.SimpleNamespace(
        state=SwarmState(total_tokens=0),
        _max_tokens=0,
        _max_cost=0.0,
        _max_seconds=1,
        _started_monotonic=_time.monotonic() - 5,
        _run_cost=lambda: 0.0,
    )
    with pytest.raises(_BudgetExhausted, match="time budget"):
        SwarmFlow._check_budget(stub)


def test_teardown_listener_calls_teardown():
    import types

    from swarm.flow import SwarmFlow

    calls = []

    class Listener:
        def teardown(self):
            calls.append("teardown")

    stub = types.SimpleNamespace(listener=Listener())
    SwarmFlow._teardown_listener(stub)
    assert calls == ["teardown"]
    assert stub.listener is not None  # kept: the TUI still drains its queue


def _merge_git(monkeypatch, *, merge_rc=0, branch_push_rc=0, base_push_rc=0):
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        call = list(args)
        calls.append(call)
        a = call[1:]
        out, rc = "ok", 0
        if a[:2] == ["rev-parse", "--verify"]:
            rc = 1  # branch does not exist yet
        elif (
            a[:2] == ["switch", "-c"]
            or a[:2] == ["switch", "main"]
            or a[0] == "add"
            or a[0] == "commit"
            or a[:1] == ["reset"]
        ):
            rc = 0
        elif a[:3] == ["push", "-u", "origin"]:
            rc, out = branch_push_rc, "rejected branch"
        elif a[:2] == ["rev-parse", "HEAD"]:
            out = "abc123def"
        elif a[0] == "merge" and "--abort" in a:
            rc = 0
        elif a[0] == "merge":
            rc, out = merge_rc, "CONFLICT (content)"
        elif a[:3] == ["push", "origin", "main"]:
            rc, out = base_push_rc, "rejected base"
        return _FakeProc(rc=rc, out=out)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("SWARM_BASE_BRANCH", "main")
    monkeypatch.setenv("SWARM_MERGE_MODE", "merge")
    monkeypatch.setattr("swarm.tools_guarded._git_changed", list)
    return calls


def test_branch_name_is_sanitized():
    from swarm.flow import _branch_name

    assert _branch_name("001-example-app", "T3") == "swarm/001-example-app-T3"
    assert _branch_name("001/x y", "T3:z") == "swarm/001-x-y-T3-z"


def test_merge_mode_happy_path(monkeypatch):
    calls = _merge_git(monkeypatch)
    rec = _commit_changes("001", "T2", "do things", paths=["app/x.py"])
    assert rec["ok"] == "1"
    assert rec["branch"] == "swarm/001-T2"
    assert rec["base"] == "main"
    assert rec["merge"] == "ok"
    flat = [c[1:] for c in calls]
    assert ["switch", "-c", "swarm/001-T2"] in flat
    assert ["add", "-A", "--", "app/x.py"] in flat
    assert ["merge", "--no-ff", "swarm/001-T2", "-m", "merge: swarm 001-T2 green"] in flat
    assert ["push", "origin", "main"] in flat


def test_merge_conflict_is_not_green(monkeypatch):
    calls = _merge_git(monkeypatch, merge_rc=1)
    rec = _commit_changes("001", "T2", "do things", paths=["app/x.py"])
    assert rec["ok"] == "0"
    assert rec["merge"].startswith("conflict")
    flat = [c[1:] for c in calls]
    assert ["merge", "--abort"] in flat
    assert ["push", "origin", "main"] not in flat


def test_branch_push_failure_keeps_work_and_untouched_base(monkeypatch):
    calls = _merge_git(monkeypatch, branch_push_rc=1)
    rec = _commit_changes("001", "T2", "do things", paths=["app/x.py"])
    assert rec["ok"] == "0"
    assert rec["push"].startswith("failed")
    assert "kept local branch" in rec["rollback"]
    flat = [c[1:] for c in calls]
    assert ["merge", "--no-ff", "swarm/001-T2", "-m", "merge: swarm 001-T2 green"] not in flat


def test_base_push_failure_rolls_back_merge(monkeypatch):
    calls = _merge_git(monkeypatch, base_push_rc=1)
    rec = _commit_changes("001", "T2", "do things", paths=["app/x.py"])
    assert rec["ok"] == "0"
    assert rec["push"].startswith("failed (merge not pushed)")
    assert "reset main to abc123de" in rec["rollback"]
    assert ["reset", "--hard", "abc123def"] in [c[1:] for c in calls]


def test_merge_failure_maps_to_merge_failed(tmp_path, monkeypatch):
    status, payload = _save_run_stub(
        tmp_path,
        monkeypatch,
        commit_rec={"commit": "ok", "push": "ok", "merge": "conflict: boom", "ok": "0"},
    )
    assert status == "merge_failed"
    assert payload["status"] == "merge_failed"


def _git_init_repo(repo):
    import subprocess as sp

    def run(*args):
        return sp.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)

    run("init", "-q", "-b", "main")
    run("config", "user.email", "swarm@test.local")
    run("config", "user.name", "swarm test")
    (repo / "app").mkdir()
    (repo / "app" / "base.py").write_text("x = 1\n")
    run("add", "-A")
    run("commit", "-q", "-m", "base")
    remote = repo.parent / (repo.name + "-remote.git")
    sp.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    run("remote", "add", "origin", str(remote))
    run("push", "-q", "-u", "origin", "main")
    return remote, run


def test_merge_mode_against_real_git(tmp_path, monkeypatch):
    from swarm import flow

    repo = tmp_path / "repo"
    repo.mkdir()
    _remote, run = _git_init_repo(repo)
    (repo / "app" / "new.py").write_text("y = 2\n")
    monkeypatch.setattr(flow, "REPO_ROOT", repo)
    monkeypatch.delenv("SWARM_MERGE_MODE", raising=False)
    monkeypatch.setenv("SWARM_BASE_BRANCH", "main")

    rec = flow._commit_changes("001", "T2", "add new.py", paths=["app/new.py"])
    assert rec["ok"] == "1", rec
    assert rec["branch"] == "swarm/001-T2"

    branches = run("branch", "--list", "swarm/001-T2").stdout
    assert "swarm/001-T2" in branches
    merge_subject = run("log", "-1", "--merges", "--pretty=%s").stdout.strip()
    assert merge_subject == "merge: swarm 001-T2 green"
    assert (repo / "app" / "new.py").is_file()
    assert run("status", "--porcelain").stdout.strip() == ""


def test_commit_emits_done_ledger_trailers(monkeypatch):
    calls = []
    monkeypatch.setenv("SWARM_MERGE_MODE", "direct")
    _fake_git(monkeypatch, ["app/x.py"], calls)
    rec = _commit_changes(
        "001-example-app",
        "T3",
        "do things",
        task_hash_value="a" * 64,
        spec_hash_value="b" * 64,
        run_id="run-1",
    )
    msg = calls[1][3]
    assert "Swarm-Task: 001-example-app/T3" in msg
    assert f"Swarm-Task-Hash: {'a' * 64}" in msg
    assert f"Swarm-Spec-Hash: {'b' * 64}" in msg
    assert "Swarm-Run: run-1" in msg
    assert rec["ok"] == "1"


def test_save_run_records_done_ledger(tmp_path, monkeypatch):
    status, payload = _save_run_stub(tmp_path, monkeypatch)
    assert status == "green"
    assert payload["done"]["recorded"] is True
    assert payload["done"]["task_hash"]


def test_save_run_hold_records_delta_hashes(tmp_path, monkeypatch):
    status, payload = _save_run_stub(tmp_path, monkeypatch, require=True)
    assert status == "awaiting_approval"
    assert payload["delta_hashes"] == {"app/x.py": "<missing>"}
    assert "head" in payload


def test_commit_trailers_feed_the_done_ledger(tmp_path, monkeypatch):
    import swarm.tools_guarded as tg
    from swarm import flow
    from swarm.done import done_entries

    repo = tmp_path / "repo"
    repo.mkdir()
    _, _run = _git_init_repo(repo)
    (repo / "app" / "new.py").write_text("y = 2\n")
    monkeypatch.setattr(flow, "REPO_ROOT", repo)
    monkeypatch.setattr(tg, "REPO_ROOT", repo)
    monkeypatch.delenv("SWARM_MERGE_MODE", raising=False)
    monkeypatch.setenv("SWARM_BASE_BRANCH", "main")

    task_hash = "a" * 64
    spec_hash = "b" * 64
    rec = _commit_changes(
        "001-x",
        "T1",
        "add new.py",
        paths=["app/new.py"],
        task_hash_value=task_hash,
        spec_hash_value=spec_hash,
        run_id="run-1",
    )
    assert rec["ok"] == "1", rec
    entries = done_entries(repo)
    entry = entries["001-x/T1"]
    assert entry.task_hash == task_hash
    assert entry.spec_hash == spec_hash
    assert entry.source == "git"


def test_gate_commands_are_config_driven():
    from swarm.flow import DEFAULT_GATE_COMMANDS, gate_commands

    assert gate_commands({"SWARM_GATE_COMMANDS": "pytest -q;npm run check"}) == [
        "pytest -q",
        "npm run check",
    ]
    assert gate_commands({}) == list(DEFAULT_GATE_COMMANDS)


def test_recover_prior_delta_requires_exact_match(tmp_path, monkeypatch):
    import json
    import types

    import swarm.tools_guarded as tg
    from swarm.flow import SwarmFlow, SwarmState
    from swarm.spec_loader import SpecTask

    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "x.py").write_text("x\n")
    prev = repo / "swarm" / "runs" / "20260101-000000-1-aaaa"
    cur = repo / "swarm" / "runs" / "20260102-000000-2-bbbb"
    prev.mkdir(parents=True)
    cur.mkdir(parents=True)
    (prev / "meta.json").write_text(json.dumps({"spec": "001-x", "task": "T1"}))
    (prev / "progress.json").write_text(json.dumps({"delta_hashes": {"app/x.py": "h"}}))
    monkeypatch.setattr("swarm.flow.REPO_ROOT", repo)
    monkeypatch.setattr(tg, "REPO_ROOT", repo)
    monkeypatch.setattr(tg, "_git_changed", lambda: ["app/x.py"])

    stub = types.SimpleNamespace(
        run_dir=cur,
        state=SwarmState(spec_dir="001-x", task_id="T1"),
        _in_scope_dirty=lambda: list(tg._git_changed()),
        _in_scope_paths=lambda paths: list(paths),
    )
    task = SpecTask(id="T1", ac_refs=("AC-1",), brief="do x")
    owned = SwarmFlow._task_owned_dirty(stub, task)
    assert owned == {"app/x.py": prev.name}

    monkeypatch.setattr(tg, "_git_changed", lambda: ["app/x.py", "app/y.py"])
    owned = SwarmFlow._task_owned_dirty(stub, task)
    assert owned == {"app/x.py": prev.name}  # extras stay untouched
    monkeypatch.setattr(tg, "_git_changed", lambda: ["app/y.py"])
    assert SwarmFlow._task_owned_dirty(stub, task) == {}


def test_commit_empty_vacancy_direct_mode(monkeypatch):
    calls = []
    monkeypatch.setenv("SWARM_MERGE_MODE", "direct")
    _fake_git(monkeypatch, [], calls)
    rec = _commit_changes("001-x", "T1", "do x", paths=[], allow_empty=True)
    assert rec["ok"] == "1"
    commit = next(c for c in calls if c[:2] == ["git", "commit"])
    assert "--allow-empty" in commit
    assert "Swarm-Vacancy: 1" in commit[commit.index("-m") + 1]


def test_repair_verdict_accepts_clean_pass(monkeypatch):
    import types

    from swarm import flow
    from swarm.spec_loader import SpecTask

    class LLM:
        def call(self, prompt):
            return "VERDICT: PASS"

    monkeypatch.setattr("swarm.llms.reviewer_llm", lambda: LLM())
    stub = types.SimpleNamespace(
        state=flow.SwarmState(review_verdict="unknown"),
        _verdict_retried=False,
    )
    flow.SwarmFlow._repair_verdict(stub, SpecTask(id="T1", ac_refs=("AC-1",), brief="do x"), "exit=0")
    assert stub.state.review_verdict == "pass"
    assert "verdict repair" in stub.state.review_text


def test_repair_verdict_falls_back_to_free_model(monkeypatch):
    import types

    from swarm import flow
    from swarm.spec_loader import SpecTask

    class Bad:
        def call(self, prompt):
            raise RuntimeError("offline")

    class Good:
        def call(self, prompt):
            return "VERDICT: PASS"

    monkeypatch.setattr("swarm.llms.reviewer_llm", lambda: Bad())
    monkeypatch.setattr("swarm.llms.verdict_fallback_llm", lambda: Good())
    stub = types.SimpleNamespace(
        state=flow.SwarmState(review_verdict="unknown"),
        _verdict_retried=False,
    )
    flow.SwarmFlow._repair_verdict(stub, SpecTask(id="T1", ac_refs=("AC-1",), brief="do x"), "")
    assert stub.state.review_verdict == "pass"


def test_repair_verdict_does_not_override_blocked(monkeypatch):
    import types

    from swarm import flow
    from swarm.spec_loader import SpecTask

    stub = types.SimpleNamespace(
        state=flow.SwarmState(review_verdict="blocked"),
        _verdict_retried=False,
    )
    flow.SwarmFlow._repair_verdict(stub, SpecTask(id="T1", ac_refs=(), brief="x"), "")
    assert stub.state.review_verdict == "blocked"


def test_reviewer_verdict_parses_json():
    from swarm.flow import reviewer_verdict

    assert reviewer_verdict('{"verdict": "PASS", "reason": "gates green"}') == "pass"
    assert reviewer_verdict('{"verdict": "BLOCKED"}') == "blocked"
    assert reviewer_verdict("VERDICT: PASS") == "pass"


def test_reason_codes_are_specific():
    import types

    from swarm.flow import _reason_code

    state = types.SimpleNamespace(review_verdict="unknown")
    assert _reason_code("needs_human", {}, state) == "reviewer_no_verdict"
    state.review_verdict = "blocked"
    assert _reason_code("needs_human", {}, state) == "reviewer_blocked"
    state.review_verdict = "pass"
    assert _reason_code("needs_human", {"vacancy_note": "x"}, state) == "vacancy"
    assert _reason_code("needs_human", {"gates": {"pytest -q": 1}}, state) == "gates_failed"
    assert _reason_code("green", {}, state) == "green"


def test_fix_rounds_are_bounded():
    from swarm.crew import MAX_FIX_ROUNDS, build_fix_crew, build_senior_crew
    from swarm.spec_loader import SpecTask

    task = SpecTask(id="T2", ac_refs=("AC-1",), brief="do things")
    assert MAX_FIX_ROUNDS == 3
    for crew in (
        build_fix_crew("001", task, "pytest exit=1"),
        build_senior_crew("001", task, "pytest exit=1"),
    ):
        assert len(crew.tasks) == 1  # coder only; QA runs in the flow
        assert "QA" in crew.tasks[0].description


def test_qa_budget_covers_every_gate():
    """015 tuning: QA must be able to run all gates + git status + answer."""
    from swarm.crew import build_review_crew
    from swarm.flow import gate_commands
    from swarm.spec_loader import SpecTask

    crew = build_review_crew("001", SpecTask(id="T1", ac_refs=("AC-1",), brief="x"), "did it")
    required = len(gate_commands()) + 1  # + `git status`
    assert crew.agents[0].max_iter >= required + 2


def test_block_is_grounded_requires_checkable_evidence():
    from swarm.flow import block_is_grounded

    assert block_is_grounded("FAILED tests/test_scoring_regression.py::test_matrix")
    assert block_is_grounded("app/main.py:42 - TypeError")
    assert block_is_grounded("AC-5 is not covered by any test")
    assert block_is_grounded("pytest exit=1")
    assert not block_is_grounded("this does not look complete enough")
    assert not block_is_grounded("Thought: the verdict should be BLOCKED")


def test_reason_codes_for_stalled_rounds():
    import types

    from swarm.flow import _reason_code

    state = types.SimpleNamespace(review_verdict="blocked", no_progress=True, ungrounded_block=False)
    assert _reason_code("needs_human", {}, state) == "no_progress"
    state.no_progress = False
    state.ungrounded_block = True
    assert _reason_code("needs_human", {}, state) == "reviewer_blocked_ungrounded"
    state.ungrounded_block = False
    assert _reason_code("needs_human", {}, state) == "reviewer_blocked"


def test_llm_timeout_and_sdk_retries_are_configurable(monkeypatch):
    from swarm import llms

    monkeypatch.setenv("SWARM_LLM_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("SWARM_LLM_MAX_RETRIES", "1")
    model = llms._build("openrouter/nvidia/nemotron-3.5-super-vl:free", temperature=0, allow_paid=False)
    assert model.timeout == 45
    assert model.max_retries == 1
    monkeypatch.setenv("SWARM_LLM_TIMEOUT_SECONDS", "not-a-number")
    assert llms._timeout_seconds() == 60


def test_connection_timeout_is_retryable():
    from swarm.retry import classify_provider_error, is_retryable

    err = RuntimeError("Failed to connect to OpenAI API: Request timed out.")
    assert is_retryable(err) is True
    assert classify_provider_error(err) == "retryable"


def test_self_heal_installs_new_frontend_deps(tmp_path, monkeypatch):
    from swarm import preflight

    calls: list[list[str]] = []

    def fake_run(cmd, timeout):
        calls.append(cmd)
        missing = cmd[:3] == ["npm", "--prefix", "frontend"] and cmd[3:4] == ["ls"]
        return not missing  # `ls` fails when a dependency is missing

    monkeypatch.setattr(preflight, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(preflight, "_run", fake_run)
    (tmp_path / "frontend" / "node_modules").mkdir(parents=True)
    (tmp_path / "frontend" / "package.json").write_text("{}")
    actions = preflight.self_heal({"SWARM_SELF_HEAL": "1"}, log=lambda _m: None)
    assert ["npm", "--prefix", "frontend", "install"] in calls
    assert any("newly added frontend deps" in a for a in actions)


def test_ollama_timeout_is_bounded(monkeypatch):
    from swarm import llms

    monkeypatch.setenv("SWARM_OLLAMA_TIMEOUT_SECONDS", "120")
    model = llms._build("ollama/swarm-qa:latest", temperature=0, allow_paid=False)
    assert model.timeout == 120
    assert model.max_retries == 1
