"""Record a manually completed task in the done ledger (026 AC-10).

The swarm's own green path writes the trailers as part of its commit. Work that
was done by hand — the six product tasks finished outside the queue, or a task
the harness parked — leaves the `- [ ]` line open with no trailer, so the queue
re-runs it and nothing says why. `make swarm-record SPEC=014 TASK=T11` writes
an **empty** commit carrying exactly the standard trailers:

    swarm: 014-…-T11 recorded manually

    Swarm-Task: 014-…/T11
    Swarm-Task-Hash: <sha256 of id+brief+ACs>
    Swarm-Spec-Hash: <sha256 of spec.md+plan.md>
    Swarm-Run: manual-<timestamp>

It never touches the working tree and never edits `specs/` (the done ledger is
the source of truth; `tasks.md` stays yours to tick).

Usage:
    swarm/.venv/bin/python -m swarm.record 014 T11 [--no-commit] [--dry-run]
"""

from __future__ import annotations

import datetime
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> tuple[int, str]:
    p = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    return p.returncode, (p.stdout + p.stderr).strip()


def message(spec_id: str, task_id: str, task_hash: str, spec_hash: str, stamp: str) -> str:
    """The commit message the green path writes, marked as a manual record."""
    return (
        f"swarm: {spec_id}-{task_id} recorded manually\n\n"
        f"Swarm-Task: {spec_id}/{task_id}\n"
        f"Swarm-Task-Hash: {task_hash}\n"
        f"Swarm-Spec-Hash: {spec_hash}\n"
        f"Swarm-Run: manual-{stamp}\n"
    )


def record(
    spec: str,
    task_id: str,
    *,
    commit: bool = True,
    dry_run: bool = False,
) -> int:
    from swarm.done import record_done, spec_plan_hash, task_hash
    from swarm.spec_loader import load_spec_tasks, spec_dir_name, task_key

    # include_done: a manual completion is usually ticked in tasks.md already.
    spec_path, tasks = load_spec_tasks(REPO_ROOT, spec, None, include_done=True)
    wanted = task_id if task_id.upper().startswith("T") else f"T{task_id}"
    task = next((t for t in tasks if str(t.id).upper() == wanted.upper()), None)
    if task is None:
        known = ", ".join(str(t.id) for t in tasks)
        print(f"swarm-record: no task {wanted} in {spec_path.name} (have: {known})")
        return 2

    spec_id = spec_dir_name(REPO_ROOT, spec)
    hash_value = task_hash(task)
    spec_hash_value = spec_plan_hash(spec_path)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    key = task_key(REPO_ROOT, spec, str(task.id))
    body = message(spec_id, str(task.id), hash_value, spec_hash_value, stamp)

    print(f"record {key}")
    print(f"  task hash {hash_value[:16]}…  spec hash {spec_hash_value[:16]}…")
    if dry_run:
        print("--- would commit ---")
        print(body)
        return 0

    record_done(
        REPO_ROOT,
        spec_id,
        str(task.id),
        task_hash_value=hash_value,
        spec_hash_value=spec_hash_value,
        run_id=f"manual-{stamp}",
    )
    print("  ledger cache updated (swarm/runs/done.json)")
    if not commit:
        print("  no commit (--no-commit)")
        return 0

    rc, out = _git("commit", "--allow-empty", "-m", body)
    if rc != 0:
        print(f"swarm-record: commit failed: {out}")
        return 1
    sha_rc, sha = _git("rev-parse", "--short", "HEAD")
    print(f"  committed {sha if sha_rc == 0 else '?'} (empty commit, trailers only)")
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="Write the standard green trailers for a manually completed task."
    )
    ap.add_argument("spec", help="spec directory or unique prefix (e.g. 014)")
    ap.add_argument("task", help="task id (e.g. T11, or 11)")
    ap.add_argument("--no-commit", action="store_true", help="update the cache only")
    ap.add_argument("--dry-run", action="store_true", help="print the message, change nothing")
    args = ap.parse_args(argv)
    return record(args.spec, args.task, commit=not args.no_commit, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
