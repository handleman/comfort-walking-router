"""Sequential Planner→Coder→Reviewer crew scoped to one spec task (009 T5, 012 AC-8)."""

from __future__ import annotations

import os
import re
from pathlib import Path

from crewai import Agent, Crew, Process, Task

from swarm.llms import coder_llm, planner_llm, reviewer_llm
from swarm.spec_loader import SpecTask
from swarm.tools_guarded import (
    DEFAULT_SCOPE,
    CreateTool,
    EditTool,
    ShellTool,
    TrimmedFileReadTool,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _scope_rule() -> str:
    """Prompt text derived from the same scope the tools enforce (no drift)."""
    dirs = [s for s in DEFAULT_SCOPE if s.endswith("/")]
    files = [s for s in DEFAULT_SCOPE if not s.endswith("/")]
    return (
        "Touch ONLY files under " + ", ".join(dirs)
        + " and these exact files: " + ", ".join(files) + ". "
        "NEVER modify swarm/, specs/, docs/, .env*."
    )


SCOPE_RULE = _scope_rule()

STEP_RE = re.compile(r"^STEP\s*(\d+)\s*[:.\-–]\s*(.+)$", re.MULTILINE)
# Findings from 001-T2 thrash (2026-10-10): fix rounds converged only when the
# agent fixed coherently instead of patching single lines. Shared by fix + senior crews.
FIX_RULES = (
    "Fix COMPLETELY and coherently, not one line at a time: imports must resolve "
    "(relative imports within the package, never bare top-level names for package "
    "modules); sync/async must match (never await a sync function — make the caller "
    "match its callees); implementations must match their ABC signatures. "
    "If the transcript contains type-checker errors, diagnose the real "
    "mismatch first: read the failing expression, infer the type from the API "
    "response/contract or an existing interface, reuse/extend that type, and narrow "
    "unions with real guards. Try that before any escape. If a correct typing is "
    "genuinely impossible within this task, the language's narrow last-resort "
    "suppression is allowed — say why in your final answer. Never delete or disable "
    "the feature, and never blanket-suppress a file. "
    "Delete stray files you created at wrong paths instead of leaving them."
)
# 015 D1: QA is the only gate executor. Coders never run gates; they work from
# QA's report (per-gate argv, exit code, failure output). The flow drives
# QA→coder→QA rounds, bounded by MAX_FIX_ROUNDS.
MAX_STEPS = 8


def gate_commands_hint() -> str:
    """The project's gate commands (config-driven; no stack assumptions)."""
    raw = os.getenv("SWARM_GATE_COMMANDS", "").strip()
    commands = [c.strip() for c in re.split(r"[;\n]", raw) if c.strip()] or [
        "pytest -q",
        "ruff check .",
        "mypy app tests",
    ]
    return ", ".join(f"`{command}`" for command in commands)


def parse_steps(plan_text: str) -> list[str]:
    """Split a planner STEP list into executable micro-steps. Never truncates."""
    return [m.group(2).strip() for m in STEP_RE.finditer(plan_text) if m.group(2).strip()]


def steps_usable(steps: list[str]) -> bool:
    """A plan is usable only when it fits the micro-step budget and each step is sane."""
    return 1 <= len(steps) <= MAX_STEPS and all(3 <= len(s) <= 500 for s in steps)


def coder_role(task: SpecTask) -> str:
    """Pick a role from the task text; stack names are examples, not assumptions."""
    text = task.brief.lower()
    if any(
        k in text
        for k in (
            "frontend/",
            "ui/",
            "component",
            "react",
            "vue",
            "angular",
            "svelte",
            "typescript",
            "javascript",
            "css",
            "tailwind",
            "vite",
            "npm ",
        )
    ):
        return "Frontend Coder"
    if any(k in text for k in ("tests/", "test_", "pytest", "test")):
        return "Test Coder"
    return "Service Coder"


def _stack_hint(task: SpecTask) -> str:
    role = coder_role(task)
    if role == "Frontend Coder":
        return (
            "This is UI/frontend work. QA type-checks the frontend with the project gates "
            "(`SWARM_GATE_COMMANDS`); write code that passes them and never run the gates "
            "yourself. Treat type-checker errors as design "
            "feedback: read the failing expression, infer the type from the API response/contract "
            "or an existing interface, reuse or extend that type, and narrow unions properly. "
            "Try that first. If no correct typing is possible in the task, a narrow last-resort "
            "type suppression is acceptable with an explanation; deleting/disabling the feature "
            "or blanket-suppressing the file is not."
        )
    if role == "Test Coder":
        return "This is test work: add focused coverage; do not change behavior beyond the brief."
    return "This is service/backend work: keep imports, types, and public contracts coherent."


def _tools(*, allow_gates: bool = False, role: str = "coder") -> list[object]:
    """Coder tools. `allow_gates` is False for every coder-side crew (015 D1)."""
    return [
        TrimmedFileReadTool(),
        CreateTool(),
        EditTool(),
        ShellTool(allow_gates=allow_gates, agent_role=role),
    ]


def _coder(
    task: SpecTask,
    *,
    goal: str,
    backstory: str,
    max_iter: int = 6,
    allow_gates: bool = False,
    model_kind: str = "paid",
) -> Agent:
    from swarm.llms import local_coder_llm

    llm = local_coder_llm() if model_kind == "local" else coder_llm()
    return Agent(
        role=coder_role(task),
        goal=goal,
        backstory=(
            backstory
            + " QA is the only role that runs the gates and you never run them. "
            "When QA blocks, its report lists each gate command, its exit code, and the "
            "failure output: investigate from that evidence. " + _stack_hint(task)
        ),
        llm=llm,
        tools=_tools(allow_gates=allow_gates, role=coder_role(task)),
        verbose=False,
        max_iter=max_iter,
    )


def _reviewer() -> Agent:
    return Agent(
        role="QA Gatekeeper",
        goal="Block done unless every configured gate is attached and green.",
        backstory=(
            "You are the only role that runs the project gates; the coder never runs them. "
            "You run every configured gate with Guarded Shell, then report each command, "
            "its exit code, and the failure output so the coder can investigate. "
            "Never paste source code or repeat the work summary. "
            "Prefer real type fixes. A fix that removes/disables the feature or "
            "blanket-suppresses types is BLOCKED; a narrow, explained last-resort "
            "suppression may PASS when gates are green and the feature is intact."
        ),
        llm=reviewer_llm(),
        tools=[TrimmedFileReadTool(), ShellTool(agent_role="QA Gatekeeper")],
        verbose=False,
        # 015 tuning: 5 gates + `git status` + the verdict need ~7 calls; the old
        # budget of 5 made the model skip a gate and forced the harness fallback.
        max_iter=9,
    )


def build_step_crew(
    spec_dir: str,
    task: SpecTask,
    step_text: str,
    idx: int,
    total: int,
    model_kind: str = "paid",
) -> Crew:
    """One coder, one micro-step, fresh message history (bounds context)."""
    coder = _coder(
        task,
        goal="Execute one small step with Repo Edit only. Smallest diff.",
        backstory="You write scaffold files precisely. You run no network commands.",
        model_kind=model_kind,
    )
    ctx = f"spec={spec_dir} task={task.id} ac={','.join(task.ac_refs)}"
    t_step = Task(
        description=(
            f"Execute micro-step {idx}/{total} for {ctx} (no other work):\n{step_text[:2000]}\n"
            "Use Repo Create for new files, Repo Edit for existing ones. Loop rules (hard): at most 5 tool calls, "
            "then write the result; never read the same file twice. " + SCOPE_RULE
        ),
        expected_output=f"Step {idx} diff summary: files changed + one line each.",
        agent=coder,
    )
    return Crew(agents=[coder], tasks=[t_step], process=Process.sequential, verbose=False)


def build_senior_step_crew(spec_dir: str, task: SpecTask, step_text: str, idx: int, total: int, last_error: str) -> Crew:
    """Senior Developer executes one micro-step the junior coder failed repeatedly."""
    from swarm.llms import senior_llm

    senior = Agent(
        role="Senior Developer",
        goal="Execute one small step completely and coherently. No thrash.",
        backstory=(
            "You are the senior escalation for a single stuck step: the junior coder "
            "failed it repeatedly. Read the step and the last error, then do it right "
            "in one pass. You run no network commands. " + _stack_hint(task)
        ),
        llm=senior_llm(),
        tools=_tools(role="Senior Developer"),
        verbose=False,
        max_iter=12,
    )
    ctx = f"spec={spec_dir} task={task.id} ac={','.join(task.ac_refs)}"
    t_step = Task(
        description=(
            f"Senior rescue for micro-step {idx}/{total} for {ctx} (no other work):\n{step_text[:2000]}\n"
            f"The junior failed with: {last_error[:1000]}\n"
            "Use Repo Create for new files, Repo Edit for existing ones. " + FIX_RULES + " "
            "Loop rules (hard): at most 10 tool calls, then write the result. " + SCOPE_RULE
        ),
        expected_output=f"Step {idx} diff summary: files changed + one line each.",
        agent=senior,
    )
    return Crew(agents=[senior], tasks=[t_step], process=Process.sequential, verbose=False)


def build_review_crew(spec_dir: str, task: SpecTask, work_summary: str) -> Crew:
    """Reviewer only, after all micro-steps: run gates, paste evidence, give one verdict."""
    reviewer = _reviewer()
    ctx = f"spec={spec_dir} task={task.id} ac={','.join(task.ac_refs)} brief={task.brief}"
    t_verify = Task(
        description=(
            f"Final verification for {ctx}. The coder reports:\n{work_summary[:3000]}\n"
            f"Run EVERY project gate via Guarded Shell: {gate_commands_hint()}. "
            "You are the only agent allowed to run them. For each: paste the command, "
            "its exit code, and the failure output (failing test ids, lint rules, type "
            "errors) — the coder fixes from this report and must not re-run anything. "
            "Also list changed files via `git status --short`: if the coder changed nothing "
            "relevant to the brief, verdict BLOCKED (no-op), never PASS on an empty diff. "
            "If type-checker errors were suppressed with a blanket suppression or by "
            "removing/disabling the feature, verdict BLOCKED; a narrow, explained last-resort "
            "escape is acceptable when the feature is intact. "
            "Final answer format: for each gate `command → exit=<code>`; on BLOCKED, also "
            "include the failing output for that gate (up to 120 lines) and one line naming "
            "the root cause. On PASS keep it to one line per gate. End with exactly "
            "`VERDICT: PASS` or `VERDICT: BLOCKED`. Never paste whole source files or repeat "
            "the work summary; the verdict word must be present."
        ),
        expected_output=(
            "Per gate: command, exit code, and on BLOCKED the failure output; "
            "then `VERDICT: PASS` or `VERDICT: BLOCKED`."
        ),
        agent=reviewer,
    )
    return Crew(agents=[reviewer], tasks=[t_verify], process=Process.sequential, verbose=False)


# 015 tuning, derived from 24 green runs (cost p50 $0.0097 / p90 $0.0295,
# duration p50 237s / p75 454s): three QA→coder rounds converge for 19/24 tasks,
# retries now resume finished steps, so extra dev attempts only burn money.
MAX_FIX_ROUNDS = 3  # QA→coder→QA rounds before senior escalation/human
DEV_ATTEMPTS = 2  # full dev phases (steps + review + fix rounds) before senior
SENIOR_ATTEMPTS = 2  # senior passes (free model) before giving up to human
STEP_ATTEMPTS = 2  # step kickoff tries; the second already runs on the paid model
PLAN_ATTEMPTS = 2  # planner retries on unparseable output before giving up


def build_plan_crew(spec_dir: str, task: SpecTask) -> Crew:
    """Planner only: split the task into STEP micro-steps for the tiny coder."""
    read = TrimmedFileReadTool()
    planner = Agent(
        role="Spec Planner",
        goal="Split one spec task into micro-steps. No code writes.",
        backstory="You plan minimal diffs from specs/ context. You never write files. " + _stack_hint(task),
        llm=planner_llm(),
        tools=[read, ShellTool()],
        verbose=False,
        max_iter=10,
    )
    ctx = f"spec={spec_dir} task={task.id} ac={','.join(task.ac_refs)} brief={task.brief}"
    t_plan = Task(
        description=(
            f"Split {ctx} into MICRO-STEPS for a tiny coder model (each step: one file, one exact edit, "
            f"independently executable). Read specs/{spec_dir}/spec.md, plan.md, tasks.md and constitution first. "
            "Output format (exact, one per line): `STEP n: <file> — <one precise action>`. "
            f"4–{MAX_STEPS} steps. No other text. Loop rules (hard): at most 6 tool calls, then write the answer; "
            "never read the same file twice; `ls` instead of guessing paths. " + SCOPE_RULE
        ),
        expected_output=f"STEP 1: ...\nSTEP 2: ... (4-{MAX_STEPS} lines, nothing else)",
        agent=planner,
    )
    return Crew(agents=[planner], tasks=[t_plan], process=Process.sequential, verbose=False)


def build_fix_crew(
    spec_dir: str, task: SpecTask, qa_report_text: str, qa_review: str = ""
) -> Crew:
    """Coder only: fix what QA's report proves is broken (015 D1).

    QA is invoked by the flow after this crew, so a round is: QA report → coder
    fix (no gates) → QA re-verification. The coder never runs gates.
    """
    coder = _coder(
        task,
        goal="Investigate QA's report, then fix the real cause. Smallest coherent diff.",
        backstory=(
            "You fix scaffold files precisely. QA has already run the gates and rejected "
            "this attempt; you work from its exit codes and failure output. "
            "You run no network commands and no gates."
        ),
        max_iter=14,
        allow_gates=False,
    )
    ctx = f"spec={spec_dir} task={task.id} ac={','.join(task.ac_refs)} brief={task.brief}"
    qa_block = (
        f"QA's verdict note:\n{qa_review[-1200:]}\n" if qa_review.strip() else ""
    )
    t_fix = Task(
        description=(
            f"Fix round for {ctx}. QA ran the gates and its report is your evidence:\n"
            f"{qa_report_text[:7000]}\n"
            + qa_block
            + "Investigate the real cause before editing: read the files named in the "
            "report and follow the failing test/lint/type lines. Fix the cause, not the "
            "symptom. If the report is a Prettier/code-style failure, run "
            "`npm --prefix frontend run format` first (allowed in fix rounds). "
            "Change only what the report proves is wrong. "
            "Use Repo Create for new files, Repo Edit for existing files. "
            + FIX_RULES
            + " Loop rules (hard): at most 12 tool calls, then write the final answer; "
            "never read the same file twice. " + SCOPE_RULE
        ),
        expected_output=(
            "Diff summary of the fix + which reported gate line each change addresses."
        ),
        agent=coder,
    )
    return Crew(agents=[coder], tasks=[t_fix], process=Process.sequential, verbose=False)


def build_senior_crew(spec_dir: str, task: SpecTask, qa_report_text: str, qa_review: str = "") -> Crew:
    """Senior Developer only: one-shot escalation after repeated QA rejections.

    QA re-verifies afterwards in the flow (same contract as a normal fix round).
    """
    from swarm.llms import senior_llm

    senior = Agent(
        role="Senior Developer",
        goal="Investigate why QA keeps blocking, fix every failure in one pass. No thrash.",
        backstory=(
            "You are the senior escalation: the junior coder failed repeatedly and QA kept "
            "returning BLOCKED. QA owns the gates, so its exit codes and failure output are "
            "your evidence. You run no network commands and no gates. " + _stack_hint(task)
        ),
        llm=senior_llm(),
        tools=_tools(allow_gates=False, role="Senior Developer"),
        verbose=False,
        max_iter=16,
    )
    ctx = f"spec={spec_dir} task={task.id} ac={','.join(task.ac_refs)} brief={task.brief}"
    qa_block = f"QA's latest BLOCKED note:\n{qa_review[-1200:]}\n" if qa_review.strip() else ""
    t_fix = Task(
        description=(
            f"Senior fix for {ctx}. QA report:\n{qa_report_text[:7000]}\n"
            + qa_block
            + "Find the root cause and fix EVERY reported failure in one pass. "
            + FIX_RULES
            + " Use Repo Create for new files, Repo Edit for existing files. "
            "Loop rules (hard): at most 14 tool calls, then write the final answer; "
            "never read the same file twice. " + SCOPE_RULE
        ),
        expected_output=(
            "Diff summary of the fix + which reported gate line each change addresses."
        ),
        agent=senior,
    )
    return Crew(agents=[senior], tasks=[t_fix], process=Process.sequential, verbose=False)
