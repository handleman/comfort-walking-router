"""Parallel task attempts with serialized integration (023 phase 1).

One task at a time is the queue's throughput ceiling. The phases *inside* a task
are dependent, but independent tasks are not: they can be attempted in isolated
worktrees and the first green delta integrated into the main tree.

This module is deliberately conservative:

- a worker runs `swarm.flow --no-commit` in a throwaway worktree with the
  current harness copy, so the main tree is never written by a worker;
- only a **green** worker is integrated, and only one integration runs at a
  time (the main-tree lock);
- the coordinator re-runs the project gates on the main tree before committing,
  so the merge evidence is the same as a serial run's;
- a patch that does not apply or fails a gate is rolled back and the task is
  re-queued (`conflict`/`gates_failed`), never half-merged;
- tasks whose briefs name overlapping files are not run together.

This is a race, not a scheduler: the first green wins, the rest are re-queued.
That is enough to double throughput on independent work without a durable
orchestrator (ADR-012 keeps that as a future option).
"""

from __future__ import annotations

import json
import queue
import shlex
import subprocess
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from swarm import prompts
from swarm.bench import live

REPO_ROOT = Path(__file__).resolve().parent.parent
INTEGRATION_SCOPE = ("app/", "frontend/", "tests/", "contracts/", "requirements", "pyproject.toml", ".gitignore")


@dataclass
class WorkerResult:
    spec: str
    task: str
    ok: bool = False
    status: str = "failed"
    worktree: str = ""
    run_dir: str = ""
    changed: list[str] = field(default_factory=list)
    diff: str = ""
    error: str = ""


def _scope_files(changed: list[str]) -> list[str]:
    return [
        path
        for path in changed
        if any(path.startswith(prefix) or path == prefix for prefix in INTEGRATION_SCOPE)
    ]


def _brief_paths(repo: Path, spec: str, task: str) -> set[str]:
    from swarm.spec_loader import load_spec_tasks, spec_dir_name

    spec_dir = spec_dir_name(repo, spec)
    try:
        _, tasks = load_spec_tasks(repo, spec_dir, task)
    except OSError:
        return set()
    return set(prompts.brief_paths(tasks[0].brief)) if tasks else set()


def independent(repo: Path, pairs: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    """Group tasks whose briefs name disjoint files (a conservative batch plan)."""
    batches: list[list[tuple[str, str]]] = []
    taken: dict[str, set[str]] = {}
    for spec, task in pairs:
        paths = _brief_paths(repo, spec, task)
        for batch in batches:
            if all(not (paths & taken[f"{s}/{t}"]) for s, t in batch):
                batch.append((spec, task))
                taken[f"{spec}/{task}"] = paths
                break
        else:
            batches.append([(spec, task)])
            taken[f"{spec}/{task}"] = paths
    return batches


def _git(repo: Path, *args: str, stdin: str | None = None) -> tuple[int, str]:
    p = subprocess.run(
        ["git", *args], cwd=repo, check=False, capture_output=True, text=True,
        input=stdin, timeout=120,
    )
    return p.returncode, (p.stdout if p.returncode == 0 else p.stderr)


def run_worker(
    spec: str,
    task: str,
    *,
    repo: Path = REPO_ROOT,
    timeout: int | None = None,
) -> WorkerResult:
    """Run one task in a throwaway worktree; never write the main tree."""
    result = WorkerResult(spec=spec, task=task)
    worktree = Path(tempfile.mkdtemp(prefix=f"swarm-par-{spec}-{task}-"))
    added = False
    try:
        rc, base = _git(repo, "rev-parse", "HEAD")
        if rc != 0:
            result.error = "not a git repository"
            return result
        rc, out = _git(repo, "worktree", "add", "--detach", str(worktree), base.strip())
        if rc != 0:
            result.error = f"worktree add failed: {out.strip()[:200]}"
            return result
        added = True
        live.copy_harness(repo, worktree)
        live.link_venvs(repo, worktree)
        env = dict(__import__("os").environ)
        live.fill_from_dotenv(repo, env)
        env["SWARM_STASH_UNRELATED"] = "0"
        env["PYTHONPATH"] = str(worktree)
        env["PATH"] = f"{repo / '.venv' / 'bin'}:{repo / 'swarm' / '.venv' / 'bin'}:{env.get('PATH', '')}"
        python = repo / "swarm" / ".venv" / "bin" / "python"
        proc = subprocess.run(
            [str(python), "-m", "swarm.flow", "--spec", spec, "--task", task,
             "--no-commit", "--no-tui"],
            cwd=worktree, env=env, check=False, capture_output=True, text=True,
            timeout=timeout or live.timeout_seconds(),
        )
        run_dir = live._run_dir(worktree)
        payload: dict[str, Any] = {}
        if run_dir is not None:
            try:
                payload = json.loads((run_dir / "run.json").read_text())
            except (OSError, json.JSONDecodeError):
                payload = {}
        result.status = str(payload.get("status") or "failed")
        result.ok = result.status == "green"
        result.run_dir = str(run_dir or "")
        result.changed = _scope_files([str(p) for p in (payload.get("changed_files") or [])])
        if result.changed:
            rc, diff = _git(worktree, "diff", "--binary", base.strip(), "--", *result.changed)
            result.diff = diff if rc == 0 else ""
        if not result.ok:
            result.error = str(payload.get("reason_code") or proc.stderr or "")[:300]
        return result
    except subprocess.TimeoutExpired:
        result.status = "timeout"
        result.error = "worker timed out"
        return result
    finally:
        if added and result.ok:
            _git(repo, "worktree", "remove", "--force", str(worktree))
            __import__("shutil").rmtree(worktree, ignore_errors=True)


def _run_gates(repo: Path, commands: list[str]) -> dict[str, int]:
    codes: dict[str, int] = {}
    for command in commands:
        try:
            argv = shlex.split(command)
        except ValueError:
            codes[command] = 99
            continue
        proc = subprocess.run(argv, cwd=repo, check=False, capture_output=True, text=True, timeout=900)
        codes[command] = proc.returncode
    return codes


def integrate(
    result: WorkerResult,
    *,
    repo: Path = REPO_ROOT,
    commands: list[str] | None = None,
    push: bool = True,
) -> dict[str, Any]:
    """Apply a green worker's delta to main, re-gate it, and commit it."""
    from swarm import done
    from swarm.spec_loader import load_spec_tasks, spec_dir_name

    if not result.ok or not result.diff:
        return {"status": "skipped", "task": f"{result.spec}/{result.task}"}
    rc, out = _git(repo, "apply", "--check", "--binary", "-", stdin=result.diff)
    if rc != 0:
        return {"status": "conflict", "task": f"{result.spec}/{result.task}", "detail": out[:200]}
    rc, out = _git(repo, "apply", "--binary", "-", stdin=result.diff)
    if rc != 0:
        return {"status": "conflict", "task": f"{result.spec}/{result.task}", "detail": out[:200]}

    if commands is None:
        from swarm.flow import gate_commands

        commands = gate_commands()
    codes = _run_gates(repo, commands)
    failed = {command: code for command, code in codes.items() if code != 0}
    if failed:
        _git(repo, "apply", "-R", "--binary", "-", stdin=result.diff)
        return {"status": "gates_failed", "task": f"{result.spec}/{result.task}", "gates": failed}

    spec_dir = spec_dir_name(repo, result.spec)
    try:
        spec_path, tasks = load_spec_tasks(repo, spec_dir, result.task)
        spec_task = tasks[0]
    except (OSError, IndexError):
        _git(repo, "apply", "-R", "--binary", "-", stdin=result.diff)
        return {"status": "unknown_task", "task": f"{result.spec}/{result.task}"}
    _git(repo, "add", "-A")
    message = (
        f"{spec_dir}/{result.task}: {spec_task.brief}\n\n"
        f"Swarm-Task: {spec_dir}/{result.task}\n"
        f"Swarm-Task-Hash: {done.task_hash(spec_task)}\n"
        f"Swarm-Spec-Hash: {done.spec_plan_hash(spec_path)}\n"
        f"Swarm-Parallel: {Path(result.run_dir).name or 'parallel'}\n"
    )
    rc, out = _git(repo, "commit", "-m", message)
    if rc != 0:
        return {"status": "commit_failed", "task": f"{result.spec}/{result.task}", "detail": out[:200]}
    rc, sha = _git(repo, "rev-parse", "HEAD")
    if push:
        _git(repo, "push", "origin", "HEAD")  # best effort: the harness push path has a fallback
    return {"status": "integrated", "task": f"{result.spec}/{result.task}", "commit": sha.strip()}


def run_batch(
    pairs: list[tuple[str, str]],
    *,
    repo: Path = REPO_ROOT,
    workers: int = 2,
    runner: Callable[..., WorkerResult] | None = None,
    integrator: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Race independent tasks in parallel; integrate greens serially."""
    runner = runner or (lambda spec, task, **kw: run_worker(spec, task, **kw))
    integrator = integrator or (lambda result, **kw: integrate(result, **kw))
    results: queue.Queue[WorkerResult] = queue.Queue()
    groups = independent(repo, pairs)
    # A group is mutually independent by construction; take up to `workers`
    # from the first group (tasks from different groups may share files).
    chosen = (groups[0][:workers] if groups else pairs[:workers])

    def work(spec: str, task: str) -> None:
        results.put(runner(spec, task, repo=repo))

    threads = [threading.Thread(target=work, args=pair, daemon=True) for pair in chosen]
    for thread in threads:
        thread.start()
    rows: list[dict[str, Any]] = []
    for _ in chosen:
        result = results.get()
        row = {"spec": result.spec, "task": result.task, "status": result.status}
        if result.ok:
            row.update(integrator(result, repo=repo))
        rows.append(row)
    for thread in threads:
        thread.join()
    return {
        "workers": workers,
        "tasks": [f"{s}/{t}" for s, t in chosen],
        "rows": rows,
        "integrated": sum(1 for row in rows if row.get("status") == "integrated"),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="swarm.parallel", description="parallel task attempts")
    parser.add_argument("--batch", required=True, help="comma separated spec:task pairs")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--repo", default=str(REPO_ROOT))
    args = parser.parse_args(argv)
    pairs = [
        (part.split(":", 1)[0].strip(), part.split(":", 1)[1].strip())
        for part in args.batch.split(",")
        if ":" in part
    ]
    if not pairs:
        print("no tasks in --batch")
        return 2
    out = run_batch(pairs, repo=Path(args.repo), workers=max(1, args.workers))
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if out.get("integrated") else 1


if __name__ == "__main__":
    raise SystemExit(main())
