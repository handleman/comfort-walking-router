"""053 swarm hardening (2026-11-25): one regression test per AC.

Every fixture here is a real shape from the 2026-11-25 T23/T6 session, not a
hypothetical: a green-gate block with no evidence, a brief that *references* an
already-implemented helper, a stray `frontend/e2e/` write on a map task, and a
suite that never launched.
"""

from __future__ import annotations

import types

# ---- AC-1: a block must be grounded in recorded evidence --------------------


def test_a_green_run_blocked_with_no_evidence_never_gets_a_fix_round():
    """T23: all gates green, verifier pass, cause `test`, no pytest ever run."""
    from swarm.flow import ungrounded_block

    assert ungrounded_block(
        {"npm check": 0, "npm lint": 0, "npm test": 0, "scope": 0},
        "blocked",
        {"verdict": "pass", "blocked": False},
        "The implementation is not what the spec asks for.",
    )


def test_a_block_that_cites_file_line_still_proceeds():
    from swarm.flow import ungrounded_block

    assert not ungrounded_block(
        {"npm test": 0},
        "blocked",
        {"verdict": "pass"},
        "frontend/src/App.svelte:12 still calls onDestroy inside onMount",
    )


def test_a_block_on_a_failing_gate_is_not_ungrounded():
    from swarm.flow import ungrounded_block

    assert not ungrounded_block(
        {"pytest -q": 1},
        "blocked",
        {"verdict": "pass"},
        "tests fail",
    )


def test_a_verifier_block_keeps_the_fix_loop():
    from swarm.flow import ungrounded_block

    assert not ungrounded_block(
        {"npm test": 0},
        "blocked",
        {"verdict": "blocked", "blocked": True},
        "I think this is wrong",
    )


def test_the_reason_code_says_ungrounded_block():
    from swarm.flow import _reason_code

    state = types.SimpleNamespace(
        ungrounded_block=True,
        no_progress=False,
        verifier={},
        review_verdict="blocked",
    )
    assert _reason_code("needs_human", {}, state) == "reviewer_blocked_ungrounded"


# ---- AC-2: a referenced path is not a required delta -----------------------


def test_use_from_a_path_is_a_reference():
    """T6 named `helpers.ts` as the home of an existing helper, not a deliverable."""
    from swarm.evidence import is_referenced

    brief = "Use `planRoute(page, origin, destination)` from `frontend/e2e/helpers.ts`."
    assert is_referenced(brief, "frontend/e2e/helpers.ts")


def test_an_ownership_mention_keeps_the_path_required():
    from swarm.evidence import is_referenced

    assert not is_referenced(
        "Edit `frontend/e2e/helpers.ts` to add planRoute.", "frontend/e2e/helpers.ts"
    )


def test_the_t6_brief_does_not_require_a_change_to_the_helper(tmp_path):
    from swarm import guards

    brief = (
        "Migrate the specs: use `planRoute` from `frontend/e2e/helpers.ts`; the "
        "helpers already exist — use them. Also update `frontend/e2e/search.spec.ts`."
    )
    record = guards.delta_record(
        brief, ["frontend/e2e/search.spec.ts"], tmp_path
    )
    assert record["reason"] == ""
    assert "frontend/e2e/helpers.ts" not in record["named"]
    assert record["missing"] == []
    assert record["untouched"] == []


def test_a_bare_filename_is_shorthand_not_a_deliverable(tmp_path):
    """`... are already in `helpers.ts`` must not become `missing: helpers.ts`."""
    from swarm import guards

    record = guards.delta_record(
        "The helpers are already in `helpers.ts`; update `frontend/src/App.svelte`.",
        ["frontend/src/App.svelte"],
        tmp_path,
    )
    assert record["missing"] == []
    assert record["reason"] == ""


# ---- AC-3: per-task write allowlist ---------------------------------------


def test_a_stray_e2e_write_on_a_map_task_is_out_of_scope():
    """T23: the coder edited `frontend/e2e/helpers.ts` and flipped e2e_required."""
    from swarm import guards

    allow = guards.task_allowlist("Fix `frontend/src/App.svelte`.")
    changed = [
        "frontend/src/App.svelte",
        "frontend/src/lib/map/icons.ts",
        "frontend/e2e/helpers.ts",
        "app/saved_routes.py",
    ]
    assert guards.allowlist_violations(changed, allow) == [
        "frontend/e2e/helpers.ts",
        "app/saved_routes.py",
    ]


def test_plan_step_targets_join_the_allowlist():
    from swarm import guards

    allow = guards.task_allowlist(
        "Fix the map.", ["Change `frontend/src/lib/map/icons.ts` next."]
    )
    assert guards.allowlist_violations(["frontend/src/lib/map/icons.ts"], allow) == []


def test_an_unnamed_brief_does_not_restrict_writes():
    from swarm import guards

    assert guards.allowlist_violations(
        ["frontend/src/App.svelte", "app/main.py"], guards.task_allowlist("Make it work.")
    ) == []


def test_lockfiles_are_never_treated_as_off_scope():
    from swarm import guards

    allow = guards.task_allowlist("Fix `frontend/src/App.svelte`.")
    assert guards.allowlist_violations(["package-lock.json"], allow) == []


def test_a_stray_e2e_write_does_not_make_a_map_task_an_e2e_task(tmp_path, monkeypatch):
    """The map task must not be asked for a Playwright run it never owned."""
    from swarm import evidence, flow

    monkeypatch.setenv("SWARM_E2E_EVIDENCE", "1")
    (tmp_path / "shell_log.jsonl").write_text("")
    stub = types.SimpleNamespace(
        run_dir=tmp_path,
        state=types.SimpleNamespace(
            brief="Fix `frontend/src/App.svelte`.",
            changed_files=["frontend/src/App.svelte", "frontend/e2e/helpers.ts"],
            e2e={},
        ),
        _evidence_hash=lambda: "h",
    )
    stub._e2e_state = types.MethodType(flow.SwarmFlow._e2e_state, stub)
    assert stub._e2e_state() == {}
    # Sanity: the raw delta would have demanded a run.
    assert evidence.e2e_required(
        stub.state.brief, stub.state.changed_files
    )


# ---- AC-4: a suite that never launched is an environment fault -------------


def test_a_spawn_failure_is_a_launch_error():
    from swarm import e2e_triage

    error = e2e_triage.launch_error({"tail": "Error: spawn /bin/sh ENOENT"})
    assert error and "ENOENT" in error


def test_a_red_suite_with_failures_is_not_a_launch_error():
    from swarm import e2e_triage

    assert e2e_triage.launch_error({"tail": "1 failed\n  ✘ 1 walk-mode.spec.ts:3:1"}) == ""


def test_no_failures_and_no_launch_error_stays_unclassified():
    from swarm import e2e_triage

    assert e2e_triage.launch_error({"tail": ""}) == ""
    assert e2e_triage.launch_error(None) == ""


# ---- AC-5: cap + health stand ---------------------------------------------


def test_the_inner_task_cap_allows_a_stale_suite_migration():
    from swarm import inner

    # The 2026-11-25 stale suite had ~11 failures; a cap of 3 refused the repair.
    assert inner.MAX_TASKS >= 11


def test_swarm_health_reports_ok(monkeypatch, tmp_path):
    from swarm import health

    calls: list[str] = []

    def fake_run(argv, label):
        calls.append(label)

    monkeypatch.setattr(health, "_run", fake_run)
    monkeypatch.setattr(health, "REPO_ROOT", tmp_path)
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("")
    (tmp_path / "swarm" / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / "swarm" / ".venv" / "bin" / "python").write_text("")

    assert health.check() == []
    assert health.main() == 0
    assert calls == ["app tests", "e2e suite"] * 2


def test_swarm_health_fails_loudly(monkeypatch, tmp_path):
    from swarm import health

    monkeypatch.setattr(health, "_run", lambda argv, label: f"{label}: exit 1\nboom")
    monkeypatch.setattr(health, "REPO_ROOT", tmp_path)
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("")
    (tmp_path / "swarm" / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / "swarm" / ".venv" / "bin" / "python").write_text("")

    problems = health.check()
    assert len(problems) == 2
    assert health.main() == 1


def test_the_health_tail_keeps_the_suite_summary_not_server_noise():
    from swarm import health

    log = (
        "[WebServer] INFO:     Uvicorn running on http://127.0.0.1:8000\n"
        '[vite-plugin-svelte] Unused CSS selector ".comfort-segments"\n'
        "  9 failed\n"
        "  3 skipped"
    )
    tail = health._tail(log)
    assert "9 failed" in tail
    assert "Uvicorn running" not in tail
    assert "vite-plugin-svelte" not in tail


# ---- 053 follow-up: host sleep is recorded, not read as a model timeout -----


def test_a_silent_gap_is_recorded_as_host_suspension(tmp_path):
    from swarm import events

    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"type": "llm_started", "at": "a", "mono": 10.0}\n'
        '{"type": "llm_timeout", "at": "b", "mono": 3610.0}\n'
    )
    gap = events.suspension_gap(path, threshold=300)
    assert gap == {"gap_seconds": 3600.0, "after": "a", "resumed": "b"}


def test_a_busy_run_has_no_suspension_record(tmp_path):
    from swarm import events

    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join(
            f'{{"type": "llm_started", "at": "x", "mono": {10.0 + i}}}'
            for i in range(20)
        )
    )
    assert events.suspension_gap(path, threshold=300) is None


def test_a_missing_event_log_is_not_a_suspension(tmp_path):
    from swarm import events

    assert events.suspension_gap(tmp_path / "nope.jsonl", threshold=1) is None


def test_the_reason_code_names_host_suspension():
    from swarm.flow import _reason_code

    state = types.SimpleNamespace(
        ungrounded_block=False,
        no_progress=False,
        verifier={"verdict": "error"},
        review_verdict="",
    )
    payload = {"host_suspended": {"gap_seconds": 3600.0}}
    assert _reason_code("needs_human", payload, state) == "host_suspended"
