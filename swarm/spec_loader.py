"""Parse specs/<id>/{spec,plan,tasks}.md into task objects (009 T3, AC-3). No LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

TASK_RE = re.compile(r"^- \[ \] (T\d+)\s*(\([^)]*\))?\s*:\s*(.+)$", re.MULTILINE)
AC_RE = re.compile(r"AC-\d+")


@dataclass(frozen=True)
class SpecTask:
    id: str
    ac_refs: tuple[str, ...]
    brief: str


def parse_tasks_md(text: str) -> list[SpecTask]:
    out: list[SpecTask] = []
    for m in TASK_RE.finditer(text):
        tid, paren, brief = m.group(1), m.group(2) or "", m.group(3).strip()
        out.append(SpecTask(id=tid, ac_refs=tuple(AC_RE.findall(paren)), brief=brief))
    return out


def spec_dir_name(repo_root: Path, spec: str) -> str:
    """Canonical spec directory name; a unique prefix (`007`) → `007-live-position`.

    Queue keys must not depend on how the run was invoked: `run.sh 007 T9`
    records `spec: "007"` in run.json, but the flow and the parked-task list use
    the directory name. Normalising once keeps `retry_later` honest.
    """
    specs = repo_root / "specs"
    try:
        if (specs / spec).is_dir():
            return spec
        matches = sorted(p.name for p in specs.iterdir() if p.is_dir() and p.name.startswith(spec))
    except OSError:
        return spec
    return matches[0] if len(matches) == 1 else spec


def task_key(repo_root: Path, spec: str, task: str) -> str:
    """Queue key `spec_dir/task`, the same whatever form the caller passes."""
    return f"{spec_dir_name(repo_root, spec)}/{task}"


def load_spec_tasks(repo_root: Path, spec_dir: str, task_filter: str | None = None) -> tuple[Path, list[SpecTask]]:
    specs = repo_root / "specs"
    spec_path = specs / spec_dir
    if not spec_path.is_dir():
        matches = sorted(p for p in specs.iterdir() if p.is_dir() and p.name.startswith(spec_dir))
        if len(matches) == 1:
            spec_path = matches[0]
    tasks = parse_tasks_md((spec_path / "tasks.md").read_text())
    if task_filter:
        tasks = [t for t in tasks if t.id == task_filter]
    return spec_path, tasks
