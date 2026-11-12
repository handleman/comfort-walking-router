"""One assembly point for prompt text (020 T2, AC-2).

Every per-task crew builds its prompt from here, in two parts:

    description = stable_prefix(...) + "\\n\\n" + volatile part

The stable prefix is a pure function of the task and the spec artifacts, so two
steps (or two fix rounds) of the same task send a byte-identical prefix. That is
the precondition for provider prompt caching and for Ollama's prefix KV reuse:
a prompt that reassembles its own head every round cannot be cached. The
volatile tail (step text, round number, report, work summary) comes last.

Stable prefix (in order): role, goal, backstory (see `agent_copy`), task
context (spec/task/AC ids, brief, the referenced AC paragraphs), fixed rules
for the role (scope, read-real-API, loop limits, gate/verifier contracts).

`prompt_prefix(task, spec_dir, kind)` returns the provider-order prefix and its
short hash; `swarm/bench` records the hash per case.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from swarm.spec_loader import SpecTask

REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_STEPS = 8
MAX_AC_CHARS = 900
# 021 T5: put the referenced AC paragraphs back into the coder prefix. 020 T2
# excluded them to keep the prefix lean; this is the A/B for that decision.
CODER_ACS_ENV = "SWARM_CODER_ACS"


def coder_acs_enabled(env: dict[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return str(source.get(CODER_ACS_ENV, "0")).strip().lower() in {"1", "true", "yes"}
MAX_PLAN_LINES = 12

_BACKTICK_PATH_RE = re.compile(r"`([A-Za-z0-9_./-]+\.[A-Za-z0-9]+)`")
_BARE_PATH_RE = re.compile(
    r"(?<![\w/`])((?:app|tests|frontend|contracts|docs|swarm)/[\w./-]+\.[A-Za-z0-9]+)"
)


def brief_paths(brief: str) -> list[str]:
    """Files the brief names, in first-mention order, de-duplicated."""
    found = [m.group(1) for m in _BACKTICK_PATH_RE.finditer(brief or "")]
    found += [m.group(1) for m in _BARE_PATH_RE.finditer(brief or "")]
    out: list[str] = []
    seen: set[str] = set()
    for raw in found:
        path = raw.removeprefix("./").strip()
        if path and path not in seen:
            seen.add(path)
            out.append(path)
    return out


# ---------------------------------------------------------------------------
# role: the agent block, and the fixed rules that follow it in the description
# ---------------------------------------------------------------------------


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


def stack_hint(task: SpecTask) -> str:
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


def scope_rule() -> str:
    """Prompt text derived from the same scope the tools enforce (no drift)."""
    from swarm.tools_guarded import DEFAULT_SCOPE

    dirs = [s for s in DEFAULT_SCOPE if s.endswith("/")]
    files = [s for s in DEFAULT_SCOPE if not s.endswith("/")]
    return (
        "Touch ONLY files under " + ", ".join(dirs)
        + " and these exact files: " + ", ".join(files) + ". "
        "NEVER modify swarm/, specs/, docs/, .env*."
    )


SCOPE_RULE = scope_rule()

QA_IS_THE_GATEKEEPER = (
    " QA is the only role that runs the gates and you never run them. "
    "When QA blocks, its report lists each gate command, its exit code, and the "
    "failure output: investigate from that evidence."
)

STEP_RULES = (
    "Before you write code for an existing module, read that module once and use "
    "its REAL exported API — never invent a function, store or field. If the API "
    "you need does not exist, add it in this task's scope instead of calling "
    "something imaginary. "
    "When the step writes a test, IMPORT the module under test (e.g. "
    "`import { walkMode } from '../walkMode'`) and call its real exports. Never "
    "re-declare a local copy of the code under test and never stub the function "
    "you are testing: a test that tests its own fake proves nothing. "
    "Use Repo Create for new files, Repo Edit for existing ones. Loop rules (hard): "
    "at most 5 tool calls, then write the result; never read the same file twice."
)

# Findings from 001-T2 thrash (2026-10-10): fix rounds converged only when the
# agent fixed coherently instead of patching single lines. Shared by fix + senior.
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

FIX_READ_RULES = (
    "The report lists the FAILING gates first, each with its exit code, the "
    "key lines (file:line: message) and the raw output. Fix exactly those "
    "lines: read the file named in a key line once, change the cause, move on. "
    "Never re-read a file you already read in this round. "
    "If a key line says a name is missing or a type does not match, the module "
    "that should provide it is named nearby: read it once and use its REAL API. "
    "If the API you need does not exist, add it in this task's scope instead of "
    "inventing calls to it. If the file under repair re-declares the module it "
    "should import, replace the local copy with the real import. "
    "If the only failing gate is a lint/format gate, the harness already ran the "
    "project formatter, so what is left is a rule violation, not a wrap: fix the "
    "rule (never disable it). "
    "Change only what the report proves is wrong."
)

PLAN_RULES = (
    "Split the task into MICRO-STEPS for a tiny coder model (each step: one file, "
    "one exact edit, independently executable). Read the spec documents first. "
    "Before a step touches an existing module, read that module so the step names "
    "its REAL exported API — a step that writes a test must name the module under "
    "test, the import path to use and the functions it calls. Never plan a call to "
    "a function you have not seen, and never plan a test that re-declares the code "
    "under test. "
    "Output format (exact, one per line): `STEP n: <file> — <one precise action>`. "
    f"4–{MAX_STEPS} steps. No other text. Loop rules (hard): at most 6 tool calls, "
    "then write the answer; never read the same file twice; `ls` instead of guessing paths."
)

QA_RULES = (
    "You are the only agent allowed to run the gates. Run EVERY project gate via "
    "Guarded Shell. For each: paste the command, its exit code, and the failure "
    "output (failing test ids, lint rules, type errors) — the coder fixes from this "
    "report and must not re-run anything. "
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
)

VERIFIER_RULES = (
    "Answer ONE question: does the implemented scenario do what the brief says, "
    "end to end? Check three things:\n"
    "1. EVERY element the brief names exists (file, endpoint, component, test). "
    "Read the files with the read tool; it returns whole files.\n"
    "2. The pieces CONNECT: an endpoint is mounted where the app serves it; a "
    "component imports the REAL module instead of a local copy; the pinned "
    "contract and the code agree; a test imports the module it tests.\n"
    "3. The referenced acceptance criteria are addressed.\n"
    "The connection view is a best-effort static scan — a missing edge is a "
    "hint, not a proof; verify a suspected duplicate by reading both files. "
    "Judge the scenario only: no style or taste, no gate runs, no edits. "
    "Do NOT prescribe how a test mocks, structures its fixtures or names its "
    "cases: require the behaviour the acceptance criterion names. If a "
    "correction step was already applied, judge the resulting scenario; do not "
    "restate the same design preference in different words.\n\n"
    "Output format (exact, no other prose):\n"
    "FINDING: <file:line or file> — <what is wrong, precisely>\n"
    "… one line per problem …\n"
    "STEP n: <file> — <one precise action that fixes it>\n"
    "… only when BLOCKED …\n"
    "VERDICT: PASS\n"
    "or\n"
    "VERDICT: BLOCKED\n"
    "A BLOCKED verdict must have at least one FINDING and at least one STEP; "
    "with nothing concrete to fix, answer PASS instead."
)

SELF_CHECK_RULES = (
    "Each key line is `file:line: message`: read that file once and fix the "
    "cause — a type error means the code disagrees with a real API, so read "
    "the module that owns the type and use its REAL exported API. If the API "
    "you need does not exist, add it in this task's scope instead of casting, "
    "suppressing or disabling the check. A lint rule is a real rule: fix the "
    "code, never disable the rule. "
    "Change only what the report proves is wrong. "
    "Use Repo Create for new files, Repo Edit for existing files."
)


def gate_commands_hint() -> str:
    """The project's gate commands (config-driven; no stack assumptions)."""
    raw = os.getenv("SWARM_GATE_COMMANDS", "").strip()
    commands = [c.strip() for c in re.split(r"[;\n]", raw) if c.strip()] or [
        "pytest -q",
        "ruff check .",
        "mypy app tests",
    ]
    return ", ".join(f"`{command}`" for command in commands)


_AGENT_COPY: dict[str, tuple[str, str]] = {
    "step": (
        "Execute one small step with Repo Edit only. Smallest diff.",
        "You write scaffold files precisely. You run no network commands.",
    ),
    "fix": (
        "Investigate QA's report, then fix the real cause. Smallest coherent diff.",
        (
            "You fix scaffold files precisely. QA has already run the gates and rejected "
            "this attempt; you work from its exit codes and failure output. "
            "You run no network commands and no gates."
        ),
    ),
    "selfcheck": (
        "Fix the type and lint errors the harness found. Smallest coherent diff.",
        (
            "You fix scaffold files precisely. The harness ran the project's static "
            "checks (type checker and linter) before QA and they are red; you work "
            "from their exit codes and error output, not from a report you have to "
            "re-derive. You run no gates and no network commands."
        ),
    ),
    "senior": (
        "Investigate why QA keeps blocking, fix every failure in one pass. No thrash.",
        (
            "You are the senior escalation: the junior coder failed repeatedly and QA kept "
            "returning BLOCKED. QA owns the gates, so its exit codes and failure output are "
            "your evidence. You run no network commands and no gates."
        ),
    ),
    "senior_step": (
        "Execute one small step completely and coherently. No thrash.",
        (
            "You are the senior escalation for a single stuck step: the junior coder "
            "failed it repeatedly. Read the step and the last error, then do it right "
            "in one pass. You run no network commands."
        ),
    ),
    "qa": (
        "Block done unless every configured gate is attached and green.",
        (
            "You are the only role that runs the project gates; the coder never runs them. "
            "You run every configured gate with Guarded Shell, then report each command, "
            "its exit code, and the failure output so the coder can investigate. "
            "Never paste source code or repeat the work summary. "
            "A test that re-declares or stubs the module under test instead of "
            "importing it tests nothing: verdict BLOCKED. "
            "Prefer real type fixes. A fix that removes/disables the feature or "
            "blanket-suppresses types is BLOCKED; a narrow, explained last-resort "
            "suppression may PASS when gates are green and the feature is intact."
        ),
    ),
    "verifier": (
        (
            "Decide whether the implemented scenario does what the brief says, end "
            "to end. Read only: never write a file, never run a gate, never commit."
        ),
        (
            "You verify the scenario, not the gates. The gates test the code that "
            "exists; a missing endpoint, an unmounted route or a duplicate module "
            "produces no failing assertion, so you are the only reader that compares "
            "the implementation with what was asked for. You never write files and "
            "never run gates — QA owns the gates. Your correction plan is advice for "
            "the coder crews, and your final answer is the only artefact you produce."
        ),
    ),
    "plan": (
        "Split one spec task into micro-steps. No code writes.",
        "You plan minimal diffs from specs/ context. You never write files.",
    ),
}

_CODER_KINDS = {"step", "fix", "selfcheck", "senior", "senior_step"}
_SENIOR_KINDS = {"senior", "senior_step"}


_FIXED_ROLES = {
    "qa": "QA Gatekeeper",
    "verifier": "Scenario Verifier",
    "plan": "Spec Planner",
}


def agent_copy(task: SpecTask | None, kind: str) -> dict[str, str]:
    """role/goal/backstory for one crew kind. Role is task-derived for coders."""
    goal, backstory = _AGENT_COPY[kind]
    if kind in _SENIOR_KINDS:
        assert task is not None, f"kind {kind} needs a task"
        role = "Senior Developer"
        backstory = backstory + " " + stack_hint(task)
    elif kind in _CODER_KINDS:
        assert task is not None, f"kind {kind} needs a task"
        role = coder_role(task)
        backstory = backstory + QA_IS_THE_GATEKEEPER + " " + stack_hint(task)
    else:
        role = _FIXED_ROLES[kind]
        if kind == "plan":
            assert task is not None, "kind plan needs a task"
            backstory = backstory + " " + stack_hint(task)
    return {"role": role, "goal": goal, "backstory": backstory}


# ---------------------------------------------------------------------------
# the stable prefix
# ---------------------------------------------------------------------------


def _read_artifacts(spec_dir: str) -> tuple[str, str]:
    if not spec_dir:
        return "", ""
    base = REPO_ROOT / "specs" / spec_dir
    out = []
    for name in ("spec.md", "plan.md"):
        try:
            out.append((base / name).read_text())
        except OSError:
            out.append("")
    return out[0], out[1]


def task_block(
    task: SpecTask, spec_dir: str, *, ac: bool = False, plan: bool = False
) -> str:
    """Spec/task/AC ids and brief; AC paragraphs and plan lines where a crew uses them.

    The verifier reads the whole scenario, so its prefix carries the referenced
    AC paragraphs and the plan lines. A coder crew works from the planner's
    derived steps and already has the brief; repeating every AC paragraph in
    every step would spend tokens on context the coder does not act on (020 is
    an efficiency phase, and the bench shows the cost per case).
    """
    spec_md, plan_md = _read_artifacts(spec_dir)
    acs = ", ".join(task.ac_refs) or "(none)"
    lines = [
        "TASK CONTEXT (stable for every round of this task)",
        f"spec={spec_dir} task={task.id} ac={acs}",
        f"BRIEF: {task.brief}",
    ]
    if ac and task.ac_refs and spec_md:
        from swarm.verify import ac_paragraphs

        paragraphs = ac_paragraphs(spec_md, task.ac_refs)
        kept: list[str] = []
        used = 0
        for paragraph in paragraphs:
            if used + len(paragraph) > MAX_AC_CHARS:
                break
            kept.append(f"- {paragraph}")
            used += len(paragraph)
        if kept:
            lines.append("ACCEPTANCE CRITERIA (what this task must satisfy):")
            lines.extend(kept)
    if plan and plan_md:
        from swarm.verify import plan_lines

        named = brief_paths(task.brief)
        plan_hits = plan_lines(plan_md, task, named)[:MAX_PLAN_LINES]
        if plan_hits:
            lines.append("PLAN LINES (the plan's own words for these files):")
            lines.extend(f"- {line}" for line in plan_hits)
    return "\n".join(lines)


_RULES: dict[str, str] = {
    "step": STEP_RULES,
    "fix": FIX_READ_RULES + " " + FIX_RULES + " Loop rules (hard): at most 12 tool "
    "calls, then write the final answer; never read the same file twice.",
    "selfcheck": SELF_CHECK_RULES + " " + FIX_RULES + " Loop rules (hard): at most 12 tool "
    "calls, then write the final answer; never read the same file twice.",
    "senior": FIX_RULES + " Find the root cause and fix EVERY reported failure in one "
    "pass. Loop rules (hard): at most 14 tool calls, then write the final answer; "
    "never read the same file twice.",
    "senior_step": FIX_RULES + " Loop rules (hard): at most 10 tool calls, then write the result.",
    "qa": QA_RULES.replace(
        "Run EVERY project gate via Guarded Shell.",
        "Run EVERY project gate via Guarded Shell: " + gate_commands_hint() + ".",
    ),
    "verifier": VERIFIER_RULES,
    "plan": PLAN_RULES,
}


def role_rules(kind: str) -> str:
    """Fixed instructions for a crew kind, identical on every round."""
    rules = _RULES[kind]
    if kind == "verifier":
        # Read-only by contract; the scope rule is about writes, which it cannot do.
        return rules
    return rules + " " + SCOPE_RULE


def stable_prefix(task: SpecTask, spec_dir: str = "", kind: str = "step") -> str:
    """The byte-identical head of every prompt of this task for this role.

    Pure: same task, spec directory and kind → same string, whatever step or
    round asks for it. Volatile content is appended by the `*_prompt` functions.
    """
    scenario = kind == "verifier"
    coder = kind in {"step", "fix", "selfcheck", "senior", "senior_step"}
    ac = scenario or (coder and coder_acs_enabled())
    return "\n".join(
        [role_rules(kind), task_block(task, spec_dir, ac=ac, plan=scenario)]
    )


def prompt_prefix(task: SpecTask, spec_dir: str = "", kind: str = "step") -> tuple[str, str]:
    """Provider-order prefix (agent block first) and its short SHA-256.

    The bench records this hash per case, so a change that silently reassembles
    the head of the prompt shows up as a different prefix instead of a mystery.
    """
    agent = agent_copy(task, kind)
    text = "\n".join(
        [
            agent["role"],
            agent["goal"],
            agent["backstory"],
            stable_prefix(task, spec_dir, kind),
        ]
    )
    return text, hashlib.sha256(text.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# volatile tails: always appended after `stable_prefix`
# ---------------------------------------------------------------------------


def step_prompt(task: SpecTask, spec_dir: str, step_text: str, idx: int, total: int) -> str:
    from swarm import tests_first

    frozen = tests_first.frozen_note()
    return (
        stable_prefix(task, spec_dir, "step")
        + f"\n\nExecute micro-step {idx}/{total} (no other work):\n{step_text[:2000]}\n"
        + (f"{frozen}\n" if frozen else "")
        + f"Result: one line per file changed by step {idx}."
    )


def senior_step_prompt(
    task: SpecTask, spec_dir: str, step_text: str, idx: int, total: int, last_error: str
) -> str:
    return (
        stable_prefix(task, spec_dir, "senior_step")
        + f"\n\nSenior rescue for micro-step {idx}/{total} (no other work):\n{step_text[:2000]}\n"
        f"The junior failed with: {last_error[:1000]}\n"
        f"Result: one line per file changed by step {idx}."
    )


def fix_prompt(task: SpecTask, spec_dir: str, report_text: str, qa_review: str = "") -> str:
    block = f"QA's verdict note:\n{qa_review[-1200:]}\n" if qa_review.strip() else ""
    return (
        stable_prefix(task, spec_dir, "fix")
        + "\n\nQA ran the gates and its report is your evidence:\n"
        + f"{report_text}\n"
        + block
        + "Result: diff summary + which reported gate line each change addresses."
    )


def selfcheck_prompt(task: SpecTask, spec_dir: str, report_text: str) -> str:
    return (
        stable_prefix(task, spec_dir, "selfcheck")
        + "\n\nThe harness ran the static checks and this is the evidence:\n"
        + f"{report_text}\n"
        + "Result: diff summary + which reported type/lint line each change addresses."
    )


def senior_prompt(task: SpecTask, spec_dir: str, report_text: str, qa_review: str = "") -> str:
    block = f"QA's latest BLOCKED note:\n{qa_review[-1200:]}\n" if qa_review.strip() else ""
    return (
        stable_prefix(task, spec_dir, "senior")
        + "\n\nQA report:\n"
        + f"{report_text}\n"
        + block
        + "Result: diff summary + which reported gate line each change addresses."
    )


def qa_prompt(task: SpecTask, spec_dir: str, work_summary: str) -> str:
    return (
        stable_prefix(task, spec_dir, "qa")
        + f"\n\nThe coder reports:\n{work_summary[:3000]}\n"
        + "Result: per gate command and exit code, then exactly one verdict line."
    )


def verify_prompt(task: SpecTask, spec_dir: str, context_text: str) -> str:
    return (
        stable_prefix(task, spec_dir, "verifier")
        + "\n\nThe harness built this from the spec and this run's delta:\n\n"
        + f"{context_text}\n"
    )


def test_author_prompt(task: SpecTask, spec_dir: str, ac_text: str = "") -> str:
    """One failing test per acceptance criterion, before the implementation."""
    acs = ac_text or task_block(task, spec_dir, ac=True)
    return (
        "Write the FAILING test(s) for this task before any implementation exists.\n"
        "You are the Test Author: write tests only, never implementation code, and run no gates.\n\n"
        f"{acs}\n\n"
        "Rules (hard):\n"
        "- one focused test per acceptance criterion, importing the REAL module and calling its "
        "real exports; never re-declare or stub the code under test;\n"
        "- the test must fail for the right reason (missing behaviour), not because of a syntax "
        "error in the test;\n"
        "- use the project's existing test layout and framework;\n"
        "- do not touch implementation files, and do not fix the code to make your test pass.\n"
        "Result: the test file paths you wrote, and one line per test naming the criterion it checks."
    )


def plan_prompt(task: SpecTask, spec_dir: str) -> str:
    return (
        stable_prefix(task, spec_dir, "plan")
        + "\n\nResult: the STEP lines only."
    )


# ---------------------------------------------------------------------------
# parsing helpers kept next to the text they describe
# ---------------------------------------------------------------------------

STEP_RE = re.compile(r"^STEP\s*(\d+)\s*[:.\-–]\s*(.+)$", re.MULTILINE)


def parse_steps(plan_text: str) -> list[str]:
    """Split a planner STEP list into executable micro-steps. Never truncates."""
    return [m.group(2).strip() for m in STEP_RE.finditer(plan_text) if m.group(2).strip()]


def steps_usable(steps: list[str]) -> bool:
    """A plan is usable only when it fits the micro-step budget and each step is sane."""
    return 1 <= len(steps) <= MAX_STEPS and all(3 <= len(s) <= 500 for s in steps)


def step_count(plan_text: str) -> int:
    """Convenience for the bench: how many steps a plan renders."""
    return len(parse_steps(plan_text))


__all__ = [
    "FIX_RULES",
    "MAX_STEPS",
    "QA_RULES",
    "SCOPE_RULE",
    "STEP_RE",
    "agent_copy",
    "brief_paths",
    "coder_role",
    "fix_prompt",
    "gate_commands_hint",
    "parse_steps",
    "plan_prompt",
    "prompt_prefix",
    "qa_prompt",
    "role_rules",
    "selfcheck_prompt",
    "senior_prompt",
    "senior_step_prompt",
    "stable_prefix",
    "stack_hint",
    "step_prompt",
    "steps_usable",
    "task_block",
    "verify_prompt",
]


def _unused(value: Any) -> None:  # pragma: no cover - keeps typing import meaningful
    del value
