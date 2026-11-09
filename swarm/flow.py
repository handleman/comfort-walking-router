"""SwarmFlow: load spec → run crew → gate → commit → save run.json (009 T6, 012 Phase 0)."""

from __future__ import annotations

import argparse
import atexit
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent
with contextlib.suppress(Exception):
    # budgets/merge flags must be visible before SwarmFlow.__init__ reads them
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")

TERMINAL_STATUSES = (
    "crew_error",
    "quota_exhausted",
    "budget_exhausted",
    "interrupted",
    "preflight_failed",
    "merge_failed",
)


class SwarmState(BaseModel):
    spec_dir: str = ""
    task_id: str = ""
    status: str = "init"
    result: str = ""
    gates: dict[str, int] = {}
    fix_rounds: int = 0
    dev_attempts: int = 0
    senior_used: bool = False
    senior_rounds: int = 0
    transcript: str = ""
    plan_reused: bool = False
    quota_note: str = ""
    budget_note: str = ""
    review_verdict: str = ""
    changed_files: list[str] = []
    approval_required: bool = False
    approved: bool = False
    # Usage/evidence (012 T11): filled from CrewOutput.token_usage.
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_prompt_tokens: int = 0
    total_tokens: int = 0
    llm_calls: int = 0
    models_used: list[str] = []
    started_at: str = ""
    finished_at: str = ""
    resumed_from_step: int = 0
    recovery: str = ""
    recovery_note: str = ""
    review_text: str = ""


class _QuotaExhausted(SystemExit):
    """Daily free-model quota hit: stop the pilot, do not retry or escalate."""


class _BudgetExhausted(Exception):
    """Per-run token/cost/time budget hit (012 T14)."""


def _is_quota_error(e: BaseException) -> bool:
    from swarm.retry import is_quota_error

    return is_quota_error(e)


def _runs_dir() -> Path:
    return Path(REPO_ROOT) / "swarm" / "runs"


def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def plan_cache_path(spec_dir: str, task_id: str) -> Path:
    d = _runs_dir() / "plans"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{_safe_key(f'{spec_dir}-{task_id}')}.md"


def _spec_path(spec_dir: str) -> Path:
    from swarm.spec_loader import load_spec_tasks

    path, _ = load_spec_tasks(REPO_ROOT, spec_dir, None)
    return path


def plan_source_hash(spec_dir: str) -> str:
    """Hash spec/plan/tasks content so a stale cached plan can never run."""
    d = _spec_path(spec_dir)
    h = hashlib.sha256()
    for name in ("spec.md", "plan.md", "tasks.md"):
        h.update(name.encode())
        h.update(b"\0")
        p = d / name
        h.update(p.read_bytes() if p.is_file() else b"")
        h.update(b"\0")
    return h.hexdigest()


PLAN_HEADER_RE = re.compile(r"^<!-- plan-source: ([0-9a-f]{64}) -->\n?")


def read_cached_plan(path: Path, source_hash: str) -> str:
    """Return cached plan text only when its source hash still matches."""
    try:
        text = path.read_text()
    except OSError:
        return ""
    m = PLAN_HEADER_RE.match(text)
    if not m or m.group(1) != source_hash:
        return ""
    return text[m.end() :]


def write_cached_plan(path: Path, plan_text: str, source_hash: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"<!-- plan-source: {source_hash} -->\n{plan_text[:8000]}")


def _resolve_steps(plan_text: str) -> list[str]:
    """Planner output → executable micro-steps; [] when unparseable/over-budget.

    Never fall back to running raw planner text as a step: unparseable plans
    must fail loudly (001-T3 false-green, 2026-10-11), not execute garbage.
    """
    from swarm.crew import parse_steps, steps_usable

    steps = parse_steps(plan_text)
    return steps if steps_usable(steps) else []


def _resolve_scope() -> tuple[str, ...]:
    from swarm.tools_guarded import resolve_scope

    return resolve_scope()


_VERDICT_RE = re.compile(r"\b(PASS|BLOCKED)\b", re.IGNORECASE)


def reviewer_verdict(text: str) -> str:
    """Last PASS/BLOCKED word in reviewer output; 'unknown' when absent."""
    hits = _VERDICT_RE.findall(text or "")
    return hits[-1].lower() if hits else "unknown"


def _git(args: list[str], timeout: int = 120) -> tuple[int, str]:
    """Run git argv (no shell), returning (rc, tail-of-output)."""
    p = subprocess.run(
        ["git", *args],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return p.returncode, (p.stdout + p.stderr)[-500:]


def _branch_name(spec_id: str, task_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{spec_id}-{task_id}").strip("-")
    return f"swarm/{slug or 'task'}"


def _unique_branch(name: str) -> str:
    """Avoid reusing a branch left by an earlier attempt."""
    rc, _ = _git(["rev-parse", "--verify", "--quiet", f"refs/heads/{name}"])
    if rc != 0:
        return name
    return f"{name}-{dt.datetime.now().strftime('%H%M%S')}"


def _commit_changes(
    spec_id: str,
    task_id: str,
    brief: str,
    paths: list[str] | None = None,
    scope: tuple[str, ...] | None = None,
    *,
    task_hash_value: str = "",
    spec_hash_value: str = "",
    run_id: str = "",
    allow_empty: bool = False,
) -> dict[str, str]:
    """Commit + push only the run-delta paths that are in scope.

    Default mode is branch-per-task + merge queue (012 T18):
    commit on `swarm/<spec>-<task>`, push it, `--no-ff` merge into the base
    branch, push the base, and roll the merge back if that final push fails.
    `SWARM_MERGE_MODE=direct` restores the old commit-straight-to-base behavior.

    013: when hashes are supplied, the commit body carries the done-ledger
    trailers (`Swarm-Task`, `Swarm-Task-Hash`, `Swarm-Spec-Hash`, `Swarm-Run`).

    Returns ``{commit, push, ok, branch, base, merge, rollback}``;
    ``ok == "0"`` means the run must not be green.
    """
    from swarm.tools_guarded import _git_changed, is_secret_path, scope_violations

    rec: dict[str, str] = {"commit": "", "push": "", "merge": "", "rollback": "", "ok": "0"}
    scope = scope or _resolve_scope()
    changed = list(paths) if paths is not None else _git_changed()
    secret = [p for p in changed if is_secret_path(p)]
    if secret:
        rec["commit"] = f"refused: .env-looking path in run delta: {secret}"
        return rec
    in_scope = [p for p in changed if p not in scope_violations([p], scope)]
    if not in_scope and not allow_empty:
        rec["commit"] = "clean (nothing in scope changed)"
        rec["ok"] = "1"
        return rec

    def _sh(args: list[str]) -> tuple[int, str]:
        p = subprocess.run(args, check=False, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
        return p.returncode, (p.stdout + p.stderr)[-500:]

    subject = f"swarm: {spec_id}-{task_id} green — {brief[:80]} (autocommit)"
    trailers = ""
    if task_hash_value:
        trailers = f"\n\nSwarm-Task: {spec_id}/{task_id}\nSwarm-Task-Hash: {task_hash_value}"
        if spec_hash_value:
            trailers += f"\nSwarm-Spec-Hash: {spec_hash_value}"
        if run_id:
            trailers += f"\nSwarm-Run: {run_id}"
    if allow_empty and not in_scope:
        trailers += "\nSwarm-Vacancy: 1"
    msg = subject + trailers
    commit_args = ["git", "commit"]
    if allow_empty and not in_scope:
        commit_args.append("--allow-empty")
    commit_args += ["-m", msg]

    if os.getenv("SWARM_MERGE_MODE", "merge").lower() == "direct":
        if in_scope:
            rc, out = _sh(["git", "add", "-A", "--", *in_scope])
            if rc != 0:
                rec["commit"] = f"git add failed: {out}"
                return rec
        rc, out = _sh(commit_args)
        if rc != 0:
            rec["commit"] = f"git commit failed: {out}"
            return rec
        rec["commit"] = msg
        rc, out = _sh(["git", "push"])
        rec["push"] = "ok" if rc == 0 else f"failed: {out}"
        rec["ok"] = "1" if rc == 0 else "0"
        return rec

    base = os.getenv("SWARM_BASE_BRANCH", "").strip()
    if not base:
        rc, out = _git(["rev-parse", "--abbrev-ref", "HEAD"])
        base = out.strip().splitlines()[-1] if rc == 0 and out.strip() else ""
        if base == "HEAD":  # detached
            base = ""
    if not base or base == "HEAD":
        rec["commit"] = "refused: detached HEAD (set SWARM_BASE_BRANCH)"
        return rec
    rec["base"] = base
    branch = _unique_branch(_branch_name(spec_id, task_id))
    rec["branch"] = branch

    rc, out = _git(["switch", "-c", branch])
    if rc != 0:
        rec["commit"] = f"git switch -c {branch} failed: {out}"
        return rec
    if in_scope:
        rc, out = _git(["add", "-A", "--", *in_scope])
        if rc != 0:
            rec["commit"] = f"git add failed: {out}"
            _git(["switch", base])
            return rec
    rc, out = _git(commit_args[1:])
    if rc != 0:
        rec["commit"] = f"git commit failed: {out}"
        _git(["switch", base])
        return rec
    rec["commit"] = msg

    rc, out = _git(["push", "-u", "origin", branch])
    if rc != 0:
        rec["push"] = f"failed: {out}"
        rec["rollback"] = f"kept local branch {branch} (base untouched)"
        _git(["switch", base])
        return rec
    rec["push"] = f"ok ({branch})"

    rc, out = _git(["switch", base])
    if rc != 0:
        rec["merge"] = f"switch to {base} failed: {out}"
        return rec
    pre_rc, pre = _git(["rev-parse", "HEAD"])
    pre_sha = pre.strip().splitlines()[-1] if pre_rc == 0 and pre.strip() else ""
    merge_msg = f"merge: swarm {spec_id}-{task_id} green"
    rc, out = _git(["merge", "--no-ff", branch, "-m", merge_msg])
    if rc != 0:
        _git(["merge", "--abort"])
        rec["merge"] = f"conflict: {out}"
        return rec
    rec["merge"] = "ok"

    rc, out = _git(["push", "origin", base])
    if rc != 0:
        rec["push"] = f"failed (merge not pushed): {out}"
        if pre_sha:
            _git(["reset", "--hard", pre_sha])
            rec["rollback"] = f"reset {base} to {pre_sha[:8]}; branch {branch} kept"
        return rec
    rec["ok"] = "1"
    if os.getenv("SWARM_DELETE_MERGED_BRANCH", "0") == "1":
        _git(["branch", "-d", branch])
        _git(["push", "origin", "--delete", branch])
    return rec


def _frontend_test_command() -> str | None:
    """Optional frontend gate: `npm test` when the script + vitest binary exist.

    Frontend work (007/010) adds vitest under `frontend/`; backend-only checkouts
    have no `test` script, so the gate stays dormant instead of failing every run.
    """
    pkg = REPO_ROOT / "frontend" / "package.json"
    vitest = REPO_ROOT / "frontend" / "node_modules" / ".bin" / "vitest"
    if not pkg.is_file() or not vitest.exists():
        return None
    try:
        scripts = json.loads(pkg.read_text()).get("scripts", {})
    except (OSError, json.JSONDecodeError):
        return None
    return "npm --prefix frontend test -- --run" if "test" in scripts else None


def _frontend_check_command() -> str | None:
    """`npm run check` when the frontend is installed (svelte-check gate)."""
    pkg = REPO_ROOT / "frontend" / "package.json"
    if not pkg.is_file() or not (REPO_ROOT / "frontend" / "node_modules").is_dir():
        return None
    try:
        scripts = json.loads(pkg.read_text()).get("scripts", {})
    except (OSError, json.JSONDecodeError):
        return None
    return "npm --prefix frontend run check" if "check" in scripts else None


class RunLock:
    """Repo-wide exclusive lock so two pilots can never share the worktree."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh: Any = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("w")
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._fh.close()
            self._fh = None
            return False
        self._fh.write(str(os.getpid()))
        self._fh.flush()
        return True

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            self._fh.close()
        except OSError:
            pass
        self._fh = None


def _unique_run_id() -> str:
    """Timestamp + pid + random suffix: sortable and collision-free."""
    base = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    for _ in range(100):
        rid = f"{base}-{os.getpid()}-{uuid.uuid4().hex[:4]}"
        if not (_runs_dir() / rid).exists():
            return rid
    raise SystemExit("could not allocate a unique run directory")


def approval_path(spec_dir: str, task_id: str) -> Path:
    d = _runs_dir() / "approvals"
    d.mkdir(parents=True, exist_ok=True)
    try:
        key = _spec_path(spec_dir).name
    except (OSError, SystemExit):
        key = spec_dir
    return d / f"{_safe_key(f'{key}-{task_id}')}.json"


def approval_granted(spec_dir: str, task_id: str, run_dir: Path | None = None) -> bool:
    """Approval from this run's approved.json or the task-keyed ledger."""
    candidates = [approval_path(spec_dir, task_id)]
    if run_dir is not None:
        candidates.insert(0, Path(run_dir) / "approved.json")
    for p in candidates:
        try:
            if json.loads(p.read_text()).get("approved") is True:
                return True
        except (OSError, json.JSONDecodeError):
            pass
    return False


def grant_approval(spec_dir: str, task_id: str) -> Path:
    p = approval_path(spec_dir, task_id)
    p.write_text(
        json.dumps(
            {"approved": True, "spec": spec_dir, "task": task_id, "at": dt.datetime.now().isoformat(timespec="seconds")}
        )
    )
    return p


def _run_status(run_dir: Path) -> str:
    """Status of a previous run; meta-only means the process was killed."""
    try:
        return str(json.loads((run_dir / "run.json").read_text()).get("status", ""))
    except (OSError, json.JSONDecodeError):
        return "killed"


def _previous_run(
    repo_root: Path,
    spec_dir: str,
    task_id: str,
    current_run: Path | None,
) -> Path | None:
    """Newest earlier run for the same spec/task."""
    runs = repo_root / "swarm" / "runs"
    if not runs.is_dir():
        return None
    dirs = sorted(
        (p for p in runs.iterdir() if p.is_dir() and p.name[:1].isdigit()),
        reverse=True,
    )
    current = current_run.resolve() if current_run else None
    for d in dirs:
        if current is not None and d.resolve() == current:
            continue
        rec: dict[str, Any] = {}
        for fname in ("run.json", "meta.json"):
            try:
                rec = json.loads((d / fname).read_text())
                break
            except (OSError, json.JSONDecodeError):
                rec = {}
        if str(rec.get("spec")) == spec_dir and str(rec.get("task")) == task_id:
            return d
    return None


def load_checkpoint(
    prev_run: Path,
    *,
    spec_dir: str,
    task_id: str,
    plan_hash: str,
    steps: list[str],
    max_age: int = 86400,
    now: float | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """Validate `progress.json`; returns (payload, '') or (None, reason)."""
    from swarm.tools_guarded import hash_paths

    try:
        prog = json.loads((prev_run / "progress.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None, "no progress.json"
    if str(prog.get("spec")) != spec_dir or str(prog.get("task")) != task_id:
        return None, "spec/task changed"
    if str(prog.get("plan_hash")) != plan_hash:
        return None, "plan changed"
    if list(prog.get("steps") or []) != list(steps):
        return None, "steps changed"
    completed = int(prog.get("completed") or 0)
    outputs = list(prog.get("step_outputs") or [])
    if completed < 0 or completed > len(steps) or len(outputs) != completed:
        return None, "malformed progress"
    delta = prog.get("delta_hashes") or {}
    if not isinstance(delta, dict) or hash_paths(list(delta)) != delta:
        return None, "worktree changed"
    try:
        updated = dt.datetime.fromisoformat(str(prog.get("updated_at", ""))).timestamp()
    except (TypeError, ValueError):
        return None, "bad timestamp"
    if (now if now is not None else time.time()) - updated > max_age:
        return None, "checkpoint too old"
    return prog, ""


def _find_held_run(repo_root: Path, spec_dir: str, task_id: str) -> Path | None:
    """Newest run for this task still parked at `awaiting_approval`."""
    runs = repo_root / "swarm" / "runs"
    if not runs.is_dir():
        return None
    dirs = sorted(
        (p for p in runs.iterdir() if p.is_dir() and p.name[:1].isdigit()),
        reverse=True,
    )
    for d in dirs:
        try:
            rec = json.loads((d / "run.json").read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if (
            rec.get("status") == "awaiting_approval"
            and str(rec.get("task")) == task_id
            and str(rec.get("spec")) == spec_dir
        ):
            return d
    return None


def approve_held_run(
    repo_root: Path,
    spec_prefix: str,
    task_id: str,
    *,
    commit_fn: Any = None,
) -> dict[str, Any]:
    """Commit a held run's verified delta through the normal merge queue (013 T4/T5).

    Refuses when the worktree, recorded hashes, or HEAD changed since the hold.
    Returns ``{ok, code?, note?, run?, autocommit?}``; ``code=="none"`` means the
    caller should fall back to the next-run approval ledger.
    """
    from swarm.done import record_done, spec_plan_hash, task_hash
    from swarm.spec_loader import load_spec_tasks
    from swarm.tools_guarded import (
        _git_changed,
        hash_paths,
        is_secret_path,
        scope_violations,
    )

    try:
        spec_path, tasks = load_spec_tasks(repo_root, spec_prefix, task_id)
    except (OSError, SystemExit) as e:
        return {"ok": "0", "note": f"spec not found: {e}"}
    if not tasks:
        return {"ok": "0", "note": f"no task {task_id} in {spec_prefix}"}
    task = tasks[0]
    spec_dir = spec_path.name
    run_dir = _find_held_run(repo_root, spec_dir, task_id)
    if run_dir is None:
        return {"ok": "0", "code": "none", "note": "no held run"}

    try:
        rec = json.loads((run_dir / "run.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {"ok": "0", "note": f"unreadable run.json in {run_dir}"}
    delta = rec.get("delta_hashes") or {}
    if not isinstance(delta, dict) or not delta:
        return {"ok": "0", "note": "held run has no delta hashes (rerun the task)"}

    current = hash_paths(list(delta))
    drifted = sorted(p for p, h in delta.items() if current.get(p) != h)
    if drifted:
        return {"ok": "0", "note": f"worktree changed since hold: {drifted}"}

    scope = _resolve_scope()
    secret = [p for p in delta if is_secret_path(p)]
    if secret:
        return {"ok": "0", "note": f"refused: secret path in held delta: {secret}"}
    changed_now = _git_changed()
    extra = [
        p
        for p in changed_now
        if p not in delta and p not in scope_violations([p], scope)
    ]
    if extra:
        return {"ok": "0", "note": f"new in-scope changes since hold: {extra}"}

    head = str(rec.get("head", ""))
    if head:
        rc, _ = _git(["merge-base", "--is-ancestor", head, "HEAD"])
        if rc != 0:
            return {"ok": "0", "note": "HEAD no longer descends from the held run"}

    commit = commit_fn or _commit_changes
    result = commit(
        spec_dir,
        task_id,
        task.brief,
        paths=list(delta),
        task_hash_value=task_hash(task),
        spec_hash_value=spec_plan_hash(spec_path),
        run_id=run_dir.name,
    )
    if result.get("ok") != "1":
        rec["approval_error"] = result.get("merge") or result.get("push") or result.get("commit", "commit failed")
        (run_dir / "run.json").write_text(json.dumps(rec, indent=2))
        return {"ok": "0", "note": f"commit failed: {rec['approval_error']}", "autocommit": result}

    rec["status"] = "green"
    rec["approved"] = True
    rec["autocommit"] = result
    rec["approval"] = {
        "mode": "resume",
        "at": dt.datetime.now().isoformat(timespec="seconds"),
        "run": run_dir.name,
    }
    rec.setdefault("done", {})["recorded"] = True
    (run_dir / "run.json").write_text(json.dumps(rec, indent=2))
    record_done(
        repo_root,
        spec_dir,
        task_id,
        task_hash_value=task_hash(task),
        spec_hash_value=spec_plan_hash(spec_path),
        run_id=run_dir.name,
    )
    try:
        (run_dir / "progress.json").unlink()
    except OSError:
        pass
    grant_approval(spec_dir, task_id)
    return {"ok": "1", "run": run_dir.name, "autocommit": result}



class SwarmFlow(Flow[SwarmState]):
    def __init__(
        self,
        spec_dir: str,
        task_id: str,
        no_tui: bool = True,
        allow_paid: bool = False,
        replan: bool = False,
        commit: bool = True,
        require_approval: bool | None = None,
    ) -> None:
        super().__init__()
        self._spec_dir = spec_dir
        self._task_id = task_id
        self._replan = replan
        self._commit = commit
        self._interrupted = False
        self._verdict_retried = False
        self._started_monotonic = time.monotonic()
        self.state.started_at = dt.datetime.now().isoformat(timespec="seconds")
        from swarm.usage import env_float, env_int

        self._max_tokens = env_int("SWARM_MAX_TOKENS", 2_000_000)
        self._max_cost = env_float("SWARM_MAX_COST_USD", 0.05)
        self._max_seconds = env_int("SWARM_MAX_RUNTIME_SECONDS", 14400)
        self._lock = RunLock(_runs_dir() / ".lock")
        if not self._lock.acquire():
            raise SystemExit("another swarm run is active (lock: swarm/runs/.lock)")
        atexit.register(self._cleanup)
        env_approval = os.getenv("SWARM_REQUIRE_APPROVAL", "0") == "1"
        self._require_approval = env_approval if require_approval is None else require_approval
        self.state.approval_required = self._require_approval
        self._install_signals()
        # Baseline before any LLM/tool call: only this run's changes count.
        from swarm.tools_guarded import snapshot_worktree

        self._baseline = snapshot_worktree()
        self.run_dir = _runs_dir() / _unique_run_id()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (_runs_dir() / "latest").write_text(self.run_dir.name)
        (_runs_dir() / "swarm.pid").write_text(str(os.getpid()))
        meta = {
            "spec": spec_dir,
            "task": task_id,
            "pid": os.getpid(),
            "started_at": dt.datetime.now().isoformat(timespec="seconds"),
            "approval_required": self._require_approval,
        }
        (self.run_dir / "meta.json").write_text(json.dumps(meta))
        print(f"run_dir={self.run_dir}", flush=True)

    def _install_signals(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            return

        def _handler(signum: int, _frame: Any) -> None:
            self._interrupted = True
            raise SystemExit(128 + signum)

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, _handler)
            except (OSError, ValueError):
                pass

    def _cleanup(self) -> None:
        with contextlib.suppress(Exception):
            self._lock.release()
        pid = _runs_dir() / "swarm.pid"
        try:
            if pid.is_file() and pid.read_text().strip() == str(os.getpid()):
                pid.unlink()
        except OSError:
            pass

    def __del__(self) -> None:
        with contextlib.suppress(Exception):
            self._cleanup()

    # ---- usage & budgets (012 T11/T14) ----
    def _record_usage(self, crew: Any, out: Any) -> None:
        tu = getattr(out, "token_usage", None) or getattr(crew, "usage_metrics", None)
        if tu is None:
            return

        def _n(key: str) -> int:
            try:
                return int(getattr(tu, key, 0) or 0)
            except (TypeError, ValueError):
                return 0

        self.state.prompt_tokens += _n("prompt_tokens")
        self.state.completion_tokens += _n("completion_tokens")
        self.state.cached_prompt_tokens += _n("cached_prompt_tokens")
        self.state.total_tokens += _n("total_tokens")
        self.state.llm_calls += _n("successful_requests")
        for agent in getattr(crew, "agents", None) or []:
            model = getattr(getattr(agent, "llm", None), "model", "")
            if model and model not in self.state.models_used:
                self.state.models_used.append(model)

    def _run_cost(self) -> float | None:
        from swarm.usage import estimate_run_cost

        return estimate_run_cost(
            self.state.models_used, self.state.prompt_tokens, self.state.completion_tokens
        )

    def _check_budget(self) -> None:
        from swarm.usage import budget_note

        note = budget_note(
            total_tokens=self.state.total_tokens,
            cost_usd=self._run_cost(),
            elapsed_seconds=time.monotonic() - self._started_monotonic,
            max_tokens=self._max_tokens,
            max_cost_usd=self._max_cost,
            max_seconds=self._max_seconds,
        )
        if note:
            raise _BudgetExhausted(note)

    def _teardown_listener(self) -> None:
        """Unregister bus handlers but keep the object so the TUI can drain its queue."""
        listener = getattr(self, "listener", None)
        if listener is None:
            return
        with contextlib.suppress(Exception):
            listener.teardown()

    @start()
    def load_spec(self) -> dict[str, str]:
        from swarm.spec_loader import load_spec_tasks

        spec_path, tasks = load_spec_tasks(REPO_ROOT, self._spec_dir, self._task_id)
        if not tasks:
            raise SystemExit(f"No task {self._task_id} in {self._spec_dir}")
        self.state.spec_dir, self.state.task_id = self._spec_dir, tasks[0].id
        return {"spec_path": str(spec_path), "task": tasks[0].id, "brief": tasks[0].brief}

    def _run_gates(self, changed: list[str]) -> tuple[dict[str, int], str]:
        """Run constitution gates independently (never trust agent claims)."""
        from swarm.tools_guarded import ShellTool, scope_violations

        shell = ShellTool()
        gates: dict[str, int] = {}
        tails: list[str] = []
        commands = ["pytest -q", "ruff check .", "mypy app tests"]
        if frontend_check := _frontend_check_command():
            commands.append(frontend_check)
        if frontend_test := _frontend_test_command():
            commands.append(frontend_test)
        for cmd in commands:
            out = shell._run(cmd)
            try:
                gates[cmd] = int(out.split("exit=")[1].split()[0])
            except Exception:
                gates[cmd] = 99
            tails.append(f"$ {cmd}\n{out[-1200:]}")
        # Scope: only files changed by this run; pre-existing human edits are ignored.
        bad = scope_violations(changed, _resolve_scope())
        gates["scope"] = 0 if not bad else 1
        tails.append("$ scope\nOK" if not bad else f"$ scope\nVIOLATIONS: {bad}")
        return gates, "\n".join(tails)

    def _commit_green(
        self,
        brief: str,
        changed: list[str],
        *,
        task_hash_value: str = "",
        spec_hash_value: str = "",
        allow_empty: bool = False,
    ) -> dict[str, str]:
        """Commit + push run-delta in-scope changes after a green run."""
        return _commit_changes(
            self.state.spec_dir,
            self.state.task_id,
            brief,
            paths=changed,
            task_hash_value=task_hash_value,
            spec_hash_value=spec_hash_value,
            run_id=self.run_dir.name,
            allow_empty=allow_empty,
        )

    def _in_scope_dirty(self) -> list[str]:
        from swarm.tools_guarded import _git_changed, is_secret_path, scope_violations

        scope = _resolve_scope()
        return sorted(
            path
            for path in _git_changed()
            if not is_secret_path(path) and path not in scope_violations([path], scope)
        )

    def _recover_prior_delta(self, task: Any) -> tuple[list[str], str]:
        """Adopt work left dirty by this task's interrupted run.

        Only when the current in-scope dirty set exactly matches the prior
        checkpoint/run delta, so unrelated human work is never committed.
        """
        prev = _previous_run(REPO_ROOT, self.state.spec_dir, str(task.id), self.run_dir)
        if prev is None or _run_status(prev) not in ("killed", "interrupted", ""):
            return [], ""
        candidates: set[str] = set()
        try:
            prog = json.loads((prev / "progress.json").read_text())
            candidates.update((prog.get("delta_hashes") or {}).keys())
        except (OSError, json.JSONDecodeError):
            pass
        try:
            rec = json.loads((prev / "run.json").read_text())
            candidates.update(rec.get("changed_files") or [])
        except (OSError, json.JSONDecodeError):
            pass
        if not candidates:
            return [], ""
        from swarm.tools_guarded import is_secret_path, scope_violations

        scope = _resolve_scope()
        candidates = {
            path
            for path in candidates
            if not is_secret_path(path) and path not in scope_violations([path], scope)
        }
        if not candidates:
            return [], ""
        dirty = set(self._in_scope_dirty())
        # Require every prior path to still be dirty; unrelated dirty files are
        # left alone (they belong to another task/human).
        if not candidates <= dirty:
            return [], ""
        return sorted(candidates), prev.name

    def _delete_progress(self) -> None:
        try:
            (self.run_dir / "progress.json").unlink()
        except OSError:
            pass

    def _repair_verdict(self, task: Any, transcript: str) -> None:
        """One clean verdict-only retry when the reviewer omitted PASS/BLOCKED.

        Tries the reviewer first, then the senior model. Only overrides an
        explicit PASS/BLOCKED with a parsed PASS/BLOCKED; otherwise leaves
        `unknown` so the run still stops as needs_human.
        """
        if self.state.review_verdict != "unknown" or self._verdict_retried:
            return
        self._verdict_retried = True
        from swarm.llms import reviewer_llm, senior_llm

        prompt = (
            f"Task: {task.id} — {task.brief}\n"
            f"Gate transcript (tail):\n{transcript[-1500:]}\n\n"
            "The deterministic gates are shown above. Reply with exactly one line:\n"
            "VERDICT: PASS\n"
            "or\n"
            "VERDICT: BLOCKED\n"
            "No code, no explanation, no repeating the work summary."
        )
        for factory in (reviewer_llm, senior_llm):
            out: str | None = None
            try:
                out = str(factory().call(prompt))
            except Exception:
                out = None
            if out is None:
                continue
            verdict = reviewer_verdict(out)
            if verdict != "unknown":
                self.state.review_verdict = verdict
                self.state.review_text = f"{self.state.review_text}\n--- verdict repair ---\n{out}"
                print(f"reviewer verdict repaired: {verdict}", flush=True)
                return

    def _write_progress(
        self,
        plan_hash: str,
        steps: list[str],
        completed: int,
        step_outputs: list[str],
    ) -> None:
        """Atomically persist step progress so a kill can resume (013 T6)."""
        from swarm.tools_guarded import hash_paths, run_delta

        payload = {
            "run_id": self.run_dir.name,
            "spec": self.state.spec_dir,
            "task": self.state.task_id,
            "plan_hash": plan_hash,
            "steps": list(steps),
            "completed": completed,
            "step_outputs": list(step_outputs),
            "delta_hashes": hash_paths(run_delta(self._baseline)),
            "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        path = self.run_dir / "progress.json"
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2))
            os.replace(tmp, path)
        except OSError:
            pass

    def _resume_checkpoint(
        self,
        task: Any,
        plan_text: str,
        steps: list[str],
    ) -> tuple[dict[str, Any] | None, str]:
        """Find a valid checkpoint from a killed/interrupted previous run."""
        prev = _previous_run(REPO_ROOT, self.state.spec_dir, str(task.id), self.run_dir)
        if prev is None:
            return None, ""
        if _run_status(prev) not in ("killed", "interrupted", ""):
            return None, ""
        try:
            max_age = int(os.getenv("SWARM_RESUME_MAX_AGE_SECONDS", "86400") or 86400)
        except ValueError:
            max_age = 86400
        plan_hash = hashlib.sha256(plan_text.encode()).hexdigest()
        prog, note = load_checkpoint(
            prev,
            spec_dir=self.state.spec_dir,
            task_id=str(task.id),
            plan_hash=plan_hash,
            steps=steps,
            max_age=max_age,
        )
        if prog is None:
            return None, f"checkpoint in {prev.name} rejected: {note}"
        return prog, ""

    @listen(load_spec)
    def run_crew(self, ctx: dict[str, str]) -> str:
        from swarm.crew import (
            DEV_ATTEMPTS,
            MAX_FIX_ROUNDS,
            PLAN_ATTEMPTS,
            SENIOR_ATTEMPTS,
            STEP_ATTEMPTS,
            build_fix_crew,
            build_plan_crew,
            build_review_crew,
            build_senior_crew,
            build_senior_step_crew,
            build_step_crew,
        )
        from swarm.events import SwarmListener
        from swarm.spec_loader import load_spec_tasks
        from swarm.tools_guarded import run_delta

        # Fail before the first LLM call: models, keys, Ollama, venvs, gates.
        if os.getenv("SWARM_SKIP_PREFLIGHT", "0") != "1":
            from swarm.preflight import check as preflight_check

            problems = preflight_check()
            if problems:
                note = "; ".join(str(p) for p in problems)
                self.state.result = f"preflight failed: {note}"[:4000]
                self.state.status = "preflight_failed"
                print(f"PREFLIGHT FAILED: {note}"[:1500], flush=True)
                self.save_run("preflight_failed")
                return self.state.result

        task = load_spec_tasks(REPO_ROOT, self._spec_dir, self._task_id)[1][0]
        self.listener = SwarmListener(self.run_dir)  # always trace, TUI or headless
        cache = plan_cache_path(self._spec_dir, task.id)
        source_hash = plan_source_hash(self._spec_dir)

        def _kickoff(build: Any) -> tuple[Any, str]:
            """Run a fresh crew, with quota fallback + rate-limit backoff (012 T13)."""
            from swarm.llms import activate_fallbacks, fallbacks_active
            from swarm.retry import backoff_delay, is_retryable

            last_err: Exception | None = None
            switched = fallbacks_active()
            for attempt in (1, 2, 3):
                try:
                    crew = build()
                    out = crew.kickoff()
                except Exception as e:
                    last_err = e
                    if _is_quota_error(e):
                        if not switched:
                            switched = True
                            activate_fallbacks()
                            print("quota hit → retrying with fallback models", flush=True)
                            continue
                        raise _QuotaExhausted(f"free-models-per-day quota hit: {e}"[:500]) from e
                    if is_retryable(e) and attempt < 3:
                        time.sleep(backoff_delay(attempt))
                        continue
                    break
                else:
                    self._record_usage(crew, out)
                    self._check_budget()
                    return crew, str(out)[:8000]
            raise SystemExit(f"crew failed after retries, trace in {self.run_dir}/run.json") from last_err

        def _plan_text(crew: Any) -> str:
            try:
                plan_out = getattr(crew.tasks[0], "output", None)
                text = getattr(plan_out, "raw", None) or str(plan_out)
                return text if text != "None" else ""
            except Exception:
                return ""

        try:
            plan_text = ""
            if cache.is_file() and not self._replan:
                cached = read_cached_plan(cache, source_hash)
                if _resolve_steps(cached):
                    # Proven plan for the current spec content: skip re-planning.
                    plan_text = cached
                    self.state.plan_reused = True
            for _ in range(PLAN_ATTEMPTS):
                if _resolve_steps(plan_text):
                    break
                plan_crew, _ = _kickoff(lambda: build_plan_crew(self._spec_dir, task))
                plan_text = _plan_text(plan_crew)
            steps = _resolve_steps(plan_text)
            if not steps:
                raise SystemExit("planner returned no usable plan (no STEP lines or over step budget)")
            write_cached_plan(cache, plan_text, source_hash)
            plan_hash = hashlib.sha256(plan_text.encode()).hexdigest()
            checkpoint, recovery_note = self._resume_checkpoint(task, plan_text, steps)
            resume_from = int(checkpoint.get("completed") or 0) if checkpoint else 0
            checkpoint_outputs = list(checkpoint.get("step_outputs") or []) if checkpoint else []
            if checkpoint:
                self.state.resumed_from_step = resume_from
                self.state.recovery = "checkpoint"
                print(f"resuming {task.id} after step {resume_from}/{len(steps)}", flush=True)
            elif recovery_note:
                self.state.recovery = "restart"
                self.state.recovery_note = recovery_note
                print(f"restarting {task.id}: {recovery_note}", flush=True)
            gates: dict[str, int] = {}
            transcript = ""
            # Dev phase (micro-steps + review + gates + fix round), up to
            # DEV_ATTEMPTS; then senior escalation, then human.
            while True:
                self.state.dev_attempts += 1
                if self.state.dev_attempts > 1:
                    resume_from = 0
                    checkpoint_outputs = []
                # Micro-execution: fresh coder (fresh context) per step; reviewer only at the end.
                # A step failing STEP_ATTEMPTS times is rescued by the senior, then we continue.
                step_outs: list[str] = list(checkpoint_outputs)
                self._write_progress(plan_hash, steps, len(step_outs), step_outs)
                for i, step in enumerate(steps, 1):
                    if i <= resume_from:
                        continue
                    step_out = ""
                    last_err: BaseException | None = None
                    for _ in range(STEP_ATTEMPTS):
                        try:
                            _, step_out = _kickoff(
                                lambda step=step, i=i: build_step_crew(self._spec_dir, task, step, i, len(steps))
                            )
                            last_err = None
                            break
                        except _QuotaExhausted:
                            raise
                        except SystemExit as e:
                            last_err = e
                    if last_err is not None:
                        self.state.senior_used = True
                        self.state.senior_rounds += 1
                        _, step_out = _kickoff(
                            lambda step=step, i=i, last_err=last_err: build_senior_step_crew(
                                self._spec_dir, task, step, i, len(steps), str(last_err)
                            )
                        )
                    step_outs.append(f"--- step {i}/{len(steps)} ---\n{step_out}")
                    self._write_progress(plan_hash, steps, i, step_outs)
                work_summary = "\n".join(step_outs)
                _, review_out = _kickoff(lambda work_summary=work_summary: build_review_crew(self._spec_dir, task, work_summary))
                self.state.review_verdict = reviewer_verdict(review_out)
                self.state.review_text = review_out
                self.state.result = f"{work_summary}\n--- review ---\n{review_out}"[:8000]
                # Fix loop: gate fail → coder retry with transcript (bounded) → re-gate.
                base_rounds = self.state.fix_rounds
                changed = run_delta(self._baseline)
                gates, transcript = self._run_gates(changed)
                if all(v == 0 for v in gates.values()):
                    self._repair_verdict(task, transcript)
                while not all(v == 0 for v in gates.values()) and self.state.fix_rounds - base_rounds < MAX_FIX_ROUNDS:
                    self.state.fix_rounds += 1
                    self.state.transcript = transcript
                    try:
                        _, fix_out = _kickoff(lambda transcript=transcript: build_fix_crew(self._spec_dir, task, transcript))
                        self.state.review_verdict = reviewer_verdict(fix_out)
                        self.state.review_text = fix_out
                        self.state.result = str(fix_out)[:8000]
                    except SystemExit as e:
                        self.state.result = str(e)[:4000]
                        break
                    changed = run_delta(self._baseline)
                    gates, transcript = self._run_gates(changed)
                    if all(v == 0 for v in gates.values()):
                        self._repair_verdict(task, transcript)
                if all(v == 0 for v in gates.values()) or self.state.dev_attempts >= DEV_ATTEMPTS:
                    break
            if not all(v == 0 for v in gates.values()):
                # Senior escalation: up to SENIOR_ATTEMPTS full fix passes by the
                # strong free-tier brain, QA re-verifies each round via review + gates.
                while not all(v == 0 for v in gates.values()) and self.state.senior_rounds < SENIOR_ATTEMPTS:
                    self.state.senior_used = True
                    self.state.senior_rounds += 1
                    self.state.transcript = transcript
                    try:
                        _, senior_out = _kickoff(lambda transcript=transcript: build_senior_crew(self._spec_dir, task, transcript))
                        self.state.review_verdict = reviewer_verdict(senior_out)
                        self.state.result = str(senior_out)[:8000]
                    except SystemExit as e:
                        self.state.result = str(e)[:4000]
                        raise
                    _, review_out = _kickoff(lambda: build_review_crew(self._spec_dir, task, self.state.result))
                    self.state.review_verdict = reviewer_verdict(review_out)
                    self.state.review_text = review_out
                    self.state.result = f"{self.state.result}\n--- senior review ---\n{review_out}"[:8000]
                    changed = run_delta(self._baseline)
                    gates, transcript = self._run_gates(changed)
                    if all(v == 0 for v in gates.values()):
                        self._repair_verdict(task, transcript)
            self.state.changed_files = run_delta(self._baseline)
        except _QuotaExhausted as e:
            self.state.result = str(e)[:4000]
            self.state.status = "quota_exhausted"
            self.state.quota_note = f"{self._spec_dir}/{self.state.task_id or self._task_id}: {e}"[:500]
            print(f"QUOTA EXHAUSTED: {self.state.quota_note} — pilot stopped, resume after reset", flush=True)
            self.save_run("quota_exhausted")
            return self.state.result
        except _BudgetExhausted as e:
            self.state.result = str(e)[:4000]
            self.state.budget_note = str(e)[:500]
            self.state.status = "budget_exhausted"
            print(f"BUDGET EXHAUSTED: {e} — pilot stopped", flush=True)
            self.save_run("budget_exhausted")
            return self.state.result
        except SystemExit as e:
            self.state.result = str(e)[:4000]
            self.state.status = "interrupted" if self._interrupted else "crew_error"
            self.save_run(self.state.status)
            raise
        self.state.gates = gates
        self.state.transcript = transcript
        self.state.status = "crew_done"
        return self.state.result

    @listen(run_crew)
    def gate(self, result: str) -> str:
        # Gates already ran inside run_crew (fix loop needs them mid-stage);
        # this listener only maps them to a final status. Terminal states pass
        # through untouched.
        if self.state.status in TERMINAL_STATUSES:
            return self.state.status
        if getattr(self, "_interrupted", False):
            self.state.status = "interrupted"
        elif (
            not self.state.gates
            or not all(v == 0 for v in self.state.gates.values())
            or self.state.review_verdict != "pass"
        ):
            self.state.status = "needs_human"
        else:
            self.state.status = "green"
        return self.state.status

    @listen(gate)
    def save_run(self, status: str) -> str:
        from swarm.done import record_done, spec_plan_hash, task_hash
        from swarm.spec_loader import load_spec_tasks
        from swarm.tools_guarded import hash_paths, in_scope_changes, run_delta

        spec_path: Path | None = None
        try:
            spec_path, tasks = load_spec_tasks(REPO_ROOT, self.state.spec_dir, self.state.task_id)
            task = tasks[0] if tasks else None
        except (OSError, SystemExit):
            task = None
        task_hash_value = task_hash(task) if task else ""
        spec_hash_value = spec_plan_hash(spec_path) if spec_path else ""
        brief = task.brief if task else ""
        ac_refs = list(task.ac_refs) if task else []
        scope = _resolve_scope()
        changed = run_delta(self._baseline)
        in_scope = in_scope_changes(changed, scope)
        approved = approval_granted(self.state.spec_dir, self.state.task_id, self.run_dir)
        self.state.changed_files = changed
        self.state.approved = approved
        in_scope_hashes = hash_paths(in_scope)
        head_rc, head_out = _git(["rev-parse", "HEAD"])
        head = head_out.strip().splitlines()[-1] if head_rc == 0 and head_out.strip() else ""
        self.state.finished_at = dt.datetime.now().isoformat(timespec="seconds")
        cost = self._run_cost()
        usage = {
            "prompt_tokens": self.state.prompt_tokens,
            "completion_tokens": self.state.completion_tokens,
            "cached_prompt_tokens": self.state.cached_prompt_tokens,
            "total_tokens": self.state.total_tokens,
            "llm_calls": self.state.llm_calls,
            "models": list(self.state.models_used),
            "cost_usd": cost,
            "started_at": self.state.started_at,
            "finished_at": self.state.finished_at,
            "duration_seconds": round(time.monotonic() - self._started_monotonic, 1),
        }

        payload: dict[str, Any] = {
            "spec": self.state.spec_dir,
            "task": self.state.task_id,
            "brief": brief,
            "ac_refs": ac_refs,
            "status": status,
            "gates": self.state.gates,
            "fix_rounds": self.state.fix_rounds,
            "dev_attempts": self.state.dev_attempts,
            "senior_used": self.state.senior_used,
            "senior_rounds": self.state.senior_rounds,
            "quota_note": self.state.quota_note,
            "plan_reused": self.state.plan_reused,
            "review_verdict": self.state.review_verdict,
            "changed_files": changed,
            "in_scope_changes": in_scope,
            "approval_required": self._require_approval,
            "approved": approved,
            "result_tail": self.state.result[-2000:],
            "review_tail": self.state.review_text[-3000:],
            "gate_transcript_tail": self.state.transcript[-2000:],
            "cost": cost,
            "cost_note": (
                "free/local models"
                if cost == 0.0
                else ("unknown price for paid model" if cost is None else "estimated from token usage")
            ),
            "usage": usage,
            "budget": {
                "max_tokens": self._max_tokens,
                "max_cost_usd": self._max_cost,
                "max_runtime_seconds": self._max_seconds,
            },
            "budget_note": self.state.budget_note,
            "done": {"task_hash": task_hash_value, "spec_hash": spec_hash_value, "recorded": False},
            "resumed_from_step": self.state.resumed_from_step,
            "recovery": self.state.recovery,
            "recovery_note": self.state.recovery_note,
        }
        allow_empty = False
        if status == "green":  # noqa: SIM102 - recovery block is intentionally separate
            if not in_scope:
                # Nothing new from this run. Recover work left by the same task's
                # interrupted run, else record an empty green commit (already done).
                recovered, prev_name = self._recover_prior_delta(task) if task else ([], "")
                dirty_in_scope = self._in_scope_dirty()
                if recovered:
                    changed = recovered
                    in_scope = recovered
                    in_scope_hashes = hash_paths(in_scope)
                    payload["changed_files"] = changed
                    payload["in_scope_changes"] = in_scope
                    payload["recovered_from"] = prev_name
                    payload["vacancy_note"] = (
                        f"recovered pre-existing in-scope work from {prev_name}"
                    )
                elif not dirty_in_scope:
                    allow_empty = True
                    payload["vacancy_note"] = (
                        "no in-scope changes; recording an empty green commit (already satisfied)"
                    )
                else:
                    status = "needs_human"
                    payload["vacancy_note"] = (
                        "green gates but in-scope work is pre-existing/unrelated: "
                        f"{dirty_in_scope}"
                    )
        if status == "green":
            if self.state.review_verdict != "pass":
                status = "needs_human"
                payload["review_note"] = f"reviewer verdict was {self.state.review_verdict!r}, not PASS"
            elif self._require_approval and not approved:
                status = "awaiting_approval"
                payload["delta_hashes"] = in_scope_hashes
                payload["head"] = head
                payload["approval_note"] = (
                    f"approval required: press `a` in the dashboard or run with --approve "
                    f"({approval_path(self.state.spec_dir, self.state.task_id)})"
                )
            elif self._commit:
                rec = self._commit_green(
                    brief,
                    changed,
                    task_hash_value=task_hash_value,
                    spec_hash_value=spec_hash_value,
                    allow_empty=allow_empty,
                )
                payload["autocommit"] = rec
                if rec.get("ok") == "1":
                    record_done(
                        REPO_ROOT,
                        self.state.spec_dir,
                        self.state.task_id,
                        task_hash_value=task_hash_value,
                        spec_hash_value=spec_hash_value,
                        run_id=self.run_dir.name,
                    )
                    payload["done"]["recorded"] = True
                    self._delete_progress()
                else:
                    if rec.get("merge", "").startswith(("conflict", "switch")):
                        status = "merge_failed"
                    elif rec.get("push", "").startswith("failed"):
                        status = "push_failed"
                    else:
                        status = "commit_failed"
                    payload["status"] = status
        payload["status"] = status
        if status == "green":
            self._delete_progress()
        payload["evidence"] = {
            "ac_refs": ac_refs,
            "gates": self.state.gates,
            "review_verdict": self.state.review_verdict,
            "changed_files": changed,
            "in_scope_changes": in_scope,
            "approved": approved,
            "usage": usage,
        }
        (self.run_dir / "run.json").write_text(json.dumps(payload, indent=2))
        self._teardown_listener()
        self._cleanup()
        return status


def _next_after(ids: list[str], current: str) -> str | None:
    """Next task id in spec order after `current`; None when done."""
    try:
        nxt = ids[ids.index(current) + 1]
    except (ValueError, IndexError):
        return None
    return nxt


# The harness never implements itself: pilots stay out of harness specs.
HARNESS_SPECS = ("009-swarm-harness", "012-dark-factory-harness", "013-dark-factory-phase-2")


def _spec_after(repo_root: Path, current_dir: str) -> str | None:
    """Next spec dir (directory order) that has tasks, skipping harness specs."""
    specs = repo_root / "specs"
    names = sorted(
        p.name
        for p in specs.iterdir()
        if p.is_dir() and (p / "tasks.md").is_file() and p.name not in HARNESS_SPECS
    )
    return _next_after(names, current_dir)


def _next_open_spec(repo_root: Path, current_dir: str) -> tuple[str, str] | None:
    """First unchecked task in a spec that sorts after `current_dir`."""
    from swarm.spec_loader import load_spec_tasks

    nxt_spec = _spec_after(repo_root, current_dir)
    while nxt_spec is not None:
        try:
            _, nt = load_spec_tasks(repo_root, nxt_spec, None)
        except (OSError, SystemExit):
            nt = []
        if nt:
            return nxt_spec, nt[0].id
        nxt_spec = _spec_after(repo_root, nxt_spec)
    return None


def _open_task_ids(repo_root: Path, spec_path: Path, tasks: list[Any]) -> list[str]:
    """Unchecked tasks minus done-ledger hits for the current spec/plan content."""
    from swarm.done import done_entries, is_done, spec_plan_hash

    entries = done_entries(repo_root)
    spec_hash = spec_plan_hash(spec_path)
    return [
        str(t.id)
        for t in tasks
        if not is_done(entries, spec_path.name, t, spec_hash)
    ]


def _next_todo(all_ids: list[str], todo_ids: list[str], current: str) -> str | None:
    """Next runnable task after `current`, preserving spec order."""
    todo = set(todo_ids)
    try:
        idx = all_ids.index(current)
    except ValueError:
        return todo_ids[0] if todo_ids else None
    for task_id in all_ids[idx + 1 :]:
        if task_id in todo:
            return task_id
    return None


def _first_open_task(repo_root: Path, skip: tuple[str, str] | None = None) -> tuple[str, str] | None:
    """Earliest unchecked, not-done task across the queue (wrap-around)."""
    from swarm.spec_loader import load_spec_tasks

    specs = repo_root / "specs"
    if not specs.is_dir():
        return None
    for name in sorted(
        p.name
        for p in specs.iterdir()
        if p.is_dir() and (p / "tasks.md").is_file() and p.name not in HARNESS_SPECS
    ):
        try:
            spec_path, tasks = load_spec_tasks(repo_root, name, None)
        except (OSError, SystemExit):
            continue
        todo = _open_task_ids(repo_root, spec_path, tasks)
        for task_id in todo:
            if skip != (name, task_id):
                return name, task_id
    return None


def _last_checkpoint_task(repo_root: Path) -> tuple[str, str] | None:
    """(spec, task) of the most recent run, held or otherwise.

    `--approve` with no explicit spec/task uses this so `make swarm-approve`
    releases the task that is actually waiting, not a hardcoded default.
    """
    runs = repo_root / "swarm" / "runs"
    if not runs.is_dir():
        return None
    candidates: list[Path] = []
    pointer = runs / "latest"
    if pointer.is_file():
        name = pointer.read_text().strip()
        if name:
            candidates.append(runs / name)
    dirs = sorted(p for p in runs.iterdir() if p.is_dir() and p.name[:1].isdigit())
    candidates.extend(reversed(dirs))
    seen: set[Path] = set()
    for run_dir in candidates:
        if run_dir in seen:
            continue
        seen.add(run_dir)
        for fname in ("run.json", "meta.json"):
            try:
                rec = json.loads((run_dir / fname).read_text())
            except (OSError, json.JSONDecodeError):
                continue
            spec, task = rec.get("spec"), rec.get("task")
            if spec and task:
                return str(spec), str(task)
    return None


def _resume_point(repo_root: Path) -> tuple[str, str] | None:
    """Where the sequence last stopped: (spec, task) to run next.

    Latest run green → next task (or first open task of a later spec). Latest run
    red, or killed before writing run.json (meta.json only) → same task again
    when it is still unchecked. A checkpoint task that is checked/absent advances
    to the next open task, then wraps to the earliest open spec so newly added
    earlier-spec tasks are never stranded. None when every spec task is green.
    """
    from swarm.spec_loader import load_spec_tasks

    runs = repo_root / "swarm" / "runs"
    if not runs.is_dir():
        return None
    dirs = sorted(p for p in runs.iterdir() if p.is_dir() and p.name[:1].isdigit())
    if not dirs:
        return None
    latest = dirs[-1]
    status = "green"
    try:
        rec = json.loads((latest / "run.json").read_text())
        spec = str(rec.get("spec", "001"))
        task = str(rec.get("task", "T1"))
        status = str(rec.get("status", "green"))
    except Exception:
        try:
            meta = json.loads((latest / "meta.json").read_text())
            spec = str(meta.get("spec", "001"))
            task = str(meta.get("task", "T1"))
            status = "killed"
        except Exception:
            return None
    try:
        spec_path, all_tasks = load_spec_tasks(repo_root, spec, None)
    except (OSError, SystemExit):
        # Missing spec/tasks file: a red/killed checkpoint still retries as written.
        return (spec, task) if status != "green" else _first_open_task(repo_root, (spec, task))
    ids = [t.id for t in all_tasks]
    todo_ids = _open_task_ids(repo_root, spec_path, all_tasks)
    if status != "green" and task in ids:
        return spec_path.name, task
    nxt = _next_todo(ids, todo_ids, task)
    if nxt is not None:
        return spec_path.name, nxt
    later = _next_open_spec(repo_root, spec_path.name)
    if later is not None:
        return later
    return _first_open_task(repo_root, (spec_path.name, task))


def run_tasks(
    spec_prefix: str,
    start_task: str,
    *,
    allow_paid: bool = False,
    replan: bool = False,
    commit: bool = True,
    single: bool = False,
    require_approval: bool | None = None,
) -> Any:
    """Run one spec task per SwarmFlow; on green, loop to the next task and spec.

    Yields (flow, status) per task. Stops after the first non-green task,
    after the last task of the last spec, or immediately when `single` is set.
    Each task keeps its own run_dir + run.json; green tasks autocommit (see save_run).
    """
    from swarm.spec_loader import load_spec_tasks

    spec_path, all_tasks = load_spec_tasks(REPO_ROOT, spec_prefix, None)
    spec_dir = spec_path.name
    all_ids = [t.id for t in all_tasks]
    todo_ids = _open_task_ids(REPO_ROOT, spec_path, all_tasks)
    if start_task not in all_ids:
        raise SystemExit(f"No task {start_task} in {spec_prefix} (have: {all_ids})")
    task_id: str | None = start_task
    flow_spec = spec_prefix  # keep the original prefix form: plan-cache keys depend on it
    while True:
        while task_id is not None:
            flow = SwarmFlow(
                flow_spec,
                task_id,
                allow_paid=allow_paid,
                replan=replan,
                commit=commit,
                require_approval=require_approval,
            )
            status = flow.kickoff()
            yield flow, status
            if single or status != "green":
                return
            task_id = _next_todo(all_ids, todo_ids, task_id)
        # Spec done and green: advance to the next spec with tasks.
        spec_dir = _spec_after(REPO_ROOT, spec_dir) or ""
        if not spec_dir:
            return
        flow_spec = spec_dir
        spec_path, all_tasks = load_spec_tasks(REPO_ROOT, spec_dir, None)
        all_ids = [t.id for t in all_tasks]
        todo_ids = _open_task_ids(REPO_ROOT, spec_path, all_tasks)
        task_id = todo_ids[0] if todo_ids else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=None)
    ap.add_argument("--task", default=None)
    ap.add_argument("--no-tui", action="store_true", default=True)
    ap.add_argument("--allow-paid", action="store_true", default=False)
    ap.add_argument("--replan", action="store_true", default=False,
                    help="ignore cached plan and run the planner again")
    ap.add_argument("--no-commit", action="store_true", default=False,
                    help="skip autocommit+push after green runs")
    ap.add_argument("--single", action="store_true", default=False,
                    help="run only the given task, do not loop to the next one")
    ap.add_argument("--resume", action="store_true", default=False,
                    help="derive spec/task from the last checkpoint (green → next, red → retry)")
    ap.add_argument("--require-approval", action="store_true", default=None,
                    help="hold green runs as awaiting_approval until approved (or SWARM_REQUIRE_APPROVAL=1)")
    ap.add_argument("--approve", action="store_true", default=False,
                    help="commit a held run now, or write the approval ledger when none is held")
    args = ap.parse_args()
    if args.resume:
        pt = _resume_point(REPO_ROOT)
        if pt is None:
            print("all specs complete, nothing to resume")
            return
        args.spec, args.task = pt
        print(f"resuming at {args.spec} {args.task}")
    elif args.approve and args.spec is None and args.task is None:
        last = _last_checkpoint_task(REPO_ROOT)
        if last is not None:
            args.spec, args.task = last
    args.spec = args.spec or "001-example-app"
    args.task = args.task or "T1"
    if args.approve:
        held = approve_held_run(REPO_ROOT, args.spec, args.task)
        if held.get("ok") == "1":
            print(f"approved+committed {args.spec} {args.task} (run {held.get('run')})")
            return
        if held.get("code") == "none":
            p = grant_approval(args.spec, args.task)
            print(f"approved {args.spec} {args.task} (no held run; ledger for the next run) → {p}")
            return
        print(f"approval failed: {held.get('note')}")
        raise SystemExit(1)
    for flow, status in run_tasks(
        args.spec,
        args.task,
        allow_paid=args.allow_paid,
        replan=args.replan,
        commit=not args.no_commit,
        single=args.single,
        require_approval=args.require_approval,
    ):
        print(f"{flow.state.task_id}: {status}")


if __name__ == "__main__":
    main()
