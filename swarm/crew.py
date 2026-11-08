"""Sequential Planner→Coder→Reviewer crew scoped to one spec task (009 T5, 012 AC-8)."""

from __future__ import annotations

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
    "match its callees); implementations must match their ABC signatures. Run "
    "`ruff check --fix .` first for mechanical nits, then hand-fix the rest. "
    "Delete stray files you created at wrong paths instead of leaving them."
)
MAX_STEPS = 8


def parse_steps(plan_text: str) -> list[str]:
    """Split a planner STEP list into executable micro-steps. Never truncates."""
    return [m.group(2).strip() for m in STEP_RE.finditer(plan_text) if m.group(2).strip()]


def steps_usable(steps: list[str]) -> bool:
    """A plan is usable only when it fits the micro-step budget and each step is sane."""
    return 1 <= len(steps) <= MAX_STEPS and all(3 <= len(s) <= 500 for s in steps)


def coder_role(task: SpecTask) -> str:
    """Pick a role that matches the task's stack, not just Python scaffold work."""
    text = task.brief.lower()
    if any(k in text for k in ("frontend/", ".svelte", "svelte", "typescript", "vite", "npm ", "leaflet")):
        return "Frontend Coder"
    if any(k in text for k in ("tests/", "test_", "pytest", "test")):
        return "Test Coder"
    return "Python Scaffold Coder"


def _stack_hint(task: SpecTask) -> str:
    role = coder_role(task)
    if role == "Frontend Coder":
        return "This is frontend work: Svelte/TypeScript/npm; keep `npm run check`/`build` green."
    if role == "Test Coder":
        return "This is test work: add focused pytest coverage; do not change behavior beyond the brief."
    return "This is Python backend work: keep imports, types, and FastAPI contracts coherent."


def _tools() -> list[object]:
    return [TrimmedFileReadTool(), CreateTool(), EditTool(), ShellTool()]


def _coder(task: SpecTask, *, goal: str, backstory: str, max_iter: int = 6) -> Agent:
    return Agent(
        role=coder_role(task),
        goal=goal,
        backstory=backstory + " " + _stack_hint(task),
        llm=coder_llm(),
        tools=_tools(),
        verbose=False,
        max_iter=max_iter,
    )


def _reviewer() -> Agent:
    return Agent(
        role="QA Gatekeeper",
        goal="Block done unless pytest+ruff+mypy evidence is attached and green.",
        backstory="You verify with Guarded Shell and report exit codes honestly.",
        llm=reviewer_llm(),
        tools=[TrimmedFileReadTool(), ShellTool()],
        verbose=False,
        max_iter=5,
    )


def build_step_crew(spec_dir: str, task: SpecTask, step_text: str, idx: int, total: int) -> Crew:
    """One coder, one micro-step, fresh message history (bounds context)."""
    coder = _coder(
        task,
        goal="Execute one small step with Repo Edit only. Smallest diff.",
        backstory="You write scaffold files precisely. You run no network commands.",
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
        tools=_tools(),
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
            "Run `pytest`, `ruff check .`, `mypy app tests` via Guarded Shell and paste exit codes + tails. "
            "Also list changed files via `git status --short`: if the coder changed nothing "
            "relevant to the brief, verdict BLOCKED (no-op), never PASS on an empty diff. "
            "End with exactly one verdict word: PASS or BLOCKED."
        ),
        expected_output="Gate transcripts: pytest exit + ruff exit + mypy exit and PASS/BLOCKED verdict.",
        agent=reviewer,
    )
    return Crew(agents=[reviewer], tasks=[t_verify], process=Process.sequential, verbose=False)


MAX_FIX_ROUNDS = 2  # gate fail → coder retry with transcript (twice), then escalate/human
DEV_ATTEMPTS = 3  # dev phase (steps + review + fix round) retries before senior escalation
SENIOR_ATTEMPTS = 2  # senior one-shot fix passes before giving up to human
STEP_ATTEMPTS = 3  # micro-step kickoff retries before senior step rescue
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


def build_fix_crew(spec_dir: str, task: SpecTask, transcript: str) -> Crew:
    """Coder + Reviewer only: fix what the gates rejected. Bounded by MAX_FIX_ROUNDS in flow."""
    coder = _coder(
        task,
        goal="Fix exactly what the gate transcript rejects. Smallest diff.",
        backstory="You fix scaffold files precisely. You run no network commands.",
        max_iter=10,
    )
    reviewer = _reviewer()
    ctx = f"spec={spec_dir} task={task.id} ac={','.join(task.ac_refs)} brief={task.brief}"
    t_fix = Task(
        description=(
            f"Fix round for {ctx}. The previous attempt FAILED gates:\n{transcript[:3000]}\n"
            "Change only what the transcript rejects. Use Repo Create for new files, Repo Edit for existing files. "
            + FIX_RULES + " "
            "Loop rules (hard): at most 6 tool calls, then write the final answer; "
            "never read the same file twice. " + SCOPE_RULE
        ),
        expected_output="Diff summary of the fix + what gate line each change addresses.",
        agent=coder,
    )
    t_verify = Task(
        description=f"Re-verify {ctx}: run `pytest`, `ruff check .`, `mypy app tests` via Guarded Shell and paste exit codes + tails. End with PASS or BLOCKED.",
        expected_output="Gate transcripts: pytest exit + ruff exit + mypy exit and PASS/BLOCKED verdict.",
        agent=reviewer,
        context=[t_fix],
    )
    return Crew(agents=[coder, reviewer], tasks=[t_fix, t_verify], process=Process.sequential, verbose=False)


def build_senior_crew(spec_dir: str, task: SpecTask, transcript: str) -> Crew:
    """Senior Developer (strong free-tier brain) + QA Reviewer: one-shot escalation.

    Used after DEV_ATTEMPTS dev phases all failed gates. The senior fixes ALL
    gate failures in one pass then hands back to QA for re-verification.
    """
    from swarm.llms import senior_llm

    senior = Agent(
        role="Senior Developer",
        goal="Fix every gate failure in one pass. Largest diff necessary, no thrash.",
        backstory=(
            "You are the senior escalation: the junior coder failed repeatedly. "
            "Read the gate transcript, fix every failure completely and coherently "
            "(imports must resolve, sync/async must match, types must check). "
            "You run no network commands. " + _stack_hint(task)
        ),
        llm=senior_llm(),
        tools=_tools(),
        verbose=False,
        max_iter=12,
    )
    reviewer = _reviewer()
    ctx = f"spec={spec_dir} task={task.id} ac={','.join(task.ac_refs)} brief={task.brief}"
    t_fix = Task(
        description=(
            f"Senior fix for {ctx}. The junior dev FAILED gates repeatedly, latest transcript:\n{transcript[:4000]}\n"
            "Fix EVERY failure in one pass. " + FIX_RULES + " "
            "Use Repo Create for new files, Repo Edit for existing files. "
            "Loop rules (hard): at most 10 tool calls, then write the final answer; "
            "never read the same file twice. " + SCOPE_RULE
        ),
        expected_output="Diff summary of the fix + what gate line each change addresses.",
        agent=senior,
    )
    t_verify = Task(
        description=f"Re-verify {ctx}: run `pytest`, `ruff check .`, `mypy app tests` via Guarded Shell and paste exit codes + tails. End with PASS or BLOCKED.",
        expected_output="Gate transcripts: pytest exit + ruff exit + mypy exit and PASS/BLOCKED verdict.",
        agent=reviewer,
        context=[t_fix],
    )
    return Crew(agents=[senior, reviewer], tasks=[t_fix, t_verify], process=Process.sequential, verbose=False)
