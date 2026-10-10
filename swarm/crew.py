"""Sequential Planner→Coder→Reviewer crew scoped to one spec task (009 T5)."""

from __future__ import annotations

import re
from pathlib import Path

from crewai import Agent, Crew, Process, Task

from swarm.llms import coder_llm, planner_llm, reviewer_llm
from swarm.spec_loader import SpecTask
from swarm.tools_guarded import EditTool, ShellTool, TrimmedFileReadTool

REPO_ROOT = Path(__file__).resolve().parent.parent


def _coder() -> Agent:
    return Agent(
        role="Python Scaffold Coder",
        goal="Execute one small step with Repo Edit only. Smallest diff.",
        backstory="You write scaffold files precisely. You run no network commands.",
        llm=coder_llm(),
        tools=[TrimmedFileReadTool(), EditTool(), ShellTool()],
        verbose=False,
        max_iter=6,  # micro-steps must finish in a few calls or fail fast
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


STEP_RE = re.compile(r"^STEP\s*(\d+)\s*[:.\-–]\s*(.+)$", re.M)
MAX_STEPS = 8


def parse_steps(plan_text: str) -> list[str]:
    """Split a planner STEP list into executable micro-steps (tiny-coder sized)."""
    steps = [m.group(2).strip() for m in STEP_RE.finditer(plan_text)]
    return steps[:MAX_STEPS]


def build_step_crew(spec_dir: str, task: SpecTask, step_text: str, idx: int, total: int) -> Crew:
    """One coder, one micro-step, fresh message history (bounds context)."""
    coder = _coder()
    ctx = f"spec={spec_dir} task={task.id} ac={','.join(task.ac_refs)}"
    t_step = Task(
        description=(
            f"Execute micro-step {idx}/{total} for {ctx} (no other work):\n{step_text[:2000]}\n"
            "Use Repo Edit for file changes. Loop rules (hard): at most 5 tool calls, "
            "then write the result; never read the same file twice."
        ),
        expected_output=f"Step {idx} diff summary: files changed + one line each.",
        agent=coder,
    )
    return Crew(agents=[coder], tasks=[t_step], process=Process.sequential, verbose=False)


def build_review_crew(spec_dir: str, task: SpecTask, work_summary: str) -> Crew:
    """Reviewer only, after all micro-steps: run gates, paste evidence."""
    reviewer = _reviewer()
    ctx = f"spec={spec_dir} task={task.id} ac={','.join(task.ac_refs)} brief={task.brief}"
    t_verify = Task(
        description=(
            f"Final verification for {ctx}. The coder reports:\n{work_summary[:3000]}\n"
            "Run `pytest`, `ruff check .`, `mypy .` via Guarded Shell and paste exit codes + tails."
        ),
        expected_output="Gate transcripts: pytest exit + ruff exit + mypy exit and PASS/BLOCKED verdict.",
        agent=reviewer,
    )
    return Crew(agents=[reviewer], tasks=[t_verify], process=Process.sequential, verbose=False)

REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_FIX_ROUNDS = 1  # gate fail → coder retry with transcript, then human (no endless loop)


def build_plan_crew(spec_dir: str, task: SpecTask) -> Crew:
    """Planner only: split the task into STEP micro-steps for the tiny coder."""
    read = TrimmedFileReadTool()
    planner = Agent(
        role="Spec Planner",
        goal="Split one spec task into micro-steps. No code writes.",
        backstory="You plan minimal diffs from specs/ context. You never write files.",
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
            "4–8 steps. No other text. Loop rules (hard): at most 6 tool calls, then write the answer; "
            "never read the same file twice; `ls` instead of guessing paths."
        ),
        expected_output="STEP 1: ...\nSTEP 2: ... (4-8 lines, nothing else)",
        agent=planner,
    )
    return Crew(agents=[planner], tasks=[t_plan], process=Process.sequential, verbose=False)


def build_crew(spec_dir: str, task: SpecTask) -> Crew:
    read = TrimmedFileReadTool()
    edit = EditTool()
    shell = ShellTool()
    # NOTE: no DirectoryReadTool — `ls` via Guarded Shell covers listing with
    # far fewer wandering branches for small models.

    planner = Agent(
        role="Spec Planner",
        goal="Expand one spec task into an exact file-operation list. No code writes.",
        backstory="You plan minimal diffs from specs/ context. You never write files.",
        llm=planner_llm(),
        tools=[read, shell],
        verbose=False,
        max_iter=10,  # fail fast: small models loop instead of converging (2026-10-10)
    )
    coder = Agent(
        role="Python Scaffold Coder",
        goal="Execute the plan with Repo Edit only. Smallest diff that satisfies the ACs.",
        backstory="You write scaffold files precisely. You run no network commands.",
        llm=coder_llm(),
        tools=[read, edit, shell],
        verbose=False,
        max_iter=10,  # fail fast: unbounded re-reads blew 262k ctx on Qwen-9B (2026-10-10)
    )
    reviewer = Agent(
        role="QA Gatekeeper",
        goal="Block done unless pytest+ruff+mypy evidence is attached and green.",
        backstory="You verify with Guarded Shell and report exit codes honestly.",
        llm=reviewer_llm(),
        tools=[read, shell],
        verbose=False,
        max_iter=5,
    )

    ctx = f"spec={spec_dir} task={task.id} ac={','.join(task.ac_refs)} brief={task.brief}"
    loop_rules = (
        "Loop rules (hard): at most 6 tool calls, then write the final answer; "
        "never read the same file twice; `ls` instead of guessing paths; "
        "answer from what you already observed."
    )
    t_plan = Task(
        description=(
            f"Split {ctx} into MICRO-STEPS for a tiny coder model (each step: one file, one exact edit, "
            f"independently executable). Read specs/{spec_dir}/spec.md, plan.md, tasks.md and constitution first. "
            "Output format (exact, one per line): `STEP n: <file> — <one precise action>`. "
            "4–8 steps. No other text. Loop rules (hard): at most 6 tool calls, then write the answer; "
            "never read the same file twice; `ls` instead of guessing paths."
        ),
        expected_output="STEP 1: ...\nSTEP 2: ... (4-8 lines, nothing else)",
        agent=planner,
    )
    t_code = Task(
        description=f"Execute the plan for {ctx}. Use Repo Edit for every file change. {loop_rules}",
        expected_output="Diff summary (files changed) + note of any deviation from plan.",
        agent=coder,
        context=[t_plan],
    )
    t_verify = Task(
        description=f"Verify {ctx}: run `pytest`, `ruff check .`, `mypy .` via Guarded Shell and paste exit codes + tails.",
        expected_output="Gate transcripts: pytest exit + ruff exit + mypy exit and PASS/BLOCKED verdict.",
        agent=reviewer,
        context=[t_code],
    )
    return Crew(agents=[planner, coder, reviewer], tasks=[t_plan, t_code, t_verify], process=Process.sequential, verbose=False)


def build_fix_crew(spec_dir: str, task: SpecTask, transcript: str) -> Crew:
    """Coder + Reviewer only: fix what the gates rejected. Bounded by MAX_FIX_ROUNDS in flow."""
    read = TrimmedFileReadTool()
    edit = EditTool()
    shell = ShellTool()

    coder = Agent(
        role="Python Scaffold Coder",
        goal="Fix exactly what the gate transcript rejects. Smallest diff.",
        backstory="You fix scaffold files precisely. You run no network commands.",
        llm=coder_llm(),
        tools=[read, edit, shell],
        verbose=False,
        max_iter=10,
    )
    reviewer = Agent(
        role="QA Gatekeeper",
        goal="Block done unless pytest+ruff+mypy evidence is attached and green.",
        backstory="You verify with Guarded Shell and report exit codes honestly.",
        llm=reviewer_llm(),
        tools=[read, shell],
        verbose=False,
        max_iter=5,
    )
    ctx = f"spec={spec_dir} task={task.id} ac={','.join(task.ac_refs)} brief={task.brief}"
    t_fix = Task(
        description=(
            f"Fix round for {ctx}. The previous attempt FAILED gates:\n{transcript[:3000]}\n"
            "Change only what the transcript rejects. Use Repo Edit for every file change. "
            "Loop rules (hard): at most 6 tool calls, then write the final answer; "
            "never read the same file twice."
        ),
        expected_output="Diff summary of the fix + what gate line each change addresses.",
        agent=coder,
    )
    t_verify = Task(
        description=f"Re-verify {ctx}: run `pytest`, `ruff check .`, `mypy .` via Guarded Shell and paste exit codes + tails.",
        expected_output="Gate transcripts: pytest exit + ruff exit + mypy exit and PASS/BLOCKED verdict.",
        agent=reviewer,
        context=[t_fix],
    )
    return Crew(agents=[coder, reviewer], tasks=[t_fix, t_verify], process=Process.sequential, verbose=False)


def build_exec_crew(spec_dir: str, task: SpecTask, plan_text: str) -> Crew:
    """Coder + Reviewer only, driven by a cached plan — skips re-planning.

    Used when a previous run already produced a good plan but failed downstream.
    """
    read = TrimmedFileReadTool()
    edit = EditTool()
    shell = ShellTool()

    coder = Agent(
        role="Python Scaffold Coder",
        goal="Execute the approved plan with Repo Edit only. Smallest diff that satisfies the ACs.",
        backstory="You write scaffold files precisely. You run no network commands.",
        llm=coder_llm(),
        tools=[read, edit, shell],
        verbose=False,
        max_iter=10,
    )
    reviewer = Agent(
        role="QA Gatekeeper",
        goal="Block done unless pytest+ruff+mypy evidence is attached and green.",
        backstory="You verify with Guarded Shell and report exit codes honestly.",
        llm=reviewer_llm(),
        tools=[read, shell],
        verbose=False,
        max_iter=5,
    )
    ctx = f"spec={spec_dir} task={task.id} ac={','.join(task.ac_refs)} brief={task.brief}"
    loop_rules = (
        "Loop rules (hard): at most 6 tool calls, then write the final answer; "
        "never read the same file twice; `ls` instead of guessing paths; "
        "answer from what you already observed."
    )
    t_code = Task(
        description=(
            f"Execute this APPROVED plan for {ctx} (do not re-plan, do not deviate without reason):\n"
            f"{plan_text[:4000]}\nUse Repo Edit for every file change. {loop_rules}"
        ),
        expected_output="Diff summary (files changed) + note of any deviation from plan.",
        agent=coder,
    )
    t_verify = Task(
        description=f"Verify {ctx}: run `pytest`, `ruff check .`, `mypy .` via Guarded Shell and paste exit codes + tails.",
        expected_output="Gate transcripts: pytest exit + ruff exit + mypy exit and PASS/BLOCKED verdict.",
        agent=reviewer,
        context=[t_code],
    )
    return Crew(agents=[coder, reviewer], tasks=[t_code, t_verify], process=Process.sequential, verbose=False)
