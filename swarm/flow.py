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
import shlex
import signal
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
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
    "config_error",
    "commit_failed",
    "push_failed",
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
    # 015: QA-owned evidence, cost attribution, routing, verification honesty.
    qa_report: dict[str, Any] = {}
    steps_meta: list[dict[str, Any]] = []
    skipped_ac: list[str] = []
    out_of_scope_reverted: list[str] = []
    stashed: list[str] = []
    stash_conflict: list[str] = []
    stash_conflict_ref: str = ""
    stash_conflict_resolution: str = ""
    stash_conflict_note: str = ""
    orphan_stashes: list[dict[str, str]] = []
    evidence_note: str = ""
    style_autofix: dict[str, Any] = {}
    # 017: the static checks (types, lint) the coder had to pass before QA.
    self_check: dict[str, Any] = {}
    # 019: the scenario verifier's verdict, rounds, findings and correction plan.
    verifier: dict[str, Any] = {}
    no_progress: bool = False
    ungrounded_block: bool = False


class _QuotaExhausted(SystemExit):
    """Daily free-model quota hit: stop the pilot, do not retry or escalate."""


class _BudgetExhausted(Exception):
    """Per-run token/cost/time budget hit (012 T14, 015 AC-6)."""


class _ConfigError(SystemExit):
    """Terminal misconfiguration (bad base URL/key/HTML body): never retried."""


def _role_model_rows() -> list[dict[str, Any]]:
    """Effective per-role models for progress.json / the dashboard."""
    try:
        from swarm.llms import role_models

        return role_models()
    except Exception:
        return []


def _fallback_role_names() -> list[str]:
    """Roles currently on a fallback model; empty when every role is primary."""
    try:
        from swarm.llms import fallback_roles

        return fallback_roles()
    except Exception:
        return []


def _fallback_key(role: str) -> str:
    """Map a crew role to the `*_MODEL` env var whose fallback it may use."""
    if role.startswith(("qa", "reviewer")):
        return "SWARM_REVIEWER_MODEL"
    if role.startswith("planner"):
        return "SWARM_PLANNER_MODEL"
    if role.startswith("verifier"):
        return "SWARM_VERIFIER_MODEL"
    if role.startswith("senior"):
        return "SWARM_SENIOR_MODEL"
    return "SWARM_CODER_MODEL"


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


_VERDICT_RE = re.compile(r"^\s*\**\s*VERDICT\s*:?\s*\**\s*(PASS|BLOCKED)\b", re.IGNORECASE | re.MULTILINE)
_STANDALONE_RE = re.compile(r"^\s*\**\s*(PASS|BLOCKED)\s*\**\s*[.!]?\s*$", re.IGNORECASE | re.MULTILINE)
_JSON_BLOCK_RE = re.compile(r"\{.*?\}", re.DOTALL)


def reviewer_verdict(text: str) -> str:
    """The reviewer's declared verdict, never a word from its reasoning.

    A 9B reviewer writes things like "the verdict should be BLOCKED" while
    thinking and can run out of iterations before its final line (006-T5). Only
    `VERDICT: …` lines (or a JSON verdict, or a standalone final word) count;
    anything else is `unknown`, which triggers one clean verdict-only retry.
    """
    body = text or ""
    for block in _JSON_BLOCK_RE.findall(body):
        try:
            data = json.loads(block)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            verdict = str(data.get("verdict", "")).strip().lower()
            if verdict in ("pass", "blocked"):
                return verdict
    hits = _VERDICT_RE.findall(body)
    if hits:
        return hits[-1].lower()
    standalone = _STANDALONE_RE.findall(body)
    return standalone[-1].lower() if standalone else "unknown"


_GROUNDED_RE = re.compile(
    r"(test_\w+|FAILED\s|\w+\.(?:py|svelte|ts|tsx|js):\d+|exit=[1-9]\d*|AC-\d+|TypeError|AssertionError)",
    re.IGNORECASE,
)


def block_is_grounded(text: str) -> bool:
    """A BLOCKED verdict must point at something checkable, not a vibe.

    006-T5 burned six paid fix rounds because the reviewer's *reasoning* said
    "the verdict should be BLOCKED" and the parser believed it. A real block
    cites a test, a file:line, a failing command, or an AC.
    """
    return bool(_GROUNDED_RE.search(text or ""))


def _gates_green(gates: dict[str, int]) -> bool:
    """All deterministic gate exit codes are 0 (empty gate map is not green)."""
    return bool(gates) and all(code == 0 for code in gates.values())


def _reason_code(status: str, payload: dict[str, Any], state: Any) -> str:
    """Machine-readable why: green, reviewer_*, gates_failed, vacancy, …"""
    if status == "green":
        return "green"
    if status != "needs_human":
        return status
    verifier = getattr(state, "verifier", None) or {}
    if verifier.get("blocked"):
        return "verifier_blocked"
    verdict = str(getattr(state, "review_verdict", "") or "")
    if getattr(state, "no_progress", False):
        return "no_progress"
    if getattr(state, "ungrounded_block", False):
        return "reviewer_blocked_ungrounded"
    if verdict == "unknown":
        return "reviewer_no_verdict"
    if verdict and verdict != "pass":
        return "reviewer_blocked"
    if payload.get("vacancy_note"):
        return "vacancy"
    gates = payload.get("gates") or {}
    if not gates or any(code != 0 for code in gates.values()):
        return "gates_failed"
    return "needs_human"


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


def _git_push(args: list[str], timeout: int = 180) -> tuple[int, str]:
    """`git push`, falling back to a working ssh transport.

    An agent shell may be unable to start `/usr/bin/ssh` at all ("No user
    exists for uid N"), so git's own transport never reaches the handshake and
    the run's push fails. `swarm.gitpush` retries the push with an explicit
    ssh command, falling back to a paramiko-based client. The first transport
    that works wins; the repo is left exactly as git left it either way.
    """
    rc, out = _git(["push", *args], timeout=timeout)
    if rc == 0:
        return rc, out
    try:
        from swarm import gitpush
    except Exception:
        return rc, out
    try:
        if gitpush.push(args=args) == 0:
            return 0, "ok (fallback ssh transport)"
    except Exception as e:
        return rc, f"{out}\n(fallback transport failed: {type(e).__name__}: {e})"
    return rc, out


def _branch_name(spec_id: str, task_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{spec_id}-{task_id}").strip("-")
    return f"swarm/{slug or 'task'}"


def _unique_branch(name: str) -> str:
    """Avoid reusing a branch left by an earlier attempt."""
    rc, _ = _git(["rev-parse", "--verify", "--quiet", f"refs/heads/{name}"])
    if rc != 0:
        return name
    return f"{name}-{dt.datetime.now().strftime('%H%M%S')}"


def _dirty_paths() -> set[str]:
    p = subprocess.run(
        ["git", "diff", "--name-only"],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if p.returncode != 0:
        return set()
    return {line.strip() for line in p.stdout.splitlines() if line.strip()}


def _unmerged_paths() -> list[str]:
    rc, out = _git(["diff", "--name-only", "--diff-filter=U"])
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def conflict_markers(paths: list[str]) -> list[str]:
    """016: paths that still contain conflict markers after the crew edited them."""
    bad: list[str] = []
    for path in paths:
        try:
            text = (REPO_ROOT / path).read_text(errors="replace")
        except OSError:
            bad.append(path)
            continue
        if any(
            line.lstrip().startswith(("<<<<<<<", ">>>>>>>", "======="))
            for line in text.splitlines()
        ):
            bad.append(path)
    return bad


def _run_gate_commands() -> list[tuple[str, int, str]]:
    """Deterministic gates for a crew-resolved merge (the crew never runs them)."""
    results: list[tuple[str, int, str]] = []
    for cmd in gate_commands():
        try:
            p = subprocess.run(
                shlex.split(cmd), check=False, cwd=REPO_ROOT, capture_output=True, text=True, timeout=1800
            )
            results.append((cmd, p.returncode, (p.stdout + p.stderr)[-400:]))
        except (OSError, subprocess.SubprocessError) as e:
            results.append((cmd, 1, str(e)[:400]))
    return results


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
    resolver: Callable[[list[str]], tuple[bool, str]] | None = None,
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
        rc, out = _git_push([])
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

    rc, out = _git_push(["-u", "origin", branch])
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
    if rc == 0:
        rec["merge"] = "ok"
    else:
        # 016: give one dedicated crew the conflicted files, then decide
        # deterministically (no markers, all gates green) whether to keep it.
        conflicts = _unmerged_paths()
        resolved = False
        note = ""
        if resolver is not None and conflicts:
            resolved, note = resolver(conflicts)
        if not resolved:
            _git(["merge", "--abort"])
            rec["merge"] = f"conflict: {out}"
            rec["conflict"] = f"{', '.join(conflicts)} — {note}".strip(" —")
            return rec
        rc_add, add_out = _git(["add", "--", *conflicts])
        rc_commit, commit_out = (
            _git(["commit", "-m", merge_msg]) if rc_add == 0 else (1, add_out)
        )
        if rc_commit != 0:
            _git(["merge", "--abort"])
            rec["merge"] = f"conflict: {out}"
            rec["conflict"] = (
                f"{', '.join(conflicts)} — commit failed: {commit_out.strip()[:200]}"
            )
            return rec
        rec["merge"] = f"ok (crew resolved: {', '.join(conflicts)})"
        rec["conflict"] = note or "resolved"

    rc, out = _git_push(["origin", base])
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


DEFAULT_GATE_COMMANDS = ("pytest -q", "ruff check .", "mypy app tests")


def gate_commands(env: dict[str, str] | None = None) -> list[str]:
    """Project gate commands: `SWARM_GATE_COMMANDS` (semicolon/newline separated).

    The harness core is project-agnostic; this repo sets pytest/ruff/mypy/npm
    check in `.env`. Defaults keep older checkouts working.
    """
    env = os.environ if env is None else env
    raw = env.get("SWARM_GATE_COMMANDS", "").strip()
    if raw:
        return [cmd.strip() for cmd in re.split(r"[;\n]", raw) if cmd.strip()]
    return list(DEFAULT_GATE_COMMANDS)


def _frontend_test_command() -> str | None:
    """Deprecated shim retained for callers; use `gate_commands()` instead."""
    return None


def _frontend_check_command() -> str | None:
    """Deprecated shim retained for callers; use `gate_commands()` instead."""
    return None


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


def same_spec(a: str, b: str) -> bool:
    """`005` and `005-saved-routes` name the same spec (queue uses prefixes)."""
    if not a or not b:
        return False
    if a == b:
        return True
    return a.startswith(b + "-") or b.startswith(a + "-")


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
        if same_spec(str(rec.get("spec")), spec_dir) and str(rec.get("task")) == task_id:
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
    path_filter: Callable[[str], bool] | None = None,
    lenient: bool = False,
) -> tuple[dict[str, Any] | None, str]:
    """Validate `progress.json`; returns (payload, '') or (None, reason)."""
    from swarm.tools_guarded import hash_paths

    try:
        prog = json.loads((prev_run / "progress.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None, "no progress.json"
    if not same_spec(str(prog.get("spec")), spec_dir) or str(prog.get("task")) != task_id:
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
    if path_filter is not None and isinstance(delta, dict):
        delta = {path: digest for path, digest in delta.items() if path_filter(path)}
    if not isinstance(delta, dict) or hash_paths(list(delta)) != delta:
        if not lenient:
            return None, "worktree changed"
        # A deleted file invalidates the whole prefix: the remaining steps build
        # on it, so redoing only the last step would resume on a missing file.
        gone = [path for path in delta if not (REPO_ROOT / path).exists()]
        if gone:
            return None, f"worktree changed: {len(gone)} file(s) missing"
        # 015 AC-7: keep the verified prefix and redo only the last step.
        prog = {**prog, "drift": True}
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
            and same_spec(str(rec.get("spec")), spec_dir)
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
        # 015 AC-6: a single task cannot eat the whole run.
        self._max_cost_task = env_float("SWARM_MAX_COST_PER_TASK", 0.05)
        self._max_seconds_task = env_int("SWARM_MAX_SECONDS_PER_TASK", 1800)
        self._task_started = time.monotonic()
        self._task_tokens_start = 0
        self._task_cost_start = 0.0
        self._usage_by_role: dict[str, dict[str, Any]] = {}
        self._usage_by_step: dict[str, dict[str, Any]] = {}
        self._failure_sigs: set[tuple[str, str]] = set()
        self._stash_ref = ""
        self._stash_sha = ""
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
        # Never kick a crew from a signal/atexit path: see save_run for the
        # run-end restore, where a conflict can be resolved and recorded.
        self._restore_stash(allow_crew=False)
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

    # ---- usage & budgets (012 T11/T14, 015 AC-6) ----
    def _record_usage(
        self,
        crew: Any,
        out: Any,
        *,
        role: str = "",
        step: Any = None,
        before: tuple[int, int] = (0, 0),
    ) -> None:
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
        models: list[str] = []
        for agent in getattr(crew, "agents", None) or []:
            model = getattr(getattr(agent, "llm", None), "model", "")
            if model:
                models.append(str(model))
                if model not in self.state.models_used:
                    self.state.models_used.append(model)
        # 015 AC-6: attribute this call to its role/step (deltas, not totals).
        prompt = self.state.prompt_tokens - int(before[0])
        completion = self.state.completion_tokens - int(before[1])
        if role or step is not None:
            from swarm.usage import estimate_cost

            model = models[0] if models else ""
            cost = estimate_cost({model: (prompt, completion)}) if model else None
            bucket = self._usage_by_role.setdefault(
                role or "unknown",
                {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0, "cost_known": True, "calls": 0},
            )
            # The model a role actually ran, not the env var: a fallback to local
            # Ollama must be visible per role in run.json (and in the dashboard).
            bucket["model"] = model or bucket.get("model", "")
            bucket["prompt_tokens"] += prompt
            bucket["completion_tokens"] += completion
            bucket["calls"] += 1
            if cost is None:
                bucket["cost_known"] = False
            else:
                bucket["cost_usd"] += cost
            if step is not None:
                key = str(step)
                entry = self._usage_by_step.setdefault(
                    key, {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0, "cost_known": True, "model": model}
                )
                entry["prompt_tokens"] += prompt
                entry["completion_tokens"] += completion
                entry["model"] = model or entry.get("model", "")
                if cost is None:
                    entry["cost_known"] = False
                else:
                    entry["cost_usd"] += cost

    def _run_cost(self) -> float | None:
        from swarm.usage import estimate_run_cost

        return estimate_run_cost(
            self.state.models_used, self.state.prompt_tokens, self.state.completion_tokens
        )

    def _usage_snapshot(self) -> dict[str, Any]:
        cost = self._run_cost()
        return {
            "prompt_tokens": self.state.prompt_tokens,
            "completion_tokens": self.state.completion_tokens,
            "cached_prompt_tokens": self.state.cached_prompt_tokens,
            "total_tokens": self.state.total_tokens,
            "llm_calls": self.state.llm_calls,
            "models": list(self.state.models_used),
            "fallback_roles": _fallback_role_names(),
            "cost_usd": cost,
            "started_at": self.state.started_at,
            "finished_at": self.state.finished_at,
            "duration_seconds": round(time.monotonic() - self._started_monotonic, 1),
            "by_role": self._usage_by_role,
            "by_step": self._usage_by_step,
        }

    def _local_coder(self) -> bool:
        """True when the coder runs on Ollama, so its spend is exactly $0."""
        try:
            from swarm.llms import role_models

            return any(
                row["role"] == "coder" and str(row["model"]).startswith("ollama/")
                for row in role_models()
            )
        except Exception:
            return False

    def _free_local_run(self) -> bool:
        """A local coder that has spent nothing: dollar/token caps are meaningless.

        The cost check is not decoration: with `SWARM_ALLOW_PAID=1` the planner or
        senior can still spend real money in a local-coder run, and that spend must
        be capped like any other.
        """
        local_fn = getattr(self, "_local_coder", None)
        if not callable(local_fn) or not local_fn():
            return False
        return self._run_cost() == 0.0

    def _check_budget(self) -> None:
        from swarm.usage import budget_note

        # Free local work must not be stopped by a dollar/token ceiling (it can
        # never spend one). The run-level time cap stays as the backstop.
        free_fn = getattr(self, "_free_local_run", None)
        local = bool(free_fn()) if callable(free_fn) else False
        note = budget_note(
            total_tokens=0 if local else self.state.total_tokens,
            cost_usd=None if local else self._run_cost(),
            elapsed_seconds=time.monotonic() - self._started_monotonic,
            max_tokens=0 if local else self._max_tokens,
            max_cost_usd=0.0 if local else self._max_cost,
            max_seconds=self._max_seconds,
        )
        if note:
            raise _BudgetExhausted(note)
        task_note = self._task_budget_note()
        if task_note:
            raise _BudgetExhausted(
                f"task {self.state.spec_dir}/{self.state.task_id}: {task_note}"
            )

    def _task_budget_note(self) -> str:
        """015 AC-6: per-task ceiling, independent of the run budget."""
        from swarm.usage import budget_note

        free_fn = getattr(self, "_free_local_run", None)
        if callable(free_fn) and free_fn():
            # 015 follow-up: a local coder costs $0 and is slow by nature; the
            # per-task cap killed three green-in-progress runs (T9 2342s, T10
            # 2039s, 005-T8 1885s). Only the run-level time cap still applies.
            return ""
        cost = self._run_cost()
        cost_delta = None if cost is None else max(0.0, cost - self._task_cost_start)
        return budget_note(
            total_tokens=self.state.total_tokens - self._task_tokens_start,
            cost_usd=cost_delta,
            elapsed_seconds=time.monotonic() - self._task_started,
            max_tokens=0,
            max_cost_usd=self._max_cost_task,
            max_seconds=self._max_seconds_task,
        )

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
        commands = gate_commands()
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

    def _qa_report(
        self,
        gates: dict[str, int],
        transcript: str,
        changed: list[str],
        missing: list[str],
    ) -> dict[str, Any]:
        """015 AC-3: the bounded report the coder investigates from."""
        from swarm.evidence import qa_report, split_tails

        return qa_report(
            gates=gates,
            tails=split_tails(transcript),
            changed=self._in_scope_paths(changed),
            verdict=self.state.review_verdict,
            reason=self.state.review_text,
            missing=missing,
        )

    def _maybe_repair_verdict(self, task: Any, gates: dict[str, int], transcript: str) -> None:
        """One verdict-only retry when QA returned no verdict.

        014-T1 (2026-11-12): the reviewer ran out of iterations mid-report, so
        `review_verdict` stayed "unknown" — and the fix rounds then had no
        grounded reason to work from, which is how a one-line label mismatch
        survived three fix rounds. The repair used to run only when the gates
        were green; a *red* run is exactly when a verdict is most needed
        (it is what tells the coder which gate is failing).
        """
        if self.state.review_verdict == "unknown":
            self._repair_verdict(task, transcript)

    def _set_review(self, review_out: str) -> None:
        self.state.review_verdict = reviewer_verdict(review_out)
        self.state.review_text = review_out
        self.state.result = review_out[:8000]

    def _delta_signature(self) -> str:
        """Hash of this run's in-scope delta, to detect rounds that change nothing."""
        from swarm.tools_guarded import hash_paths, run_delta

        paths = self._in_scope_paths(run_delta(self._baseline))
        return hashlib.sha256(json.dumps(hash_paths(paths), sort_keys=True).encode()).hexdigest()

    def _evidence_hash(self) -> str:
        """Same computation ShellTool logs, so evidence can be matched to edits."""
        from swarm.tools_guarded import _git_changed, hash_paths, in_scope_changes

        return hashlib.sha256(
            json.dumps(hash_paths(in_scope_changes(_git_changed())), sort_keys=True).encode()
        ).hexdigest()

    def _gate_evidence(
        self,
        changed: list[str],
        *,
        agents: tuple[str, ...] | None = None,
    ) -> tuple[dict[str, int], str, list[str]]:
        """015 AC-2: green comes from recorded executions, not model prose."""
        from swarm.evidence import SHELL_LOG, gate_evidence, read_executions
        from swarm.tools_guarded import scope_violations

        commands = gate_commands()
        executions = read_executions(self.run_dir / SHELL_LOG)
        gates, tails, missing = gate_evidence(
            executions=executions,
            commands=commands,
            current_hash=self._evidence_hash(),
            agents=agents,
        )
        bad = scope_violations(changed, _resolve_scope())
        gates["scope"] = 0 if not bad else 1
        tails.append("$ scope\nOK" if not bad else f"$ scope\nVIOLATIONS: {bad}")
        if missing:
            tails.append("$ missing-gates\n" + ", ".join(missing))
        return gates, "\n".join(tails), missing

    def _gates_or_evidence(self, changed: list[str]) -> tuple[dict[str, int], str, list[str]]:
        """Evidence is authoritative; `SWARM_TRUST_QA_EVIDENCE=0` restores 012 behaviour."""
        if os.getenv("SWARM_TRUST_QA_EVIDENCE", "1") == "0":
            gates, transcript = self._run_gates(changed)
            return gates, transcript, []
        used_fallback = False
        gates: dict[str, int] = {}
        transcript = ""
        missing: list[str] = []
        for attempt in range(2):
            gates, transcript, missing = self._gate_evidence(changed)
            used_fallback = False
            if missing and os.getenv("SWARM_GATE_FALLBACK", "1") == "1":
                # The local QA model sometimes skips a gate. The harness runs only the
                # missing ones and records them; QA stays the primary executor.
                from swarm.tools_guarded import ShellTool

                runner = ShellTool(agent_role="harness-fallback")
                for command in missing:
                    runner._run(command)
                gates, transcript, missing = self._gate_evidence(
                    changed, agents=("QA Gatekeeper", "harness-fallback")
                )
                used_fallback = True
            if attempt == 0 and self._autofix_style(gates, transcript):
                # The formatter changed files, so the evidence hash moved: the
                # gates have to run again before anything is called green.
                continue
            break
        if missing:
            self.state.evidence_note = "no evidence for: " + ", ".join(missing)
            print(f"qa_gate_missing: {missing}", flush=True)
        elif used_fallback:
            self.state.evidence_note = "harness ran gates QA skipped"
            print("gate fallback: harness ran gates QA skipped", flush=True)
        else:
            self.state.evidence_note = ""
        self._evidence_agents = ("QA Gatekeeper", "harness-fallback") if used_fallback else None
        return gates, transcript, missing

    def _apply_formatter(self, gate: str) -> bool:
        """Run the project's formatter; revert files this run does not own.

        Shared by the QA path (`_autofix_style`) and the pre-QA self-check
        (017): formatting is mechanical, so the harness does it in both
        places and the coder never spends a round on a wrap.
        """
        from swarm import style
        from swarm.tools_guarded import ShellTool, _git_changed, run_delta

        before = set(_git_changed())
        runner = ShellTool(agent_role="harness-style")
        output = runner._run(style.fix_command())
        after = set(_git_changed())
        touched = sorted(after - before)
        # The formatter may reach files this run does not own: undo those.
        mine = set(run_delta(self._baseline)) | before
        foreign = [path for path in touched if path not in mine]
        reverted: list[str] = []
        for path in foreign:
            listed = _git(["ls-files", "--error-unmatch", path])[0] == 0
            if listed:
                rc, _ = _git(["checkout", "--", path])
            else:
                try:
                    (REPO_ROOT / path).unlink()
                    rc = 0
                except OSError:
                    rc = 1
            if rc == 0:
                reverted.append(path)
        self.state.style_autofix = {
            "gate": gate,
            "command": style.fix_command(),
            "files": touched,
            "reverted": reverted,
            "output": output[-500:],
        }
        print(
            f"style autofix: {gate} -> {style.fix_command()} ({touched or 'no change'})",
            flush=True,
        )
        return True

    def _autofix_style(self, gates: dict[str, int], transcript: str) -> bool:
        """Run the project's formatter when the only red gate is style (016).

        A Prettier/ESLint slip is mechanical: the harness fixes it and the gate
        is re-checked, instead of spending a coder round (and a local model)
        on a wrap. Only a *sole* style failure qualifies — with a red type
        check or a red test the code is wrong, not badly formatted.
        """
        from swarm import style
        from swarm.evidence import split_tails

        if not style.enabled():
            return False
        tails: dict[str, str] = {}
        for block in split_tails(transcript):
            head, _, body = block.partition("\n")
            command = head.removeprefix("$ ").strip()
            if command:
                tails[command] = body
        gate = style.style_gate(gates, tails)
        if not gate:
            return False
        return self._apply_formatter(gate)

    def _run_self_check(self) -> dict[str, Any]:
        """Run the project's static checks (types, lint) before QA (017).

        The checks are the harness's own, run under their own agent role: the
        records never count as QA evidence, so this can never make a run
        green — it only gives the coder the error before QA does.
        """
        from swarm import selfcheck, style
        from swarm.tools_guarded import ShellTool, run_delta

        if not selfcheck.enabled():
            return {}
        commands = selfcheck.commands(gate_commands())
        if not commands:
            return {}

        def _run() -> tuple[dict[str, int], dict[str, str]]:
            runner = ShellTool(agent_role="harness-selfcheck")
            codes: dict[str, int] = {}
            tails: dict[str, str] = {}
            for command in commands:
                out = runner._run(command)
                code = 99
                try:
                    code = int(out.split("exit=")[1].split()[0])
                except (IndexError, ValueError):
                    code = 99
                codes[command] = code
                _, _, body = out.partition("\n")
                tails[command] = body
            return codes, tails

        codes, tails = _run()
        # Formatting-only failures are mechanical: the harness formats, the
        # coder is never asked to.
        if style.enabled() and style.style_failures(codes, tails):
            self._apply_formatter(", ".join(style.style_failures(codes, tails)))
            codes, tails = _run()
        red = sorted(command for command, code in codes.items() if int(code) != 0)
        changed = self._in_scope_paths(run_delta(self._baseline))
        return {
            "commands": list(commands),
            "exit": codes,
            "red": red,
            "report": selfcheck.render_report(codes, tails, changed),
        }

    def _self_check_phase(self, task: Any, kick: Any) -> None:
        """Static checks before QA: the coder passes on type-clean work (017).

        007-T9 (2026-11-11) spent three QA rounds and two coder rounds on one
        type error the checker had already named. The coder now gets the
        evidence while the work is still his.
        """
        from swarm.crew import MAX_SELF_CHECK_ROUNDS, build_selfcheck_crew

        for attempt in range(MAX_SELF_CHECK_ROUNDS + 1):
            result = self._run_self_check()
            if not result:
                return
            self.state.self_check = {
                "commands": result["commands"],
                "exit": result["exit"],
                "red": result["red"],
                "rounds": attempt,
                "report": result["report"][-2000:],
            }
            if not result["red"]:
                print("self-check: static checks green", flush=True)
                return
            if attempt >= MAX_SELF_CHECK_ROUNDS:
                print(
                    f"self-check: still red after {MAX_SELF_CHECK_ROUNDS} fix round(s): "
                    + ", ".join(result["red"]),
                    flush=True,
                )
                return
            report = result["report"]
            try:
                kick(
                    lambda report=report: build_selfcheck_crew(
                        self._spec_dir, task, report
                    ),
                    f"coder:selfcheck{attempt + 1}",
                )
            except SystemExit as e:
                self.state.result = str(e)[:4000]
                return

    def _verify_phase(self, task: Any, kick: Any) -> bool:
        """Scenario verification between the 017 self-check and QA (019).

        The gates only test the code that exists, so a *missing* piece (an
        endpoint never mounted, a component never wired) passes them. This runs
        one read-only crew over the whole scenario — brief, referenced ACs,
        plan lines, the full content of every delta file and an import graph —
        and asks whether the implementation does what the brief says.

        On `BLOCKED` the verifier emits a correction plan in the planner's own
        `STEP n:` format; those steps run through `build_step_crew` (role
        `coder:verify<n>`) and the scenario is verified again, bounded by
        `MAX_VERIFY_ROUNDS`. A non-converging verifier sets `blocked` and
        returns False, so the run ends `verifier_blocked` instead of looping.
        QA still owns the gates: this phase can never make a run green.
        """
        from swarm import verify
        from swarm.crew import MAX_STEPS, build_step_crew, build_verify_crew
        from swarm.tools_guarded import run_delta

        self.state.verifier = {}
        if not verify.enabled():
            return True

        record: dict[str, Any] = {
            "verdict": "",
            "rounds": 0,
            "findings": [],
            "plan": [],
            "files": [],
            "skipped": [],
            "model": verify.model_name(),
            "delta": "",
            "blocked": False,
            "corrections": False,
        }
        self.state.verifier = record
        for round_no in range(verify.MAX_VERIFY_ROUNDS):
            changed = self._in_scope_paths(run_delta(self._baseline))
            record["delta"] = self._delta_signature()
            context = verify.scenario_context(REPO_ROOT, self._spec_dir, task, changed)
            record["files"] = list(context.get("files") or [])
            record["skipped"] = list(context.get("skipped") or [])
            context_text = verify.render_context(context)
            try:
                crew, out = kick(
                    lambda context_text=context_text: build_verify_crew(
                        self._spec_dir, task, context_text
                    ),
                    f"verifier:{round_no + 1}",
                )
            except SystemExit as e:
                # Advisory phase: a transport failure must not throw away a run
                # that QA can still decide. Recorded, then the loop continues.
                record["verdict"] = "error"
                record["note"] = str(e)[:500]
                print(f"verifier unavailable: {e}"[:500], flush=True)
                return True
            model = ""
            if crew is not None:
                agents = getattr(crew, "agents", None) or []
                if agents:
                    model = str(getattr(getattr(agents[0], "llm", None), "model", "") or "")
            if model:
                record["model"] = model
            verdict, findings = verify.parse_verdict(out)
            record["verdict"] = verdict
            record["rounds"] = round_no + 1
            if findings:
                record["findings"] = findings
            record["output"] = str(out)[-2000:]
            history = record.setdefault("history", [])
            history.append(
                {"round": round_no + 1, "verdict": verdict, "findings": findings, "plan": []}
            )
            if verdict != "blocked":
                record["blocked"] = False
                print(
                    f"verifier: {verdict.upper()} after round {round_no + 1}",
                    flush=True,
                )
                return True
            plan = verify.parse_plan(out)[:MAX_STEPS]
            record["plan"] = plan
            history[-1]["plan"] = plan
            if not findings:
                # An ungrounded block is not a loop: with nothing the coder can
                # act on, the honest answer is that the scenario was not shown
                # to be broken (019 risk note). Record it, keep the run moving.
                record["verdict"] = "pass"
                record["blocked"] = False
                print("verifier: blocked without a finding (treated as pass)", flush=True)
                return True
            if not plan:
                record["blocked"] = True
                print("verifier: blocked with no correction plan → needs a human", flush=True)
                return False
            print(
                f"verifier: BLOCKED round {round_no + 1}/{verify.MAX_VERIFY_ROUNDS} — "
                f"{len(findings)} finding(s), {len(plan)} correction step(s)",
                flush=True,
            )
            if round_no + 1 >= verify.MAX_VERIFY_ROUNDS:
                record["blocked"] = True
                print("verifier: still blocked after the round budget → needs a human", flush=True)
                return False
            report = verify.render_report(context, findings, plan)
            record["report"] = report[-4000:]
            for idx, step in enumerate(plan, 1):
                try:
                    kick(
                        lambda step=step, idx=idx, plan=plan: build_step_crew(
                            self._spec_dir, task, step, idx, len(plan)
                        ),
                        f"coder:verify{round_no + 1}",
                    )
                except SystemExit as e:
                    record["blocked"] = True
                    record["note"] = f"correction step failed: {e}"[:500]
                    print(f"verifier correction failed: {e}"[:500], flush=True)
                    return False
        record["blocked"] = True
        return False

    def _reverify_if_stale(self, task: Any, kick: Any) -> bool:
        """Re-run the scenario verifier when a later round changed the delta (019).

        Sets `state.verifier["corrections"]` when correction steps edited the
        tree, which makes QA's gate evidence stale: the caller re-runs QA.
        Returns False only when the scenario is verifiably still broken.
        """
        record = self.state.verifier
        if record.get("blocked") or not record.get("delta"):
            return True
        if record.get("delta") == self._delta_signature():
            # Fresh: nothing changed since the verifier read the tree, and a
            # previous correction pass has already been re-checked by its caller.
            record["corrections"] = False
            return True
        before = self._delta_signature()
        if not self._verify_phase(task, kick):
            return False
        corrected = self._delta_signature() != before
        self.state.verifier["delta"] = self._delta_signature()
        self.state.verifier["corrections"] = corrected
        return True

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
            resolver=self._resolve_conflict,
        )

    def _stash_unrelated(self, task: Any) -> None:
        """015 AC-10: park unrelated dirty in-scope files so they never block a run."""
        if os.getenv("SWARM_STASH_UNRELATED", "1") != "1":
            return
        try:
            owned = set(self._task_owned_dirty(task))
        except Exception:
            owned = set()
        candidates = [p for p in self._in_scope_dirty() if p not in owned]
        if not candidates:
            return
        rc, out = _git(
            ["stash", "push", "-u", "-m", f"swarm-{self.run_dir.name}", "--", *candidates]
        )
        if rc != 0:
            print(f"stash skipped: {out.strip()[:200]}", flush=True)
            return
        self._stash_ref = f"swarm-{self.run_dir.name}"
        # Remember the exact stash commit: a bare `stash pop` takes whatever is
        # on top, which may be a stash a human (or another run) pushed meanwhile.
        rc, sha = _git(["rev-parse", "refs/stash"])
        self._stash_sha = sha.strip().splitlines()[-1] if rc == 0 and sha.strip() else ""
        self.state.stashed = candidates
        print(f"stashed {len(candidates)} unrelated path(s): {candidates}", flush=True)

    def _unmerged_paths(self) -> list[str]:
        return _unmerged_paths()

    def _drop_stash(self, sha: str) -> None:
        """Drop our own stash entry, wherever it sits in the stack."""
        if not sha:
            return
        rc, listing = _git(["stash", "list", "--format=%gd %H"])
        if rc != 0:
            return
        for line in listing.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == sha:
                _git(["stash", "drop", parts[0]])
                return

    def _resolve_stash_conflict(
        self, conflicts: list[str], *, stash: str = ""
    ) -> tuple[bool, str]:
        """Resolve a conflicted stash restore; accepted only if it is provably safe.

        The parked work is wanted (the user's rule), so a crew merges it into the
        current tree. Acceptance is deterministic: no markers, no edits outside
        the conflicted files, every gate green. Anything else falls back to the
        current worktree, so the queue never inherits a broken or half-merged tree.
        """
        if os.getenv("SWARM_CONFLICT_CREW", "1") != "1":
            return False, "stash resolver disabled (SWARM_CONFLICT_CREW=0)"
        from swarm.crew import build_stash_crew

        before = (self.state.prompt_tokens, self.state.completion_tokens)
        dirty_before = _dirty_paths()
        try:
            crew = build_stash_crew(
                self.state.spec_dir,
                self.state.task_id,
                conflicts,
                stash=stash,
                detail=self.state.transcript[-1500:],
            )
            out = crew.kickoff()
        except Exception as e:
            return False, f"stash resolver failed: {e}"[:300]
        self._record_usage(crew, out, role="conflict", before=before)
        leftover = conflict_markers(conflicts)
        if leftover:
            return False, f"conflict markers left in {', '.join(leftover)}"
        extra = sorted(_dirty_paths() - dirty_before - set(conflicts))
        if extra:
            for path in extra:
                _git(["checkout", "HEAD", "--", path])
            return False, f"resolver touched files outside the conflict: {', '.join(extra[:4])}"
        gates = _run_gate_commands()
        failed = [f"{cmd} exit={code}" for cmd, code, _ in gates if code != 0]
        if failed:
            return False, f"resolved tree failed gates: {'; '.join(failed)}"
        return True, f"resolver re-applied the parked work; gates: {len(gates)}/{len(gates)} green"

    def _restore_stash(self, *, allow_crew: bool = True) -> None:
        if not self._stash_ref:
            return
        ref, self._stash_ref = self._stash_ref, ""
        sha, self._stash_sha = self._stash_sha, ""
        # Apply *our* stash, never `stash pop`: LIFO would take a stash pushed
        # by someone else during the run (it happened on 2026-11-10 and wiped a
        # recovery stash).
        rc, out = _git(["stash", "apply", sha or "stash@{0}"])
        if rc == 0:
            self._drop_stash(sha)
            return
        # A conflicted pop leaves `UU` index stages *and* keeps the stash. 014
        # broke exactly this way: T8's pop conflicted on App.svelte, the markers
        # stayed in the tree, and the next three runs gated/edited around them.
        conflicts = self._unmerged_paths()
        self.state.stash_conflict = conflicts or [ref]
        resolved = False
        note = "apply failed without unmerged paths; kept the stash"
        if conflicts:
            resolved, note = (
                self._resolve_stash_conflict(conflicts, stash=ref)
                if allow_crew
                else (False, "crew skipped during cleanup; current worktree kept")
            )
        # A rejected attempt must not leave markers or `UU`: fall back to the
        # current worktree. An accepted one gets its stages cleared so the parked
        # work stays an ordinary unstaged change.
        for path in conflicts:
            if not resolved:
                _git(["checkout", "--ours", "--", path])
            _git(["add", "--", path])
            _git(["reset", "-q", "HEAD", "--", path])
        archived = ""
        if conflicts and sha and os.getenv("SWARM_ARCHIVE_STASHES", "1") == "1":
            try:
                from swarm.stashes import archive, list_stashes

                entry = next((e for e in list_stashes(REPO_ROOT) if e["sha"] == sha), None)
                if entry is not None:
                    archived = archive(
                        REPO_ROOT,
                        entry,
                        run_id=self.run_dir.name,
                        reason="resolved" if resolved else "conflict",
                    )["ref"]
            except (RuntimeError, OSError, KeyError):
                archived = ""
        elif resolved:
            # Archiving is off but the content now lives in the worktree: a
            # successful restore is supposed to consume its stash entry.
            self._drop_stash(sha)
        self.state.stash_conflict_ref = archived
        if not conflicts:
            self.state.stash_conflict_resolution = "kept"
        elif resolved:
            self.state.stash_conflict_resolution = "crew"
        else:
            self.state.stash_conflict_resolution = "ours"
        self.state.stash_conflict_note = note
        if resolved:
            print(
                f"STASH RESTORE CONFLICT ({ref}) RESOLVED: {note}; "
                f"parked work archived as {archived or 'an unarchived stash'}",
                flush=True,
            )
        else:
            print(
                f"STASH RESTORE CONFLICT ({ref}): {', '.join(conflicts) or out.strip()[:200]}; "
                f"{note}; kept the current worktree plus "
                + (archived or "an unarchived stash for manual recovery"),
                flush=True,
            )

    def _resolve_conflict(self, conflicts: list[str]) -> tuple[bool, str]:
        """016: one conflict crew; accepted only if markers are gone and gates pass."""
        if os.getenv("SWARM_CONFLICT_CREW", "1") != "1":
            return False, "conflict crew disabled (SWARM_CONFLICT_CREW=0)"
        from swarm.crew import build_conflict_crew

        before = (self.state.prompt_tokens, self.state.completion_tokens)
        try:
            crew = build_conflict_crew(
                self.state.spec_dir,
                self.state.task_id,
                conflicts,
                detail=self.state.transcript[-1500:],
            )
            out = crew.kickoff()
        except Exception as e:
            return False, f"conflict crew failed: {e}"[:300]
        self._record_usage(crew, out, role="conflict", before=before)
        # The merge is only those files: an extra edit is scope creep the task's
        # QA never saw, so reject instead of committing it later.
        _rc, out_diff = _git(["diff", "--name-only"])
        extra = [
            p.strip()
            for p in out_diff.splitlines()
            if p.strip() and p.strip() not in conflicts
        ]
        if extra:
            return False, f"crew touched files outside the conflict: {', '.join(extra[:4])}"
        leftover = conflict_markers(conflicts)
        if leftover:
            return False, f"conflict markers left in {', '.join(leftover)}"
        gates = _run_gate_commands()
        failed = [f"{cmd} exit={code}" for cmd, code, _ in gates if code != 0]
        if failed:
            return False, f"conflict merge failed gates: {'; '.join(failed)}"
        return True, f"crew resolved; gates: {len(gates)}/{len(gates)} green"

    def _revert_out_of_scope(self, changed: list[str]) -> list[str]:
        """015 AC-10: undo out-of-scope writes instead of stopping the queue."""
        if os.getenv("SWARM_REVERT_OUT_OF_SCOPE", "1") != "1":
            return []
        from swarm.tools_guarded import scope_violations

        bad = scope_violations(changed, _resolve_scope())
        reverted: list[str] = []
        for path in bad:
            target = REPO_ROOT / path
            listed = _git(["ls-files", "--error-unmatch", path])[0] == 0
            if listed:
                rc, _ = _git(["checkout", "--", path])
            else:
                try:
                    target.unlink()
                    rc = 0
                except OSError:
                    rc = 1
            if rc == 0:
                reverted.append(path)
        if reverted:
            print(f"reverted out-of-scope writes: {reverted}", flush=True)
        return reverted

    def _in_scope_dirty(self) -> list[str]:
        from swarm.tools_guarded import _git_changed

        return self._in_scope_paths(_git_changed())

    def _in_scope_paths(self, paths: list[str]) -> list[str]:
        from swarm.tools_guarded import is_secret_path, scope_violations

        scope = _resolve_scope()
        return [
            path
            for path in paths
            if not is_secret_path(path) and path not in scope_violations([path], scope)
        ]

    def _task_owned_dirty(self, task: Any) -> dict[str, str]:
        """Dirty in-scope paths owned by prior attempts of this same task.

        Returns `{path: prior_run_name}`. Only paths from non-green attempts are
        considered, so already-committed work is never re-staged.
        """
        dirty = set(self._in_scope_dirty())
        if not dirty:
            return {}
        owned: dict[str, str] = {}
        runs = REPO_ROOT / "swarm" / "runs"
        if not runs.is_dir():
            return {}
        dirs = sorted(
            (p for p in runs.iterdir() if p.is_dir() and p.name[:1].isdigit()),
            reverse=True,
        )[:10]
        for d in dirs:
            if d.resolve() == self.run_dir.resolve():
                continue
            rec: dict[str, Any] = {}
            for fname in ("run.json", "meta.json"):
                try:
                    rec = json.loads((d / fname).read_text())
                    break
                except (OSError, json.JSONDecodeError):
                    rec = {}
            if not same_spec(str(rec.get("spec")), self.state.spec_dir) or str(
                rec.get("task")
            ) != str(task.id):
                continue
            if _run_status(d) == "green":
                continue
            candidates: set[str] = set(rec.get("changed_files") or [])
            try:
                prog = json.loads((d / "progress.json").read_text())
                candidates.update((prog.get("delta_hashes") or {}).keys())
            except (OSError, json.JSONDecodeError):
                pass
            for path in candidates:
                if path in dirty and path not in owned:
                    owned[path] = d.name
                elif path.endswith("/") or not (REPO_ROOT / path).exists():
                    # Older checkpoints stored an untracked directory; expand it.
                    for child in dirty:
                        if child.startswith(path) and child not in owned:
                            owned[child] = d.name
            if set(owned) == dirty:
                break
            # A killed run whose steps all completed owns whatever it left dirty:
            # that is its own QA-pending work, not unrelated human edits.
            try:
                prog = json.loads((d / "progress.json").read_text())
            except (OSError, json.JSONDecodeError):
                prog = {}
            steps = prog.get("steps") or []
            if steps and int(prog.get("completed") or 0) >= len(steps):
                return {path: d.name for path in sorted(dirty)}
        return owned

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
        from swarm.llms import reviewer_llm, verdict_fallback_llm

        prompt = (
            f"Task: {task.id} — {task.brief}\n"
            f"Gate transcript (tail):\n{transcript[-1500:]}\n\n"
            "The deterministic gates are shown above. Reply with exactly one line:\n"
            "VERDICT: PASS\n"
            "or\n"
            "VERDICT: BLOCKED\n"
            "No code, no explanation, no repeating the work summary."
        )
        for factory in (reviewer_llm, verdict_fallback_llm):
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

        delta = self._in_scope_paths(run_delta(self._baseline))
        payload = {
            "run_id": self.run_dir.name,
            "spec": self.state.spec_dir,
            "task": self.state.task_id,
            "plan_hash": plan_hash,
            "steps": list(steps),
            "completed": completed,
            "step_outputs": list(step_outputs),
            "delta_hashes": hash_paths(delta),
            # Live view for a tailed dashboard: the run.json is only written at
            # the end, so without this the model list stays the static env list
            # even after a role fell back to local Ollama.
            "models": _role_model_rows(),
            "fallback_roles": _fallback_role_names(),
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
        # 015 AC-7: any non-green attempt can be resumed; green is committed already.
        if _run_status(prev) == "green":
            return None, ""
        try:
            max_age = int(os.getenv("SWARM_RESUME_MAX_AGE_SECONDS", "86400") or 86400)
        except ValueError:
            max_age = 86400
        plan_hash = hashlib.sha256(plan_text.encode()).hexdigest()
        kwargs = {
            "spec_dir": self.state.spec_dir,
            "task_id": str(task.id),
            "plan_hash": plan_hash,
            "steps": steps,
            "max_age": max_age,
            "path_filter": lambda path: bool(self._in_scope_paths([path])),
        }
        prog, note = load_checkpoint(prev, **kwargs)  # type: ignore[arg-type]
        if prog is None:
            # 015 AC-7: a worktree drift no longer throws away every finished step.
            lenient, lenient_note = load_checkpoint(prev, lenient=True, **kwargs)  # type: ignore[arg-type]
            if lenient is None or not lenient.get("drift"):
                return None, f"checkpoint in {prev.name} rejected: {note or lenient_note}"
            completed = int(lenient.get("completed") or 0)
            resume_at = max(0, completed - 1)
            lenient["completed"] = resume_at
            lenient["step_outputs"] = list(lenient.get("step_outputs") or [])[:resume_at]
            return lenient, f"worktree drift; redoing step {resume_at + 1} only"
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

        # 016 follow-up: a stash left by an earlier run is preserved as a ref and
        # removed from the stack, so it can never be restored onto a wrong base.
        if os.getenv("SWARM_ARCHIVE_STASHES", "1") == "1":
            from swarm.stashes import sweep

            archived = sweep(REPO_ROOT, run_id=self.run_dir.name)
            if archived:
                self.state.orphan_stashes = archived
                print(
                    f"archived {len(archived)} orphan stash(es): "
                    + ", ".join(r["ref"] for r in archived),
                    flush=True,
                )

        task = load_spec_tasks(REPO_ROOT, self._spec_dir, self._task_id)[1][0]
        self.listener = SwarmListener(self.run_dir)  # always trace, TUI or headless
        # 015: ShellTool evidence sink + step routing.
        os.environ["SWARM_RUN_DIR"] = str(self.run_dir)
        self._stash_unrelated(task)
        # Baseline AFTER stashing: parked work must not look like this run's delta.
        from swarm.tools_guarded import snapshot_worktree

        self._baseline = snapshot_worktree()
        from swarm.evidence import report_text
        from swarm.routing import classify_step, routing_enabled
        cache = plan_cache_path(self._spec_dir, task.id)
        source_hash = plan_source_hash(self._spec_dir)

        def _kickoff(
            build: Any, *, role: str = "", step: Any = None, guard_budget: bool = True
        ) -> tuple[Any, str]:
            """Run a fresh crew with quota fallback, backoff, and typed failures.

            015 AC-6: usage is attributed to `role`/`step`. 015 AC-8: identical
            failures are not retried on the same model, and config errors are
            terminal instead of looping.
            """
            from swarm.evidence import signature
            from swarm.llms import activate_fallbacks, fallbacks_active
            from swarm.retry import backoff_delay, classify_provider_error

            last_err: Exception | None = None
            switch_key = _fallback_key(role)
            switched = fallbacks_active(switch_key)
            prompt_before = self.state.prompt_tokens
            completion_before = self.state.completion_tokens
            for attempt in (1, 2, 3):
                try:
                    # 015 AC-6: never abort between a green verdict and its commit —
                    # budgets are checked before spending, not after a result.
                    if guard_budget:
                        self._check_budget()
                    crew = build()
                    out = crew.kickoff()
                except _BudgetExhausted:
                    # A budget stop is terminal: retrying it cannot help, and
                    # swallowing it here turned "out of money" into
                    # `reviewer_no_verdict` (007-T5, 40 minutes of paid work).
                    raise
                except Exception as e:
                    last_err = e
                    if _is_quota_error(e):
                        if not switched:
                            switched = True
                            # A quota wall is provider-wide: move every role.
                            activate_fallbacks()
                            print("quota hit → retrying with fallback models", flush=True)
                            continue
                        raise _QuotaExhausted(f"free-models-per-day quota hit: {e}"[:500]) from e
                    kind = classify_provider_error(e)
                    if kind == "config":
                        raise _ConfigError(
                            f"config error in {role or 'crew'}: {type(e).__name__}: {e}"[:800]
                        ) from e
                    if kind == "retryable" and attempt < 3:
                        key = (role or "crew", signature(str(step or role or "crew"), str(e)))
                        text = f"{type(e).__name__}: {e}".lower()
                        flaky = "connect" in text or "timed out" in text
                        if key in self._failure_sigs:
                            # Second identical failure: stop retrying this model.
                            if flaky and not switched:
                                switched = True
                                # Only this role: QA must keep its local reviewer.
                                activate_fallbacks(switch_key)
                                print(
                                    "llm connection failure ×2 → retrying on fallback models",
                                    flush=True,
                                )
                                time.sleep(backoff_delay(attempt))
                                continue
                            break
                        self._failure_sigs.add(key)
                        # A single transport blip is worth one retry on the same
                        # model (calls normally take 1-7s); only then fall back.
                        time.sleep(backoff_delay(attempt))
                        continue
                    break
                else:
                    self._record_usage(
                        crew,
                        out,
                        role=role,
                        step=step,
                        before=(prompt_before, completion_before),
                    )
                    return crew, str(out)[:8000]
            raise SystemExit(f"crew failed after retries, trace in {self.run_dir}/run.json") from last_err

        def _review(task: Any, work_summary: str, *, role: str = "qa") -> bool:
            """Run QA; never let its transport failure become a run-level crew_error.

            If QA cannot answer, the harness still records gate evidence (with its
            fallback runner) and one free-model verdict attempt, so a flaky local
            reviewer parks the task as needs_human with real evidence instead of
            throwing away the run (007-T1 ended `crew_error` with empty gates).
            """
            try:
                _, review_out = _kickoff(
                    lambda work_summary=work_summary: build_review_crew(
                        self._spec_dir, task, work_summary
                    ),
                    role=role,
                    # QA is local/free and the work is already paid for: a spent
                    # task budget must not block the verification that decides it.
                    guard_budget=False,
                )
            except SystemExit as e:
                self.state.result = f"QA crew failed: {e}"[:4000]
                self.state.evidence_note = "QA crew failed; gates will be recorded by the harness"
                print("qa crew failed → harness gate evidence + free verdict", flush=True)
                return False
            self._set_review(review_out)
            return True

        def _verify_kick(build: Any, role: str) -> Any:
            """Verifier crews are not steps and never run a gate (019)."""
            return _kickoff(build, role=role, step="verify")

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
                self.state.recovery = "checkpoint-last-step" if recovery_note else "checkpoint"
                self.state.recovery_note = recovery_note
                print(
                    f"resuming {task.id} after step {resume_from}/{len(steps)}"
                    + (f" ({recovery_note})" if recovery_note else ""),
                    flush=True,
                )
            elif recovery_note:
                self.state.recovery = "restart"
                self.state.recovery_note = recovery_note
                print(f"restarting {task.id}: {recovery_note}", flush=True)
            gates: dict[str, int] = {}
            transcript = ""
            missing: list[str] = []
            work_summary = ""
            self._task_tokens_start = self.state.total_tokens
            cost_at_task_start = self._run_cost()
            self._task_cost_start = cost_at_task_start if cost_at_task_start is not None else 0.0
            self._task_started = time.monotonic()
            # Dev phase: micro-steps → QA review → QA-driven fix rounds (015 AC-4),
            # up to DEV_ATTEMPTS; then senior escalation, then human.
            # 015 AC-7: step outputs survive a dev retry — a second attempt must
            # not re-execute work the first attempt already finished.
            step_outs: list[str] = list(checkpoint_outputs)
            while True:
                self.state.dev_attempts += 1
                self._write_progress(plan_hash, steps, len(step_outs), step_outs)
                for i, step in enumerate(steps, 1):
                    if i <= len(step_outs):
                        continue
                    route = classify_step(
                        step,
                        repo_root=REPO_ROOT,
                        attempt=1,
                        task_brief=task.brief,
                        enabled=routing_enabled(),
                    )
                    step_out = ""
                    last_err: BaseException | None = None
                    model_kind = route.kind
                    for attempt in range(1, STEP_ATTEMPTS + 1):
                        # 015 AC-5: a trivial step that fails is retried paid.
                        model_kind = route.kind if attempt == 1 else "paid"
                        try:
                            _, step_out = _kickoff(
                                lambda step=step, i=i, model_kind=model_kind: build_step_crew(
                                    self._spec_dir, task, step, i, len(steps), model_kind=model_kind
                                ),
                                role=f"coder:step{i}",
                                step=i,
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
                        try:
                            _, step_out = _kickoff(
                                lambda step=step, i=i, last_err=last_err: build_senior_step_crew(
                                    self._spec_dir, task, step, i, len(steps), str(last_err)
                                ),
                                role=f"senior:step{i}",
                                step=i,
                            )
                        except SystemExit as e:
                            # Keep the task alive: gates + QA decide, not one failed call.
                            self.state.result = f"senior rescue failed: {e}"[:4000]
                            step_out = f"(senior rescue failed: {e})"[:1000]
                        model_kind = "senior"
                    self.state.steps_meta.append(
                        {
                            "index": i,
                            "model": model_kind,
                            "kind": route.kind,
                            "routing_reason": route.reason,
                        }
                    )
                    step_outs.append(f"--- step {i}/{len(steps)} ---\n{step_out}")
                    self._write_progress(plan_hash, steps, i, step_outs)
                # 017: the coder checks types/lint before the work is passed on.
                # QA is still the only gate executor; this is early feedback, not
                # a gate, and it can never make a run green.
                self._self_check_phase(
                    task,
                    lambda build, role: _kickoff(build, role=role, step="selfcheck"),
                )
                # 019: does the implemented scenario do what the brief says? The
                # gates test what exists, so a missing endpoint or an unwired
                # component passes them; this phase reads the whole scenario.
                # Read-only and advisory: QA still owns the gates and green.
                if not self._verify_phase(
                    task,
                    _verify_kick,
                ):
                    break
                work_summary = "\n".join(step_outs)
                # 015 AC-2/AC-3: QA runs the gates; its recorded executions are
                # the evidence green is built from.
                reviewed = _review(task, work_summary)
                self.state.result = f"{work_summary}\n--- review ---\n{self.state.review_text}"[:8000]
                changed = run_delta(self._baseline)
                gates, transcript, missing = self._gates_or_evidence(changed)
                self._maybe_repair_verdict(task, gates, transcript)
                if not reviewed and self.state.review_verdict == "unknown":
                    break
                if missing and self.state.review_verdict == "pass":
                    # QA said PASS without running a gate: ask once more. Never
                    # accept a verdict that its own evidence does not support.
                    _review(task, work_summary, role="qa:missing-gates")
                    changed = run_delta(self._baseline)
                    gates, transcript, missing = self._gates_or_evidence(changed)
                base_rounds = self.state.fix_rounds
                while (
                    not _gates_green(gates) or self.state.review_verdict == "blocked"
                ) and self.state.fix_rounds - base_rounds < MAX_FIX_ROUNDS:
                    self.state.fix_rounds += 1
                    round_start = self._delta_signature()
                    self.state.transcript = transcript
                    report = self._qa_report(gates, transcript, changed, missing)
                    self.state.qa_report = report
                    report_block = report_text(report)
                    qa_note = self.state.review_text
                    try:
                        _kickoff(
                            lambda report_block=report_block, qa_note=qa_note: build_fix_crew(
                                self._spec_dir, task, report_block, qa_note
                            ),
                            role=f"coder:fix{self.state.fix_rounds}",
                            step=f"fix{self.state.fix_rounds}",
                        )
                    except SystemExit as e:
                        self.state.result = str(e)[:4000]
                        break
                    changed = run_delta(self._baseline)
                    # Same round continues with QA re-verification (it runs the gates).
                    reviewed = _review(task, work_summary)
                    gates, transcript, missing = self._gates_or_evidence(changed)
                    self._maybe_repair_verdict(task, gates, transcript)
                    if not reviewed and self.state.review_verdict == "unknown":
                        break
                    if self._delta_signature() == round_start:
                        # The fix round changed nothing (007-T9: five rounds of
                        # re-reading the same file). Another identical round
                        # cannot help: stop and let a human/senior look.
                        self.state.no_progress = True
                        print(
                            "no progress: fix round changed no files",
                            flush=True,
                        )
                        break
                    if _gates_green(gates) and self.state.review_verdict == "pass":
                        break
                    if _gates_green(gates) and self.state.review_verdict == "blocked":
                        if self._delta_signature() == round_start:
                            self.state.no_progress = True
                            print(
                                "no progress: gates green, QA still blocks, diff unchanged",
                                flush=True,
                            )
                            break
                        if not block_is_grounded(self.state.review_text):
                            self.state.ungrounded_block = True
                            print(
                                "ungrounded block: gates green and QA cited nothing checkable",
                                flush=True,
                            )
                            break
                if _gates_green(gates) and self.state.review_verdict == "pass":
                    # 019: QA has passed, so check the delta QA saw against the
                    # one the verifier last read. Fixture: a QA fix round changed
                    # it, so the scenario is stale until verified again.
                    if not self._reverify_if_stale(task, _verify_kick):
                        break
                    if self.state.verifier.get("corrections"):
                        # Correction steps edited the tree: QA's evidence is stale.
                        changed = run_delta(self._baseline)
                        reviewed = _review(task, work_summary)
                        gates, transcript, missing = self._gates_or_evidence(changed)
                        self._maybe_repair_verdict(task, gates, transcript)
                if _gates_green(gates) or self.state.dev_attempts >= DEV_ATTEMPTS:
                    break
            if not _gates_green(gates) and not self.state.verifier.get("blocked"):
                # Senior escalation: up to SENIOR_ATTEMPTS passes, QA re-verifies
                # each round exactly like a normal fix round.
                while (
                    not _gates_green(gates)
                    and self.state.senior_rounds < SENIOR_ATTEMPTS
                ):
                    self.state.senior_used = True
                    self.state.senior_rounds += 1
                    self.state.transcript = transcript
                    report = self._qa_report(gates, transcript, changed, missing)
                    self.state.qa_report = report
                    report_block = report_text(report)
                    qa_note = self.state.review_text
                    try:
                        _kickoff(
                            lambda report_block=report_block, qa_note=qa_note: build_senior_crew(
                                self._spec_dir, task, report_block, qa_note
                            ),
                            role=f"senior:fix{self.state.senior_rounds}",
                            step=f"senior{self.state.senior_rounds}",
                        )
                    except SystemExit as e:
                        self.state.result = str(e)[:4000]
                        break
                    changed = run_delta(self._baseline)
                    reviewed = _review(task, work_summary)
                    gates, transcript, missing = self._gates_or_evidence(changed)
                    self._maybe_repair_verdict(task, gates, transcript)
                    if not reviewed and self.state.review_verdict == "unknown":
                        break
            if (
                _gates_green(gates)
                and self.state.review_verdict == "pass"
                and self._reverify_if_stale(task, _verify_kick)
                and self.state.verifier.get("corrections")
            ):
                # 019: the senior chase above may have changed the delta after the
                # verifier last read it. Re-read the scenario, and let QA re-decide
                # if a correction step edited it.
                changed = run_delta(self._baseline)
                reviewed = _review(task, work_summary)
                gates, transcript, missing = self._gates_or_evidence(changed)
                self._maybe_repair_verdict(task, gates, transcript)
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
        except _ConfigError as e:
            # 015 AC-8: misconfiguration is terminal, never retried.
            self.state.result = str(e)[:4000]
            self.state.status = "config_error"
            print(f"CONFIG ERROR: {e}"[:1500], flush=True)
            self.save_run("config_error")
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
        elif self.state.verifier.get("blocked"):
            # 019: the scenario was verifiably not implemented; QA's gates cannot
            # turn that into green, no matter how many of them exit 0.
            self.state.status = "needs_human"
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
        owned = self._task_owned_dirty(task) if task else {}
        if owned:
            changed = sorted(set(changed) | set(owned))
        reverted = self._revert_out_of_scope(changed)
        if reverted:
            changed = [p for p in changed if p not in reverted]
            self.state.out_of_scope_reverted = reverted
        in_scope = in_scope_changes(changed, scope)
        # 015 AC-2: re-verify QA evidence at save time. A file edited after QA's
        # last gate run (or a gate QA skipped) is never green.
        evidence_missing: list[str] = []
        if status == "green" and os.getenv("SWARM_TRUST_QA_EVIDENCE", "1") != "0":
            gates_now, transcript_now, evidence_missing = self._gate_evidence(
                changed, agents=getattr(self, "_evidence_agents", None)
            )
            self.state.gates = gates_now
            self.state.transcript = transcript_now
            if evidence_missing or not _gates_green(gates_now):
                status = "needs_human"
                self.state.evidence_note = (
                    "QA evidence is stale or incomplete: "
                    + (", ".join(evidence_missing) if evidence_missing else "gates not green at save")
                )
        approved = approval_granted(self.state.spec_dir, self.state.task_id, self.run_dir)
        self.state.changed_files = changed
        self.state.approved = approved
        in_scope_hashes = hash_paths(in_scope)
        head_rc, head_out = _git(["rev-parse", "HEAD"])
        head = head_out.strip().splitlines()[-1] if head_rc == 0 and head_out.strip() else ""
        self.state.finished_at = dt.datetime.now().isoformat(timespec="seconds")
        usage = self._usage_snapshot()
        cost = usage["cost_usd"]

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
            "recovered_paths": dict(owned),
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
                "max_cost_per_task": self._max_cost_task,
                "max_seconds_per_task": self._max_seconds_task,
                "local_coder": bool(getattr(self, "_local_coder", lambda: False)()),
                "free_local_run": bool(
                    getattr(self, "_free_local_run", lambda: False)()
                ),
            },
            "budget_note": self.state.budget_note,
            "done": {"task_hash": task_hash_value, "spec_hash": spec_hash_value, "recorded": False},
            "resumed_from_step": self.state.resumed_from_step,
            "recovery": self.state.recovery,
            "recovery_note": self.state.recovery_note,
            "qa_report": self.state.qa_report,
            "steps": self.state.steps_meta,
            "skipped_ac": self.state.skipped_ac,
            "stashed": self.state.stashed,
            "stash_conflict": self.state.stash_conflict,
            "stash_conflict_ref": self.state.stash_conflict_ref,
            "stash_conflict_resolution": self.state.stash_conflict_resolution,
            "stash_conflict_note": self.state.stash_conflict_note,
            "orphan_stashes": self.state.orphan_stashes,
            "out_of_scope_reverted": self.state.out_of_scope_reverted,
            "evidence_note": self.state.evidence_note
            or ("QA did not run: " + ", ".join(evidence_missing) if evidence_missing else ""),
            "style_autofix": self.state.style_autofix,
            "self_check": self.state.self_check,
            "verifier": self.state.verifier,
        }
        allow_empty = False
        if status == "green":  # noqa: SIM102 - recovery block is intentionally separate
            if not in_scope:
                dirty_in_scope = self._in_scope_dirty()
                if not dirty_in_scope:
                    allow_empty = True
                    payload["vacancy_note"] = (
                        "no in-scope changes; recording an empty green commit (already satisfied)"
                    )
                else:
                    status = "needs_human"
                    payload["vacancy_note"] = (
                        "green gates but in-scope work is unrelated to this task: "
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
        # 015 AC-11: never report green over silently skipped coverage.
        from swarm.evidence import count_skipped

        skipped = count_skipped(self.state.transcript)
        db_related = any(
            token in f"{brief} {' '.join(changed)}".lower()
            for token in ("db", "database", "repositor", "persist", "saved_routes", "migration")
        )
        if skipped and db_related:
            self.state.skipped_ac = list(ac_refs)
            payload["skipped_ac"] = list(ac_refs)
            payload["verification_note"] = (
                f"{skipped} test(s) skipped and this task touches persistence; "
                "the AC is not fully exercised (set DATABASE_URL to run them)"
            )
        # Pop the stash here, not in cleanup, so a conflict lands in run.json
        # instead of silently dirtying the tree for the next run.
        self._restore_stash()
        payload["stash_conflict"] = self.state.stash_conflict
        payload["stash_conflict_ref"] = self.state.stash_conflict_ref
        payload["stash_conflict_resolution"] = self.state.stash_conflict_resolution
        payload["stash_conflict_note"] = self.state.stash_conflict_note
        if self.state.stash_conflict_resolution == "crew":
            # The resolver ran after the first snapshot: refresh spend so its
            # tokens/model are in run.json too.
            usage = self._usage_snapshot()
            cost = usage["cost_usd"]
            payload["usage"] = usage
            payload["cost"] = cost
            payload["cost_note"] = (
                "free/local models"
                if cost == 0.0
                else ("unknown price for paid model" if cost is None else "estimated from token usage")
            )
        payload["reason_code"] = _reason_code(status, payload, self.state)
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
        # 018: a copy-pasteable "why did this stop?" next to the run. The
        # dashboard shows it (`h`), but a screen is not pasteable.
        with contextlib.suppress(Exception):
            from swarm.humanlog import write_human_report

            write_human_report(self.run_dir)
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
HARNESS_SPECS = (
    "009-swarm-harness",
    "012-dark-factory-harness",
    "013-dark-factory-phase-2",
    "015-dark-factory-economics",
    "016-conflict-recovery",
    "017-coder-selfcheck",
    "018-operator-readable-runs",
    "019-scenario-verifier",
)


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
    """First *runnable* task in a spec that sorts after `current_dir`.

    013: a `- [ ]` line whose hashes match the done ledger is not work. Without
    the ledger check the queue re-ran 007-T5 (green on 2026-11-09, hash-identical)
    after every green step. 015: parked tasks are skipped too, unless every
    remaining task is parked, so the queue never deadlocks on `retry_later`.
    """
    from swarm.spec_loader import load_spec_tasks, task_key

    parked = _retry_later_keys(repo_root)
    fallback: tuple[str, str] | None = None
    nxt_spec = _spec_after(repo_root, current_dir)
    while nxt_spec is not None:
        try:
            spec_path, nt = load_spec_tasks(repo_root, nxt_spec, None)
        except (OSError, SystemExit):
            spec_path, nt = None, []
        if spec_path is not None and nt:
            todo = _open_task_ids(repo_root, spec_path, nt)
            runnable = [
                t for t in todo if task_key(repo_root, spec_path.name, t) not in parked
            ]
            if runnable:
                return spec_path.name, runnable[0]
            if todo and fallback is None:
                fallback = (spec_path.name, todo[0])
        nxt_spec = _spec_after(repo_root, nxt_spec)
    return fallback


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
    """Earliest unchecked, not-done, not-parked task across the queue (wrap-around)."""
    from swarm.spec_loader import load_spec_tasks, task_key

    specs = repo_root / "specs"
    if not specs.is_dir():
        return None
    parked = _retry_later_keys(repo_root)
    fallback: tuple[str, str] | None = None
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
            if skip == (name, task_id):
                continue
            if task_key(repo_root, name, task_id) in parked:
                if fallback is None:
                    fallback = (name, task_id)
                continue
            return name, task_id
    return fallback


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


def _retry_later_keys(repo_root: Path | None = None) -> set[str]:
    """015 AC-9: tasks the supervisor parked after exhausting their attempts.

    Parked keys are canonicalised on read: an older entry written from
    `run.json.spec` (`007/T9`) must match the flow's `007-live-position/T9`.
    """
    from swarm.spec_loader import task_key

    root = repo_root or REPO_ROOT
    runs = root / "swarm" / "runs"
    try:
        data = json.loads((runs / "retry_later.json").read_text())
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(data, dict):
        return set()
    keys: set[str] = set()
    for raw in data.get("retry_later", []):
        key = str(raw)
        spec, _, task = key.partition("/")
        keys.add(task_key(root, spec, task) if task else key)
    return keys


def _without_retry_later(spec_dir: str, ids: list[str], repo_root: Path | None = None) -> list[str]:
    from swarm.spec_loader import task_key

    root = repo_root or REPO_ROOT
    parked = _retry_later_keys(root)
    kept = [task for task in ids if task_key(root, spec_dir, task) not in parked]
    # Never deadlock: if everything is parked, run them anyway.
    return kept or list(ids)


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
    if status != "green" and task in todo_ids:
        from swarm.spec_loader import task_key

        if task_key(repo_root, spec_path.name, task) not in _retry_later_keys(repo_root):
            return spec_path.name, task
        todo_ids = _without_retry_later(spec_path.name, todo_ids, repo_root)
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
            if single:
                return
            task_cap = status == "budget_exhausted" and str(
                getattr(flow.state, "budget_note", "")
            ).startswith("task ")
            if status != "green" and not task_cap:
                return
            if task_cap:
                # 015 AC-6: a per-task cap must not block the rest of the queue.
                from swarm.supervise import mark_retry_later

                mark_retry_later(f"{spec_dir}/{task_id}")
            todo_ids = _without_retry_later(spec_dir, todo_ids)
            task_id = _next_todo(all_ids, todo_ids, task_id)
        # Spec done and green: advance to the next spec with tasks.
        spec_dir = _spec_after(REPO_ROOT, spec_dir) or ""
        if not spec_dir:
            return
        flow_spec = spec_dir
        spec_path, all_tasks = load_spec_tasks(REPO_ROOT, spec_dir, None)
        all_ids = [t.id for t in all_tasks]
        todo_ids = _open_task_ids(REPO_ROOT, spec_path, all_tasks)
        todo_ids = _without_retry_later(spec_dir, todo_ids)
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
