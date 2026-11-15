"""The inner repair roster (027 T2, AC-2).

A repair is a planned change, not a free-form edit: for every failure the phase
writes a small SDD trio **inside the run dir** —

    <run>/inner/spec.md    problem, one AC per failure, acceptance
    <run>/inner/plan.md    the approach per class (drift vs coverage)
    <run>/inner/tasks.md   `- [ ] T<n> (AC-…): brief` lines, the queue's own format

`specs/` stays untouched (the swarm never edits the spec roster; that is how a
run could grade its own homework). The tasks parse with the real
`spec_loader.parse_tasks_md`, so the roster is the same shape the planner and
coder crews already understand, and the scope is decided by class: a `drift`
repair may only touch `frontend/e2e/**` (and its fixtures), a `coverage` repair
writes a new spec there, and an `impl` failure is *not* a roster task — it goes
back to the normal code fix loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from swarm.e2e_triage import FailedTest
from swarm.spec_loader import SpecTask, parse_tasks_md

INNER_DIR = "inner"
E2E_SCOPE = ("frontend/e2e/",)
MAX_TASKS = 3
SPEC_TEXT = """# Inner roster — e2e repair ({spec_id}/{task_id})

Generated from a red Playwright run. This is a *repair* roster, not new product
scope: it exists so the failing scenario passes for the reason the test states.

## Problem

The recorded suite failed for {count} test(s) in class `{cls}`:

{problems}

## Acceptance

- every test above passes in a full recorded suite run at the final delta;
- no test title is deleted, no `skip`/`fixme`/`only` is added, and the assertion
  count does not shrink (the harness checks this itself, not the model);
- the scenario verifier still sees the brief implemented in the code, not just
  in the test.

## Out of scope

Product behaviour that the spec asserts is *not* repaired here: a failing
assertion on a visible element goes back to the code fix loop (`impl`).
"""

PLAN_TEXT = """# Inner plan — e2e repair ({spec_id}/{task_id})

The class decides the approach; nothing else may change.

- `drift` — the page moved, the intent did not: update the locator/fixture in
  the spec so it addresses the element the user actually sees today. Keep the
  assertion and its intent; do not relax it.
- `coverage` — the brief names a scenario with no spec: write the spec from the
  AC in the brief, asserting what the user does and sees.

For every task: read the failing test, reproduce it in the recorded output, make
the smallest edit that satisfies the same assertion, then stop.
"""


@dataclass(frozen=True)
class Roster:
    directory: Path
    tasks: list[SpecTask]
    cls: str

    def as_dict(self) -> dict[str, object]:
        return {
            "dir": str(self.directory),
            "class": self.cls,
            "tasks": [{"id": t.id, "brief": t.brief, "acs": list(t.ac_refs)} for t in self.tasks],
        }


def scope_for(cls: str, outer_scope: tuple[str, ...]) -> tuple[str, ...]:
    """Allowed paths for one class: repairs stay in the e2e tree (AC-4)."""
    if cls in ("drift", "coverage"):
        return E2E_SCOPE
    return outer_scope


def _task_brief(index: int, fail: FailedTest) -> str:
    where = f"{fail.file}:{fail.line}"
    if fail.cls == "coverage":
        return (
            f"Write the missing e2e scenario in `frontend/e2e/{fail.file.removeprefix('e2e/')}` "
            f"(test {index}: {fail.title or 'the scenario the brief names'}): assert what the "
            "user does and sees, following the suite's existing helpers. Change no product code."
        )
    return (
        f"Repair the stale locator/fixture in `frontend/e2e/{fail.file.removeprefix('e2e/')}` at "
        f"{where} (test: {fail.title or 'unnamed'}): the element exists but the spec addresses "
        "it wrongly. Keep the assertion and its intent — do not delete, skip or weaken a check, "
        "and change no product code."
    )


def write_roster(
    run_dir: Path,
    *,
    spec_id: str,
    task_id: str,
    failed: list[FailedTest],
    acs: tuple[str, ...] = (),
    max_tasks: int = MAX_TASKS,
) -> Roster:
    """Write spec/plan/tasks for the failures; refuse more than `max_tasks`."""
    cls = failed[0].cls if failed else "unclassified"
    chosen = failed[:max_tasks]
    directory = Path(run_dir) / INNER_DIR
    directory.mkdir(parents=True, exist_ok=True)
    problems = "\n".join(
        f"- `{f.file}:{f.line}` › {f.title or '<no title>'} [{f.cls}]: {'; '.join(f.reasons)}"
        for f in chosen
    )
    ac_paren = f" (AC-{acs[0].removeprefix('AC-')})" if acs else ""
    lines = []
    for index, fail in enumerate(chosen, 1):
        lines.append(f"- [ ] T{index}{ac_paren}: {_task_brief(index, fail)}")
    tasks_md = "\n".join(lines) + "\n"
    (directory / "spec.md").write_text(
        SPEC_TEXT.format(
            spec_id=spec_id, task_id=task_id, count=len(chosen), cls=cls, problems=problems
        )
    )
    (directory / "plan.md").write_text(PLAN_TEXT.format(spec_id=spec_id, task_id=task_id))
    (directory / "tasks.md").write_text(tasks_md)
    tasks = parse_tasks_md(tasks_md)
    return Roster(directory=directory, tasks=tasks, cls=cls)


def load_roster(run_dir: Path) -> list[SpecTask]:
    """Parse the roster back with the queue's own parser (round-trip check)."""
    path = Path(run_dir) / INNER_DIR / "tasks.md"
    try:
        return parse_tasks_md(path.read_text())
    except OSError:
        return []
