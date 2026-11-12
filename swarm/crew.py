"""Sequential Planner→Coder→Reviewer crew scoped to one spec task (009 T5, 012 AC-8)."""

from __future__ import annotations

from pathlib import Path

from crewai import Agent, Crew, Process, Task

from swarm import prompts
from swarm.llms import (
    coder_llm,
    conflict_llm,
    planner_llm,
    reviewer_llm,
    senior_llm,
    verifier_llm,
)

# Back-compat re-exports: flow.py and the tests import these from swarm.crew.
from swarm.prompts import (
    FIX_RULES,
    MAX_STEPS,
    SCOPE_RULE,
    STEP_RE,
    coder_role,
    gate_commands_hint,
    parse_steps,
    stack_hint,
    steps_usable,
)

__all__ = [
    "DEV_ATTEMPTS",
    "FIX_RULES",
    "MAX_FIX_ROUNDS",
    "MAX_SELF_CHECK_ROUNDS",
    "MAX_STEPS",
    "PLAN_ATTEMPTS",
    "SCOPE_RULE",
    "SENIOR_ATTEMPTS",
    "STEP_ATTEMPTS",
    "STEP_RE",
    "build_conflict_crew",
    "build_fix_crew",
    "build_plan_crew",
    "build_review_crew",
    "build_selfcheck_crew",
    "build_senior_crew",
    "build_senior_step_crew",
    "build_stash_crew",
    "build_step_crew",
    "build_verify_crew",
    "coder_role",
    "gate_commands_hint",
    "parse_steps",
    "stack_hint",
    "steps_usable",
]
from swarm.spec_loader import SpecTask
from swarm.tools_guarded import (
    CreateTool,
    EditTool,
    FullFileReadTool,
    SearchTool,
    ShellTool,
    TrimmedFileReadTool,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _tools(*, allow_gates: bool = False, role: str = "coder") -> list[object]:
    """Coder tools. `allow_gates` is False for every coder-side crew (015 D1)."""
    return [
        TrimmedFileReadTool(),
        # 020 AC-5: locate the line that matters instead of re-reading a range.
        SearchTool(),
        CreateTool(),
        EditTool(),
        ShellTool(allow_gates=allow_gates, agent_role=role),
    ]


def _coder(
    task: SpecTask,
    kind: str,
    *,
    max_iter: int = 6,
    allow_gates: bool = False,
    model_kind: str = "paid",
) -> Agent:
    from swarm.llms import local_coder_llm

    copy = prompts.agent_copy(task, kind)
    llm = local_coder_llm() if model_kind == "local" else coder_llm()
    return Agent(
        role=copy["role"],
        goal=copy["goal"],
        backstory=copy["backstory"],
        llm=llm,
        tools=_tools(allow_gates=allow_gates, role=copy["role"]),
        verbose=False,
        max_iter=max_iter,
    )


def _reviewer() -> Agent:
    copy = prompts.agent_copy(None, "qa")
    return Agent(
        role=copy["role"],
        goal=copy["goal"],
        backstory=copy["backstory"],
        llm=reviewer_llm(),
        tools=[TrimmedFileReadTool(), ShellTool(agent_role="QA Gatekeeper")],
        verbose=False,
        # 015 tuning: 5 gates + `git status` + the verdict need ~7 calls; the old
        # budget of 5 made the model skip a gate and forced the harness fallback.
        # 014-T1 (2026-11-12): 6 gates + `git status` + the verdict + a look at
        # the failing file is ~9 calls, so a budget of 9 left the reviewer
        # re-running `pytest` instead of declaring a verdict — `review_verdict`
        # stayed "unknown" and the run had no grounded reason.
        max_iter=12,
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
    coder = _coder(task, "step", model_kind=model_kind)
    t_step = Task(
        description=prompts.step_prompt(task, spec_dir, step_text, idx, total),
        expected_output=f"Step {idx} diff summary: files changed + one line each.",
        agent=coder,
    )
    return Crew(agents=[coder], tasks=[t_step], process=Process.sequential, verbose=False)


def build_senior_step_crew(spec_dir: str, task: SpecTask, step_text: str, idx: int, total: int, last_error: str) -> Crew:
    """Senior Developer executes one micro-step the junior coder failed repeatedly."""
    copy = prompts.agent_copy(task, "senior_step")
    senior = Agent(
        role=copy["role"],
        goal=copy["goal"],
        backstory=copy["backstory"],
        llm=senior_llm(),
        tools=_tools(role=copy["role"]),
        verbose=False,
        max_iter=12,
    )
    t_step = Task(
        description=prompts.senior_step_prompt(task, spec_dir, step_text, idx, total, last_error),
        expected_output=f"Step {idx} diff summary: files changed + one line each.",
        agent=senior,
    )
    return Crew(agents=[senior], tasks=[t_step], process=Process.sequential, verbose=False)


def build_verify_crew(spec_dir: str, task: SpecTask, context_text: str) -> Crew:
    """Scenario verifier (019): read the whole scenario, judge it, plan only.

    Read-only by construction: `FullFileReadTool` (whole files) and a
    `Guarded Shell` with `allow_gates=False` (inspection only), and **no**
    write tools. Its final answer is the deliverable — `FINDING:` lines, the
    correction steps in the planner's own `STEP n:` format, and one
    `VERDICT: PASS|BLOCKED` line. The harness parses that text; the verifier
    never edits the repository, never runs a gate and never decides green.
    """
    copy = prompts.agent_copy(task, "verifier")
    verifier = Agent(
        role=copy["role"],
        goal=copy["goal"],
        backstory=copy["backstory"],
        llm=verifier_llm(),
        tools=[FullFileReadTool(), ShellTool(allow_gates=False, agent_role="verifier")],
        verbose=False,
        max_iter=12,
    )
    t_verify = Task(
        description=prompts.verify_prompt(task, spec_dir, context_text),
        expected_output=(
            "FINDING lines (one per problem), STEP n correction lines when blocked, "
            "then exactly `VERDICT: PASS` or `VERDICT: BLOCKED`."
        ),
        agent=verifier,
    )
    return Crew(agents=[verifier], tasks=[t_verify], process=Process.sequential, verbose=False)


def build_review_crew(spec_dir: str, task: SpecTask, work_summary: str) -> Crew:
    """Reviewer only, after all micro-steps: run gates, paste evidence, give one verdict."""
    reviewer = _reviewer()
    t_verify = Task(
        description=prompts.qa_prompt(task, spec_dir, work_summary),
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
# 017: coder fix rounds for the static checks (types, lint) before QA sees the
# work. A red type check is a one-line defect, not a QA round-trip.
MAX_SELF_CHECK_ROUNDS = 2


def build_plan_crew(spec_dir: str, task: SpecTask) -> Crew:
    """Planner only: split the task into STEP micro-steps for the tiny coder."""
    copy = prompts.agent_copy(task, "plan")
    planner = Agent(
        role=copy["role"],
        goal=copy["goal"],
        backstory=copy["backstory"],
        llm=planner_llm(),
        tools=[TrimmedFileReadTool(), ShellTool()],
        verbose=False,
        max_iter=10,
    )
    t_plan = Task(
        description=prompts.plan_prompt(task, spec_dir),
        expected_output=f"STEP 1: ...\nSTEP 2: ... (4-{MAX_STEPS} lines, nothing else)",
        agent=planner,
    )
    return Crew(agents=[planner], tasks=[t_plan], process=Process.sequential, verbose=False)


def build_conflict_crew(
    spec_dir: str,
    task_id: str,
    conflicts: list[str],
    *,
    detail: str = "",
) -> Crew:
    """016: one resolver for a `--no-ff` merge conflict. Read + edit only.

    No ShellTool at all: the harness runs the gates and stages the files, so the
    crew cannot mark its own work green.
    """

    resolver = Agent(
        role="Merge Conflict Resolver",
        goal="Merge both sides of a conflicted --no-ff merge without losing either.",
        backstory=(
            "You resolve git merge conflicts. Both sides are wanted: keep the task's "
            "new behaviour AND the base branch's changes, merged coherently. "
            "Remove every conflict marker (<<<<<<<, =======, >>>>>>>). "
            "You never run gates or commits — the harness does that. " + SCOPE_RULE
        ),
        llm=conflict_llm(allow_paid=True),
        tools=[TrimmedFileReadTool(), EditTool()],
        verbose=False,
        max_iter=10,
    )
    files = "\n".join(f"- {p}" for p in conflicts)
    t_resolve = Task(
        description=(
            f"Resolve the merge conflict in spec={spec_dir} task={task_id}.\n"
            f"Conflicted files (edit ONLY these):\n{files}\n\n"
            "Read each file, merge the two sides coherently, and leave no markers. "
            "Keep imports/types consistent with both sides. Smallest correct merge. "
            + (f"\nLatest QA transcript (context only):\n{detail[-1200:]}" if detail else "")
        ),
        expected_output="One line per file: how the two sides were merged.",
        agent=resolver,
    )
    return Crew(agents=[resolver], tasks=[t_resolve], process=Process.sequential, verbose=False)


def build_stash_crew(
    spec_dir: str,
    task_id: str,
    conflicts: list[str],
    *,
    stash: str = "",
    detail: str = "",
) -> Crew:
    """Resolve a conflicted `git stash apply`: read + edit only.

    The stashed side is work parked by an earlier run, the current worktree is
    newer. Both are wanted unless the parked change is already present (the
    duplicate-merge case that used to make `--ours` the only safe choice).
    """

    resolver = Agent(
        role="Stash Conflict Resolver",
        goal="Re-apply parked work on top of newer work without losing either side.",
        backstory=(
            "You resolve a conflicted `git stash apply`. `Updated upstream` is the "
            "current worktree: newer, already gated and merged. `Stashed changes` is "
            "work parked by an earlier run. Keep both when they are different work. "
            "If the stashed side is already present or clearly superseded (a "
            "regenerated lockfile, the same edit applied twice), keep the current "
            "version instead of duplicating it. Remove every conflict marker "
            "(<<<<<<<, =======, >>>>>>>). You never run gates or commits — the "
            "harness does that. " + SCOPE_RULE
        ),
        llm=conflict_llm(allow_paid=True),
        tools=[TrimmedFileReadTool(), EditTool()],
        verbose=False,
        max_iter=10,
    )
    files = "\n".join(f"- {p}" for p in conflicts)
    t_resolve = Task(
        description=(
            f"Resolve the stash conflict in spec={spec_dir} task={task_id}.\n"
            + (f"Stash: {stash}\n" if stash else "")
            + f"Conflicted files (edit ONLY these):\n{files}\n\n"
            "Read each file, merge the parked work into the current version, and "
            "leave no markers. Do not duplicate a change that is already there. "
            "Smallest correct result. "
            + (f"\nLatest run transcript (context only):\n{detail[-1200:]}" if detail else "")
        ),
        expected_output="One line per file: what was kept from each side.",
        agent=resolver,
    )
    return Crew(agents=[resolver], tasks=[t_resolve], process=Process.sequential, verbose=False)


def build_fix_crew(
    spec_dir: str, task: SpecTask, qa_report_text: str, qa_review: str = ""
) -> Crew:
    """Coder only: fix what QA's report proves is broken (015 D1).

    QA is invoked by the flow after this crew, so a round is: QA report → coder
    fix (no gates) → QA re-verification. The coder never runs gates.
    """
    coder = _coder(task, "fix", max_iter=14, allow_gates=False)
    t_fix = Task(
        description=prompts.fix_prompt(task, spec_dir, qa_report_text, qa_review),
        expected_output=(
            "Diff summary of the fix + which reported gate line each change addresses."
        ),
        agent=coder,
    )
    return Crew(agents=[coder], tasks=[t_fix], process=Process.sequential, verbose=False)


def build_selfcheck_crew(spec_dir: str, task: SpecTask, report_text: str) -> Crew:
    """Coder only: fix the type/lint errors found before QA (017).

    The harness ran the project's static checks (type checker, linter) after
    the micro-steps; the coder gets their exit codes and error output and
    fixes the cause. QA stays the only gate executor: this crew runs no
    gates, so it cannot certify its own work.
    """
    coder = _coder(task, "selfcheck", max_iter=12, allow_gates=False)
    t_fix = Task(
        description=prompts.selfcheck_prompt(task, spec_dir, report_text),
        expected_output=(
            "Diff summary of the fix + which reported type/lint line each change addresses."
        ),
        agent=coder,
    )
    return Crew(agents=[coder], tasks=[t_fix], process=Process.sequential, verbose=False)


def build_senior_crew(spec_dir: str, task: SpecTask, qa_report_text: str, qa_review: str = "") -> Crew:
    """Senior Developer only: one-shot escalation after repeated QA rejections.

    QA re-verifies afterwards in the flow (same contract as a normal fix round).
    """
    copy = prompts.agent_copy(task, "senior")
    senior = Agent(
        role=copy["role"],
        goal=copy["goal"],
        backstory=copy["backstory"],
        llm=senior_llm(),
        tools=_tools(allow_gates=False, role=copy["role"]),
        verbose=False,
        max_iter=16,
    )
    t_fix = Task(
        description=prompts.senior_prompt(task, spec_dir, qa_report_text, qa_review),
        expected_output=(
            "Diff summary of the fix + which reported gate line each change addresses."
        ),
        agent=senior,
    )
    return Crew(agents=[senior], tasks=[t_fix], process=Process.sequential, verbose=False)
