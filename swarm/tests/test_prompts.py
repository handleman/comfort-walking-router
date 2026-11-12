"""Prompt assembly tests (020 T2): one stable prefix, volatile content last."""

from __future__ import annotations

from swarm import prompts
from swarm.spec_loader import SpecTask


def _task(brief: str = "Add `app/scoring.py` factors and a test in `tests/test_scoring.py`.") -> SpecTask:
    return SpecTask(id="T2", ac_refs=("AC-2", "AC-3"), brief=brief)


# ---- the stable prefix ----


def test_stable_prefix_is_byte_identical_across_steps_and_calls():
    task = _task()
    first = prompts.stable_prefix(task, "001-example-app", "step")
    second = prompts.stable_prefix(task, "001-example-app", "step")
    assert first == second
    # iteration index is volatile, so it cannot live in the prefix
    assert "micro-step 1" not in first.lower()


def test_stable_prefix_changes_when_the_brief_changes():
    a = prompts.stable_prefix(_task("Add `app/a.py`."), "001-example-app")
    b = prompts.stable_prefix(_task("Add `app/b.py`."), "001-example-app")
    assert a != b


def test_stable_prefix_moves_with_the_role():
    task = _task()
    coder = prompts.stable_prefix(task, "001-example-app", "step")
    qa = prompts.stable_prefix(task, "001-example-app", "qa")
    verifier = prompts.stable_prefix(task, "001-example-app", "verifier")
    assert coder != qa and qa != verifier
    assert "VERDICT: PASS" in qa
    assert "FINDING:" in verifier


def test_verifier_prefix_carries_the_referenced_acceptance_criteria():
    task = _task()
    prefix = prompts.stable_prefix(task, "020-harness-efficiency", "verifier")
    assert "ACCEPTANCE CRITERIA" in prefix
    assert "AC-2" in prefix
    assert "cache hints" in prefix  # the AC paragraph itself, not just the id
    # a coder works from the planner's steps and the brief; no AC re-send (T2 is
    # the efficiency phase, and the bench charges every repeated paragraph)
    coder = prompts.stable_prefix(task, "020-harness-efficiency", "step")
    assert "ACCEPTANCE CRITERIA" not in coder
    assert task.brief in coder


def test_plan_lines_are_in_the_verifier_prefix_not_the_coder_prefix():
    task = SpecTask(id="T1", ac_refs=("AC-1",), brief="Add `swarm/bench/corpus.py`.")
    coder = prompts.stable_prefix(task, "020-harness-efficiency", "step")
    verifier = prompts.stable_prefix(task, "020-harness-efficiency", "verifier")
    assert "PLAN LINES" not in coder
    assert "PLAN LINES" in verifier
    plan_section = verifier.split("PLAN LINES", 1)[1]
    assert "corpus.py" in plan_section


def test_prompt_prefix_is_provider_order_and_hashes_the_same_text():
    task = _task()
    text, digest = prompts.prompt_prefix(task, "001-example-app", "step")
    agent = prompts.agent_copy(task, "step")
    assert text.startswith(agent["role"])
    assert agent["goal"] in text and agent["backstory"] in text
    assert prompts.stable_prefix(task, "001-example-app", "step") in text
    assert digest == prompts.prompt_prefix(task, "001-example-app", "step")[1]
    other = prompts.prompt_prefix(_task("Something else in `app/z.py`."), "001-example-app", "step")[1]
    assert digest != other


# ---- the volatile tail ----


def test_step_prompt_appends_the_step_after_the_prefix():
    task = _task()
    text = prompts.step_prompt(task, "001-example-app", "Edit `app/scoring.py` — add shade.", 3, 7)
    prefix = prompts.stable_prefix(task, "001-example-app", "step")
    assert text.startswith(prefix)
    assert text.endswith("Result: one line per file changed by step 3.")
    assert text.index("Edit `app/scoring.py`") > len(prefix) - 1
    # the brief is carried once, in the prefix, not repeated by the volatile part
    assert text.count(task.brief) == 1


def test_fix_and_qa_prompts_put_the_evidence_last():
    task = _task()
    report = "FAILING GATES\n$ pytest -q (exit=1)\nE AssertionError"
    fix = prompts.fix_prompt(task, "001-example-app", report, "VERDICT: BLOCKED")
    qa = prompts.qa_prompt(task, "001-example-app", "step summaries")
    assert fix.startswith(prompts.stable_prefix(task, "001-example-app", "fix"))
    assert fix.rstrip().endswith("each change addresses.")
    assert report in fix and "VERDICT: BLOCKED" in fix
    assert qa.startswith(prompts.stable_prefix(task, "001-example-app", "qa"))
    assert "step summaries" in qa


def test_every_crew_description_starts_with_the_same_prefix_it_hashes():
    from swarm.crew import (
        build_fix_crew,
        build_plan_crew,
        build_review_crew,
        build_selfcheck_crew,
        build_senior_crew,
        build_senior_step_crew,
        build_step_crew,
        build_verify_crew,
    )

    task = _task()
    cases = [
        ("step", build_step_crew("001-example-app", task, "Edit `app/scoring.py`.", 1, 2)),
        ("senior_step", build_senior_step_crew("001-example-app", task, "Edit `app/scoring.py`.", 1, 2, "boom")),
        ("fix", build_fix_crew("001-example-app", task, "pytest exit=1")),
        ("selfcheck", build_selfcheck_crew("001-example-app", task, "mypy exit=1")),
        ("senior", build_senior_crew("001-example-app", task, "pytest exit=1")),
        ("qa", build_review_crew("001-example-app", task, "summary")),
        ("verifier", build_verify_crew("001-example-app", task, "context")),
        ("plan", build_plan_crew("001-example-app", task)),
    ]
    for kind, crew in cases:
        description = crew.tasks[0].description
        prefix = prompts.stable_prefix(task, "001-example-app", kind)
        assert description.startswith(prefix), f"{kind} does not start with its stable prefix"
        assert prompts.prompt_prefix(task, "001-example-app", kind)[0].endswith(prefix)


# ---- agent copy ----


def test_agent_roles_stay_what_the_flow_expects():
    frontend = _task("Add `frontend/src/App.svelte` styling.")
    test_work = _task("Add `tests/test_x.py` coverage for the scorer.")
    backend = _task("Add `app/scoring.py`.")
    assert prompts.agent_copy(frontend, "step")["role"] == "Frontend Coder"
    assert prompts.agent_copy(test_work, "step")["role"] == "Test Coder"
    assert prompts.agent_copy(backend, "step")["role"] == "Service Coder"
    assert prompts.agent_copy(backend, "senior")["role"] == "Senior Developer"
    assert prompts.agent_copy(backend, "senior_step")["role"] == "Senior Developer"
    assert prompts.agent_copy(None, "qa")["role"] == "QA Gatekeeper"
    assert prompts.agent_copy(backend, "verifier")["role"] == "Scenario Verifier"


def test_coder_backstory_says_qa_owns_the_gates_once():
    copy = prompts.agent_copy(_task(), "fix")
    assert copy["backstory"].count("QA is the only role that runs the gates") == 1
    assert "gates" in copy["backstory"]
