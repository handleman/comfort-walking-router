"""Sequential Planner→Coder→Reviewer crew scoped to one spec task (009 T5)."""

from __future__ import annotations

from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai_tools import DirectoryReadTool, FileReadTool

from swarm.llms import coder_llm, planner_llm, reviewer_llm
from swarm.spec_loader import SpecTask
from swarm.tools_guarded import EditTool, ShellTool

REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_FIX_ROUNDS = 1  # gate fail → coder retry with transcript, then human (no endless loop)


def build_crew(spec_dir: str, task: SpecTask) -> Crew:
    read = FileReadTool()
    ls = DirectoryReadTool()
    edit = EditTool()
    shell = ShellTool()

    planner = Agent(
        role="Spec Planner",
        goal="Expand one spec task into an exact file-operation list. No code writes.",
        backstory="You plan minimal diffs from specs/ context. You never write files.",
        llm=planner_llm(),
        tools=[read, ls],
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
    t_plan = Task(
        description=f"Expand {ctx} into an exact file list + edit sequence. Read specs/{spec_dir}/spec.md, plan.md, tasks.md and constitution first.",
        expected_output="Ordered file-operation list with exact paths and one-line purpose each.",
        agent=planner,
    )
    t_code = Task(
        description=f"Execute the plan for {ctx}. Use Repo Edit for every file change.",
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
    read = FileReadTool()
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
            "Change only what the transcript rejects. Use Repo Edit for every file change."
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
