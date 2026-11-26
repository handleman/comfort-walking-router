"""054 AC-1: every e2e entry point builds before it serves `dist/`."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


def test_the_playwright_config_builds_before_serving():
    config = (FRONTEND / "playwright.config.ts").read_text()
    assert "globalSetup" in config
    setup = (FRONTEND / "e2e" / "global-setup.ts").read_text()
    assert "npm run build" in setup
    # The preview server is what serves dist/; it must be the global setup's job.
    assert "preview" in config


def test_the_npm_script_is_the_one_the_harness_runs():
    """`swarm.e2e` records `npm --prefix frontend run test:e2e` as the evidence."""
    package = (FRONTEND / "package.json").read_text()
    assert '"test:e2e"' in package
    from swarm import e2e

    assert ["npm", "--prefix", "frontend", "run", "test:e2e"] == e2e.agent_commands("")[1]


# ---- AC-2: a PASS without the evidence the task requires -------------------


def _state(**kw):
    import types

    from swarm.flow import SwarmState

    state = SwarmState(spec_dir="040-x", task_id="T1") if not kw else None
    if state is None:
        state = types.SimpleNamespace(**kw)
    return state


def test_a_pass_without_the_e2e_run_is_flagged(tmp_path):
    import types

    from swarm import flow

    (tmp_path / "shell_log.jsonl").write_text("")
    state = _state(
        brief="Migrate `frontend/e2e/walk-mode.spec.ts`.",
        changed_files=["frontend/e2e/walk-mode.spec.ts"],
        e2e={},
        judges={},
        review_verdict="pass",
        review_note="",
    )
    stub = types.SimpleNamespace(
        run_dir=tmp_path,
        state=state,
        _evidence_hash=lambda: "h",
        _allow_cache=set(),
    )
    stub._e2e_state = types.MethodType(flow.SwarmFlow._e2e_state, stub)
    result = stub._e2e_state()
    assert result["required"] is True and result["recorded"] is False
    assert stub.state.review_unsupported is True
    assert stub.state.judges["qa"]["missing_evidence"] == [
        "npm --prefix frontend run test:e2e"
    ]
    assert "without the required e2e" in stub.state.review_note


def test_the_reason_code_names_unsupported_review():
    import types

    from swarm.flow import _reason_code

    state = types.SimpleNamespace(
        ungrounded_block=False,
        review_unsupported=True,
        no_progress=False,
        verifier={},
        review_verdict="pass",
    )
    assert _reason_code("needs_human", {}, state) == "review_unsupported"


def test_a_harness_run_clears_the_unsupported_flag(tmp_path, monkeypatch):
    import types

    from swarm import evidence, flow

    (tmp_path / "shell_log.jsonl").write_text("")
    spec = tmp_path / "specs" / "040-x"
    spec.mkdir(parents=True)
    (spec / "tasks.md").write_text("- [ ] T1 (AC-1): x\n")
    monkeypatch.setattr(flow, "REPO_ROOT", tmp_path)
    state = _state(
        brief="Migrate `frontend/e2e/walk-mode.spec.ts`.",
        changed_files=["frontend/e2e/walk-mode.spec.ts"],
        e2e={},
        judges={},
        review_verdict="pass",
        review_note="QA PASS",
        review_unsupported=True,
    )
    stub = types.SimpleNamespace(
        run_dir=tmp_path,
        state=state,
        _evidence_hash=lambda: "h",
        _spec_dir="040-x",
        _task_id="T1",
        _baseline={},
        _in_scope_paths=lambda paths: list(paths),
        _revert_paths=lambda paths, reason="": list(paths),
        _kickoff=lambda build, role="", step="": None,
        _review=lambda task, summary, role="qa": None,
    )
    stub._run_e2e_deterministically = lambda specs: evidence.append_execution(
        tmp_path / "shell_log.jsonl",
        agent="harness-e2e",
        argv=["npm", "--prefix", "frontend", "run", "test:e2e"],
        exit_code=0,
        duration_ms=5,
        changed_after="h",
        tail="9 passed",
    )
    stub._e2e_self_heal = types.MethodType(flow.SwarmFlow._e2e_self_heal, stub)
    assert stub._e2e_self_heal() is True
    assert stub.state.review_unsupported is False
