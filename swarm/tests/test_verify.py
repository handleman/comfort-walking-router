"""Scenario verifier tests (019): the whole scenario, not the gates."""

from __future__ import annotations

import types

import swarm.crew  # noqa: F401 - bind the real ShellTool before any test patches it
from swarm import verify
from swarm.spec_loader import SpecTask
from swarm.tools_guarded import FullFileReadTool, TrimmedFileReadTool


def _task(brief: str = "GET /geocode in app/main.py", ac_refs: tuple[str, ...] = ("AC-2",)) -> SpecTask:
    return SpecTask(id="T2", ac_refs=ac_refs, brief=brief)


# ---- the scenario: ACs, plan lines, context ----


def test_ac_paragraphs_reads_both_spec_shapes_with_their_continuation():
    spec = (
        "# Spec\n\n"
        "- **AC-1** — The verifier runs when the micro-steps are ready: after\n"
        "  the last micro-step and the 017 self-check.\n"
        "- [ ] AC-2: `GET /geocode` is mounted in `app/main.py`.\n"
        "- **AC-3** — unrelated.\n"
    )
    assert verify.ac_paragraphs(spec, ["AC-1", "AC-2"]) == [
        (
            "- **AC-1** — The verifier runs when the micro-steps are ready: after "
            "the last micro-step and the 017 self-check."
        ),
        "- [ ] AC-2: `GET /geocode` is mounted in `app/main.py`.",
    ]


def test_plan_lines_name_the_lines_that_mention_the_task_files():
    plan = (
        "# Plan\n\n"
        "## Modules\n"
        "- `app/main.py` mounts the geocode router.\n"
        "- `app/cache.py` is unrelated to this sentence.\n"
    )
    lines = verify.plan_lines(plan, _task(), ["app/main.py", "tests/test_geocode.py"])
    assert any("app/main.py" in line for line in lines)
    assert not any("app/cache.py" in line for line in lines)


def _repo(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text(
        "from app.cache import Cache\n\n\ndef get_geocode():\n    return Cache()\n"
    )
    (tmp_path / "app" / "cache.py").write_text("class Cache:\n    pass\n")
    lib = tmp_path / "frontend" / "src" / "lib"
    (lib / "navigation").mkdir(parents=True)
    (lib / "walkMode.ts").write_text("export function tick() {}\n")
    (lib / "navigation" / "walk.integration.test.ts").write_text(
        "import { tick } from '../walkMode'\n"
    )
    return tmp_path


def test_connections_show_imports_and_importers(tmp_path):
    root = _repo(tmp_path)
    view = verify.connections(root, ["app/main.py", "frontend/src/lib/walkMode.ts"])
    assert view["app/main.py"]["imports"] == ["app/cache.py"]
    assert view["frontend/src/lib/walkMode.ts"]["imported_by"] == [
        "frontend/src/lib/navigation/walk.integration.test.ts"
    ]
    assert view["app/main.py"]["imported_by"] == []


def test_connections_are_empty_for_a_path_that_is_not_a_delta_file(tmp_path):
    root = _repo(tmp_path)
    assert verify.connections(root, []) == {}


def test_scenario_context_includes_whole_files_and_lists_what_it_could_not_read(tmp_path):
    root = _repo(tmp_path)
    spec_dir = root / "specs" / "014-walk-guidance-ux"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("- [ ] AC-2: `GET /geocode` is mounted in `app/main.py`.\n")
    (spec_dir / "plan.md").write_text("- `app/main.py` mounts the geocode router.\n")
    big = root / "app" / "big.py"
    big.write_text("x" * (verify.MAX_CONTEXT_CHARS + 1000))
    whole = root / "app" / "main.py"

    context = verify.scenario_context(
        root, "014-walk-guidance-ux", _task(), ["app/main.py", "app/big.py"]
    )

    assert context["brief"] == "GET /geocode in app/main.py"
    assert any("AC-2" in ac for ac in context["acs"])
    assert any("app/main.py" in line for line in context["plan"])
    # The key 019 property: a file longer than the coder's 3000-char read is here whole.
    contents = {entry["path"]: entry["content"] for entry in context["contents"]}
    assert whole.read_text() in contents["app/main.py"]
    assert "app/big.py" not in contents
    assert context["skipped"] == [{"path": "app/big.py", "chars": big.stat().st_size}]
    assert context["connections"]["app/main.py"]["imports"] == ["app/cache.py"]


def test_scenario_context_bounds_the_number_of_files(tmp_path):
    root = tmp_path
    paths = []
    for index in range(verify.MAX_VERIFY_FILES + 3):
        path = root / f"app/file{index}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {index}\n")
        paths.append(f"app/file{index}.py")
    context = verify.scenario_context(root, "019-scenario-verifier", _task(), paths)
    assert len(context["files"]) == verify.MAX_VERIFY_FILES
    assert len(context["skipped"]) == 3


def test_deleted_files_are_still_evidence(tmp_path):
    context = verify.scenario_context(tmp_path, "019-scenario-verifier", _task(), ["app/gone.py"])
    assert context["files"] == ["app/gone.py"]
    assert "(deleted or unreadable)" in context["contents"][0]["content"]


def test_render_context_says_the_file_list_is_whole_and_the_graph_is_a_hint(tmp_path):
    root = _repo(tmp_path)
    context = verify.scenario_context(root, "014-walk-guidance-ux", _task(), ["app/main.py"])
    text = verify.render_context(context)
    assert "whole files, not a head" in text
    assert "best-effort static scan" in text
    assert "from app.cache import Cache" in text


# ---- the answer ----


def test_parse_verdict_reads_pass_and_blocked():
    assert verify.parse_verdict("…\nVERDICT: PASS\n")[0] == "pass"
    assert verify.parse_verdict("**VERDICT: BLOCKED**")[0] == "blocked"
    assert verify.parse_verdict("no verdict here")[0] == "unknown"


def test_parse_verdict_collects_findings():
    verdict, findings = verify.parse_verdict(
        "FINDING: app/main.py:1 — no /geocode route is mounted\n"
        "FINDING: frontend/src/lib/navigation/walkMode.ts — duplicate of the real store\n"
        "VERDICT: BLOCKED"
    )
    assert verdict == "blocked"
    assert findings == [
        "app/main.py:1 — no /geocode route is mounted",
        "frontend/src/lib/navigation/walkMode.ts — duplicate of the real store",
    ]


def test_parse_plan_reuses_the_planner_format_and_the_planner_budget():
    from swarm.crew import MAX_STEPS

    text = "\n".join(
        f"STEP {n}: app/file{n}.py — mount endpoint {n}" for n in range(1, MAX_STEPS + 3)
    )
    steps = verify.parse_plan(text)
    assert len(steps) == MAX_STEPS
    assert steps[0] == "app/file1.py — mount endpoint 1"


def test_render_report_carries_the_findings_and_the_correction_plan():
    context = {"spec": "014", "task": "T2", "brief": "GET /geocode", "files": ["app/main.py"]}
    report = verify.render_report(
        context,
        ["app/main.py:1 — no /geocode route"],
        ["app/main.py — mount GET /geocode"],
    )
    assert "BLOCKED" in report
    assert "no /geocode route" in report
    assert "STEP" not in report  # the step text is what matters, not the marker
    assert "app/main.py — mount GET /geocode" in report


# ---- the whole-file read tool ----


def test_full_file_read_returns_more_than_the_coder_trimmed_read(tmp_path):
    body = "".join(f"line {n}\n" for n in range(1, 1200))  # ~9.5k chars
    path = tmp_path / "mod.py"
    path.write_text(body)
    trimmed = TrimmedFileReadTool(base_dir=str(tmp_path))._run(file_path=str(path))
    whole = FullFileReadTool(base_dir=str(tmp_path))._run(file_path=str(path))
    assert len(trimmed) < len(body)
    assert whole == body


def test_full_file_read_reports_name_and_size_past_the_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("SWARM_VERIFY_READ_CHARS", "2000")
    path = tmp_path / "big.py"
    path.write_text("y" * 5000)
    out = FullFileReadTool(base_dir=str(tmp_path))._run(file_path=str(path))
    assert "NOT READ WHOLE" in out
    assert "big.py" in out
    assert "5000 chars" in out
    assert "CONTINUE with start_line=" in out


def test_full_file_read_keeps_the_secret_guard(tmp_path):
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=secret")
    tool = FullFileReadTool(base_dir=str(tmp_path))
    assert tool._run(file_path=str(tmp_path / ".env")).startswith("BLOCKED")
    assert tool._run(file_path="../escape.txt").startswith("BLOCKED")


# ---- the crew and the model role ----


def test_verify_crew_is_read_only_and_runs_no_gates():
    from swarm.crew import build_verify_crew
    from swarm.tools_guarded import ShellTool

    crew = build_verify_crew("019-scenario-verifier", _task(), "SCENARIO CONTEXT")
    agent = crew.agents[0]
    names = {getattr(tool, "name", "") for tool in agent.tools}
    assert "Repo Edit" not in names
    assert "Repo Create" not in names
    shells = [tool for tool in agent.tools if isinstance(tool, ShellTool)]
    assert len(shells) == 1
    assert shells[0].allow_gates is False
    assert shells[0].agent_role == "verifier"
    assert any(isinstance(tool, FullFileReadTool) for tool in agent.tools)
    description = crew.tasks[0].description
    assert "SCENARIO CONTEXT" in description
    assert "VERDICT: PASS" in description
    assert "FINDING:" in description


def test_verifier_model_defaults_to_the_senior_brain(monkeypatch):
    import os

    from swarm.llms import verifier_llm

    monkeypatch.delenv("SWARM_VERIFIER_MODEL", raising=False)
    senior = os.environ["SWARM_SENIOR_MODEL"]
    expected = senior.removeprefix("openrouter/") if senior.startswith("openrouter/") else senior
    assert verifier_llm().model == expected  # the senior/free brain, provider prefix off


def test_verifier_model_can_have_its_own_role(monkeypatch):
    from swarm.llms import verifier_llm

    monkeypatch.setenv("SWARM_VERIFIER_MODEL", "ollama/swarm-verifier:latest")
    assert verifier_llm().model == "ollama/swarm-verifier:latest"


def test_verifier_joins_the_dashboard_roles(monkeypatch):
    import os

    from swarm.llms import role_models

    monkeypatch.delenv("SWARM_VERIFIER_MODEL", raising=False)
    rows = {row["role"]: row for row in role_models()}
    assert "verifier" in rows
    assert rows["verifier"]["model"] == os.environ["SWARM_SENIOR_MODEL"]


def test_verifier_role_has_its_own_fallback_key():
    from swarm.flow import _fallback_key

    assert _fallback_key("verifier:1") == "SWARM_VERIFIER_MODEL"
    assert _fallback_key("coder:verify1") == "SWARM_CODER_MODEL"


# ---- the flow phase ----


def _flow_stub(monkeypatch):
    from swarm import flow, tools_guarded

    monkeypatch.setattr(tools_guarded, "run_delta", lambda baseline: [])
    stub = types.SimpleNamespace(
        state=types.SimpleNamespace(verifier={}),
        _spec_dir="019-scenario-verifier",
        _baseline={},
        _in_scope_paths=lambda paths: list(paths),
        _delta_signature=lambda: "sig",
    )
    stub._verify_phase = types.MethodType(flow.SwarmFlow._verify_phase, stub)
    return stub


def _blocked(step: str = "STEP 1: app/main.py — mount GET /geocode") -> str:
    return "FINDING: app/main.py — no /geocode route\n" + step + "\nVERDICT: BLOCKED"


def test_verify_phase_passes_without_corrections(monkeypatch):
    stub = _flow_stub(monkeypatch)
    kicked: list[str] = []

    def kick(build, role):
        kicked.append(role)
        return None, "VERDICT: PASS"

    assert stub._verify_phase(_task(), kick) is True
    assert kicked == ["verifier:1"]
    assert stub.state.verifier["verdict"] == "pass"
    assert stub.state.verifier["rounds"] == 1
    assert stub.state.verifier["blocked"] is False


def test_verify_phase_feeds_the_correction_plan_back_to_the_coder(monkeypatch):
    stub = _flow_stub(monkeypatch)
    kicked: list[tuple[str, str]] = []

    def kick(build, role):
        kicked.append((role, role))
        if role.startswith("verifier:1"):
            return None, _blocked()
        if role.startswith("coder:verify1"):
            return None, "step done"
        return None, "VERDICT: PASS"

    assert stub._verify_phase(_task(), kick) is True
    assert [role for role, _ in kicked] == ["verifier:1", "coder:verify1", "verifier:2"]
    record = stub.state.verifier
    assert record["verdict"] == "pass"
    assert record["rounds"] == 2
    assert record["findings"] == ["app/main.py — no /geocode route"]
    assert record["plan"] == ["app/main.py — mount GET /geocode"]
    assert record["blocked"] is False


def test_verify_phase_does_not_loop_forever(monkeypatch):
    stub = _flow_stub(monkeypatch)
    kicked: list[str] = []

    def kick(build, role):
        kicked.append(role)
        if role.startswith("verifier"):
            return None, _blocked()
        return None, "still wrong"

    assert stub._verify_phase(_task(), kick) is False
    assert kicked == ["verifier:1", "coder:verify1", "verifier:2"]
    record = stub.state.verifier
    assert record["blocked"] is True
    assert record["rounds"] == verify.MAX_VERIFY_ROUNDS


def test_verify_phase_treats_a_block_without_a_finding_as_a_pass(monkeypatch):
    stub = _flow_stub(monkeypatch)

    def kick(build, role):
        return None, "VERDICT: BLOCKED"

    assert stub._verify_phase(_task(), kick) is True
    assert stub.state.verifier["blocked"] is False


def test_verify_phase_ends_the_round_without_a_plan(monkeypatch):
    stub = _flow_stub(monkeypatch)
    kicked: list[str] = []

    def kick(build, role):
        kicked.append(role)
        return None, "FINDING: app/main.py — no /geocode route\nVERDICT: BLOCKED"

    assert stub._verify_phase(_task(), kick) is False
    assert kicked == ["verifier:1"]  # no correction step to run
    assert stub.state.verifier["blocked"] is True


def test_verify_phase_can_be_switched_off(monkeypatch):
    stub = _flow_stub(monkeypatch)
    monkeypatch.setenv("SWARM_VERIFY", "0")
    kicked: list[str] = []

    def kick(build, role):
        kicked.append(role)
        return None, "VERDICT: BLOCKED"

    assert stub._verify_phase(_task(), kick) is True
    assert kicked == []
    assert stub.state.verifier == {}


def test_verify_phase_is_advisory_when_the_crew_cannot_run(monkeypatch):
    stub = _flow_stub(monkeypatch)

    def kick(build, role):
        raise SystemExit("transport died")

    assert stub._verify_phase(_task(), kick) is True
    assert stub.state.verifier["verdict"] == "error"


def _reverify_stub(monkeypatch, signature: str = "sig"):
    from swarm import flow

    stub = _flow_stub(monkeypatch)
    sig = {"now": signature}
    stub._delta_signature = lambda: sig["now"]
    stub._reverify_if_stale = types.MethodType(flow.SwarmFlow._reverify_if_stale, stub)
    return stub, sig


def test_reverify_skips_a_fresh_delta_and_consumes_the_flag(monkeypatch):
    stub, _ = _reverify_stub(monkeypatch)
    stub.state.verifier = {"delta": "sig", "corrections": True}
    kicked: list[str] = []

    assert stub._reverify_if_stale(_task(), lambda build, role: kicked.append(role)) is True
    assert kicked == []  # nothing changed since the verifier read the tree
    assert stub.state.verifier["corrections"] is False  # not re-applied twice


def test_reverify_reads_the_scenario_again_when_a_later_round_changed_it(monkeypatch):
    stub, sig = _reverify_stub(monkeypatch)
    stub.state.verifier = {"delta": "old", "corrections": False}

    def verify_again(task, kick):
        sig["now"] = "corrected"  # the correction step edited the tree
        return True

    stub._verify_phase = verify_again
    sig["now"] = "new"
    assert stub._reverify_if_stale(_task(), lambda build, role: None) is True
    assert stub.state.verifier["delta"] == "corrected"
    assert stub.state.verifier["corrections"] is True


def test_reverify_reports_a_scenario_that_is_still_broken(monkeypatch):
    stub, sig = _reverify_stub(monkeypatch)
    stub.state.verifier = {"delta": "old", "corrections": False}
    stub._verify_phase = lambda task, kick: False
    sig["now"] = "new"

    assert stub._reverify_if_stale(_task(), lambda build, role: None) is False


def test_reverify_does_not_touch_a_blocked_verdict(monkeypatch):
    stub, sig = _reverify_stub(monkeypatch)
    stub.state.verifier = {"delta": "old", "blocked": True}
    stub._verify_phase = lambda task, kick: True
    sig["now"] = "new"

    assert stub._reverify_if_stale(_task(), lambda build, role: None) is True
    assert stub.state.verifier["blocked"] is True


def test_a_blocked_verifier_is_never_green():
    from swarm.flow import SwarmFlow, _reason_code

    state = types.SimpleNamespace(
        no_progress=False,
        ungrounded_block=False,
        review_verdict="pass",
        verifier={"blocked": True},
    )
    assert _reason_code("needs_human", {"gates": {"pytest -q": 0}}, state) == "verifier_blocked"
    stub = types.SimpleNamespace(
        state=types.SimpleNamespace(
            status="crew_done",
            gates={"pytest -q": 0},
            review_verdict="pass",
            verifier={"blocked": True},
        ),
        _interrupted=False,
    )
    assert SwarmFlow.gate(stub, "") == "needs_human"


# ---- the operator view ----


def test_human_report_shows_the_verdict_next_to_qa():
    from swarm.humanlog import format_human_report

    payload = {
        "spec": "014-walk-guidance-ux",
        "task": "T2",
        "status": "needs_human",
        "reason_code": "verifier_blocked",
        "review_verdict": "pass",
        "gates": {"pytest -q": 0},
        "verifier": {
            "verdict": "blocked",
            "rounds": 2,
            "blocked": True,
            "findings": ["app/main.py — no /geocode route"],
            "plan": ["app/main.py — mount GET /geocode"],
            "model": "senior/free",
        },
    }
    text = format_human_report(payload, [])
    assert "verifier (BLOCKED" in text
    assert "no /geocode route" in text
    assert "mount GET /geocode" in text
    assert "reason_code: verifier_blocked" in text


def test_dashboard_metrics_show_the_verifier_verdict():
    from swarm.tui import format_metrics

    text = format_metrics(
        {"verifier": {"verdict": "pass", "rounds": 1, "findings": []}}, models=[]
    ).plain
    assert "verifier" in text
    assert "PASS" in text
