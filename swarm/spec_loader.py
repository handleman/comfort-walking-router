"""Parse `specs/<kind>/<id>/{spec,plan,tasks}.md` into task objects (009 T3, AC-3). No LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

TASK_RE = re.compile(r"^- \[ \] (T\d+)\s*(\([^)]*\))?\s*:\s*(.+)$", re.MULTILINE)
# `- [x]` lines are done work, not queue entries; `swarm.record` still needs
# them (a manual completion is normally ticked by hand).
ANY_TASK_RE = re.compile(r"^- \[[ xX]\] (T\d+)\s*(\([^)]*\))?\s*:\s*(.+)$", re.MULTILINE)
AC_RE = re.compile(r"AC-\d+")


@dataclass(frozen=True)
class SpecTask:
    id: str
    ac_refs: tuple[str, ...]
    brief: str


def parse_tasks_md(text: str, *, include_done: bool = False) -> list[SpecTask]:
    """Open `- [ ]` tasks; with `include_done` also the ticked `- [x]` ones.

    The brief text is identical either way, so `done.task_hash` computed from a
    ticked line still matches what the queue would compute.
    """
    out: list[SpecTask] = []
    for m in (ANY_TASK_RE if include_done else TASK_RE).finditer(text):
        tid, paren, brief = m.group(1), m.group(2) or "", m.group(3).strip()
        out.append(SpecTask(id=tid, ac_refs=tuple(AC_RE.findall(paren)), brief=brief))
    return out


KINDS = ("product", "harness")
# 032 used `control-plane` as the marker value; 034 renamed it to `harness` (the
# folder name). A legacy flat `kind` file may still say `control-plane`.
_KIND_ALIASES = {"product": "product", "harness": "harness", "control-plane": "harness"}


def iter_spec_dirs(repo_root: Path) -> list[Path]:
    """Every spec directory: `specs/product/*`, `specs/harness/*`, and any legacy
    flat `specs/<name>/` (the pre-034 layout, still used by the unit tests)."""
    specs = Path(repo_root) / "specs"
    out: list[Path] = []
    for kind in KINDS:
        base = specs / kind
        if base.is_dir():
            out.extend(sorted(p for p in base.iterdir() if p.is_dir()))
    if specs.is_dir():
        out.extend(sorted(p for p in specs.iterdir() if p.is_dir() and p.name not in KINDS))
    return out


def resolve_spec_dir(repo_root: Path, spec: str) -> Path | None:
    """Canonical spec directory for a name or a unique numeric prefix.

    `spec` is always a leaf name (`007-live-position`) or a prefix (`007`), so
    the search is over the two kind folders and any legacy flat dirs.
    """
    exact = [p for p in iter_spec_dirs(repo_root) if p.name == spec]
    if len(exact) == 1:
        return exact[0]
    prefix = [p for p in iter_spec_dirs(repo_root) if p.name.startswith(spec)]
    return prefix[0] if len(prefix) == 1 else None


def spec_dir_name(repo_root: Path, spec: str) -> str:
    """Canonical spec directory name; a unique prefix (`007`) → `007-live-position`.

    Queue keys must not depend on how the run was invoked: `run.sh 007 T9`
    records `spec: "007"` in run.json, but the flow and the parked-task list use
    the directory name. Normalising once keeps `retry_later` honest.
    """
    path = resolve_spec_dir(repo_root, spec)
    return path.name if path is not None else spec


def spec_kind(repo_root: Path, spec: str) -> str:
    """`product` | `harness` (034). The folder is authoritative; a `kind` file is
    the backstop for a legacy flat dir (032's marker, which predates the split).

    A spec that does not say it is harness is a product spec: the queue must
    never digest the harness, but defaulting the unknown to harness would
    silently stop running real work.
    """
    path = resolve_spec_dir(repo_root, spec)
    if path is None:
        return "product"
    if path.parent.name in KINDS:
        return path.parent.name
    try:
        text = (path / "kind").read_text().strip()
    except OSError:
        return "product"
    return _KIND_ALIASES.get(text, "product")


def task_key(repo_root: Path, spec: str, task: str) -> str:
    """Queue key `spec_dir/task`, the same whatever form the caller passes."""
    return f"{spec_dir_name(repo_root, spec)}/{task}"


def load_spec_tasks(
    repo_root: Path,
    spec_dir: str,
    task_filter: str | None = None,
    *,
    include_done: bool = False,
) -> tuple[Path, list[SpecTask]]:
    spec_path = resolve_spec_dir(repo_root, spec_dir)
    if spec_path is None:
        raise FileNotFoundError(spec_dir)
    tasks = parse_tasks_md((spec_path / "tasks.md").read_text(), include_done=include_done)
    if task_filter:
        tasks = [t for t in tasks if t.id == task_filter]
    return spec_path, tasks
