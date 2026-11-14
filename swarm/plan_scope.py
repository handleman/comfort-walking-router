"""Keep a plan inside its task (024/021 follow-up).

`004-weather-sun-T2` is "auto-rule in `app/preferences.py`". Its planner produced
six steps that also edited `app/main.py` and `contracts/route.json` — files the
*next* task's brief owns — and the verifier then blocked on defects in that extra
scope. The coder did nothing wrong; the plan had another task in it.

This guard is deterministic: a step whose target is named in **another** task's
brief, and not in this task's, is trimmed. If every step is foreign the plan is
left intact (the brief probably names no files; a trim would empty the task).
"""

from __future__ import annotations

from pathlib import Path

from swarm import prompts


def step_target(step: str) -> str | None:
    paths = prompts.brief_paths(step)
    return paths[0] if paths else None


def task_files(repo: Path, spec_dir: str) -> dict[str, set[str]]:
    """`task id → files its brief names`, from the spec's `tasks.md`."""
    from swarm.spec_loader import parse_tasks_md

    try:
        text = (repo / "specs" / spec_dir / "tasks.md").read_text()
    except OSError:
        return {}
    return {task.id: set(prompts.brief_paths(task.brief)) for task in parse_tasks_md(text)}


def scope_steps(
    repo: Path, spec_dir: str, task_id: str, steps: list[str], brief: str = ""
) -> tuple[list[str], list[str]]:
    """Drop steps that target a file another task owns; return (steps, trimmed).

    If the plan is **entirely** another task's work (the plan cache can hand a
    task its neighbour's plan), replace it with one step on the task's own files
    instead of running the wrong scope. A brief that names no files is left
    alone: there is no safe synthetic step.
    """
    owned = task_files(repo, spec_dir)
    mine = owned.get(task_id, set())
    foreign: set[str] = set()
    for other, paths in owned.items():
        if other != task_id:
            foreign |= paths
    foreign -= mine
    if not foreign:
        return steps, []

    kept: list[str] = []
    trimmed: list[str] = []
    for step in steps:
        target = step_target(step)
        if target and target in foreign:
            trimmed.append(step)
        else:
            kept.append(step)
    if not kept:
        if not mine:
            return steps, []  # the brief names no files: nothing to scope against
        own = ", ".join(sorted(mine))
        return [f"{own} — {brief or 'implement the brief'}"[:500]], trimmed
    return kept, trimmed
