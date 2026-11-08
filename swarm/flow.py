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

TERMINAL_STATUSES = (
    "crew_error",
    "quota_exhausted",
    "budget_exhausted",
    "interrupted",
    "preflight_failed",
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


def _commit_changes(
    spec_id: str,
    task_id: str,
    brief: str,
    paths: list[str] | None = None,
    scope: tuple[str, ...] | None = None,
) -> dict[str, str]:
    """Commit + push only the run-delta paths that are in scope.

    Returns ``{commit, push, ok}``; ``ok == "0"`` means the run must not be green.
    """
    from swarm.tools_guarded import _git_changed, is_secret_path, scope_violations

    rec: dict[str, str] = {"commit": "", "push": "", "ok": "0"}
    scope = scope or _resolve_scope()
    changed = list(paths) if paths is not None else _git_changed()
    secret = [p for p in changed if is_secret_path(p)]
    if secret:
        rec["commit"] = f"refused: .env-looking path in run delta: {secret}"
        return rec
    in_scope = [p for p in changed if p not in scope_violations([p], scope)]
    if not in_scope:
        rec["commit"] = "clean (nothing in scope changed)"
        rec["ok"] = "1"
        return rec

    def _sh(args: list[str]) -> tuple[int, str]:
        p = subprocess.run(args, check=False, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
        return p.returncode, (p.stdout + p.stderr)[-500:]

    rc, out = _sh(["git", "add", "-A", "--", *in_scope])
    if rc != 0:
        rec["commit"] = f"git add failed: {out}"
        return rec
    msg = f"swarm: {spec_id}-{task_id} green — {brief[:80]} (autocommit)"
    rc, out = _sh(["git", "commit", "-m", msg])
    if rc != 0:
        rec["commit"] = f"git commit failed: {out}"
        return rec
    rec["commit"] = msg
    rc, out = _sh(["git", "push"])
    rec["push"] = "ok" if rc == 0 else f"failed: {out}"
    rec["ok"] = "1" if rc == 0 else "0"
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
        self._started_monotonic = time.monotonic()
        self.state.started_at = dt.datetime.now().isoformat(timespec="seconds")
        from swarm.usage import env_float, env_int

        self._max_tokens = env_int("SWARM_MAX_TOKENS", 2_000_000)
        self._max_cost = env_float("SWARM_MAX_COST_USD", 0.05)
        self._max_seconds = env_int("SWARM_MAX_RUNTIME_SECONDS", 7200)
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

    def _commit_green(self, brief: str, changed: list[str]) -> dict[str, str]:
        """Commit + push run-delta in-scope changes after a green run."""
        return _commit_changes(self.state.spec_dir, self.state.task_id, brief, paths=changed)

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
            gates: dict[str, int] = {}
            transcript = ""
            # Dev phase (micro-steps + review + gates + fix round), up to
            # DEV_ATTEMPTS; then senior escalation, then human.
            while True:
                self.state.dev_attempts += 1
                # Micro-execution: fresh coder (fresh context) per step; reviewer only at the end.
                # A step failing STEP_ATTEMPTS times is rescued by the senior, then we continue.
                step_outs: list[str] = []
                for i, step in enumerate(steps, 1):
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
                work_summary = "\n".join(step_outs)
                _, review_out = _kickoff(lambda work_summary=work_summary: build_review_crew(self._spec_dir, task, work_summary))
                self.state.review_verdict = reviewer_verdict(review_out)
                self.state.result = f"{work_summary}\n--- review ---\n{review_out}"[:8000]
                # Fix loop: gate fail → coder retry with transcript (bounded) → re-gate.
                base_rounds = self.state.fix_rounds
                changed = run_delta(self._baseline)
                gates, transcript = self._run_gates(changed)
                while not all(v == 0 for v in gates.values()) and self.state.fix_rounds - base_rounds < MAX_FIX_ROUNDS:
                    self.state.fix_rounds += 1
                    self.state.transcript = transcript
                    try:
                        _, fix_out = _kickoff(lambda transcript=transcript: build_fix_crew(self._spec_dir, task, transcript))
                        self.state.review_verdict = reviewer_verdict(fix_out)
                        self.state.result = str(fix_out)[:8000]
                    except SystemExit as e:
                        self.state.result = str(e)[:4000]
                        break
                    changed = run_delta(self._baseline)
                    gates, transcript = self._run_gates(changed)
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
                    self.state.result = f"{self.state.result}\n--- senior review ---\n{review_out}"[:8000]
                    changed = run_delta(self._baseline)
                    gates, transcript = self._run_gates(changed)
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
        from swarm.spec_loader import load_spec_tasks
        from swarm.tools_guarded import in_scope_changes, run_delta

        try:
            _, tasks = load_spec_tasks(REPO_ROOT, self.state.spec_dir, self.state.task_id)
            task = tasks[0] if tasks else None
        except (OSError, SystemExit):
            task = None
        brief = task.brief if task else ""
        ac_refs = list(task.ac_refs) if task else []
        scope = _resolve_scope()
        changed = run_delta(self._baseline)
        in_scope = in_scope_changes(changed, scope)
        approved = approval_granted(self.state.spec_dir, self.state.task_id, self.run_dir)
        self.state.changed_files = changed
        self.state.approved = approved
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
            "gate_transcript_tail": self.state.transcript[-2000:],
            "cost": cost,
            "cost_note": (
                "free/local models"
                if cost == 0.0
                else ("unknown price for paid model" if cost is None else "estimated from token usage")
            ),
            "usage": usage,
            "budget_note": self.state.budget_note,
        }
        if status == "green":
            if not in_scope:
                # Fresh or cached plan that changed nothing in scope = vacuous pass.
                # Runs BEFORE autocommit: committing would wipe the worktree evidence.
                status = "needs_human"
                payload["vacancy_note"] = "green gates but no in-scope changes from this run"
            elif self.state.review_verdict != "pass":
                status = "needs_human"
                payload["review_note"] = f"reviewer verdict was {self.state.review_verdict!r}, not PASS"
            elif self._require_approval and not approved:
                status = "awaiting_approval"
                payload["approval_note"] = (
                    f"approval required: press `a` in the dashboard or run with --approve "
                    f"({approval_path(self.state.spec_dir, self.state.task_id)})"
                )
            elif self._commit:
                rec = self._commit_green(brief, changed)
                payload["autocommit"] = rec
                if rec.get("ok") != "1":
                    status = "push_failed" if rec.get("push", "").startswith("failed") else "commit_failed"
                    payload["status"] = status
        payload["status"] = status
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
HARNESS_SPECS = ("009-swarm-harness", "012-dark-factory-harness")


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


def _first_open_task(repo_root: Path, skip: tuple[str, str] | None = None) -> tuple[str, str] | None:
    """Earliest unchecked task across the queue (wrap-around after the last spec).

    `skip` is the last checkpoint (spec, task): a green task that was never ticked
    must not be resumed forever when it is the only unchecked line left.
    """
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
            _, tasks = load_spec_tasks(repo_root, name, None)
        except (OSError, SystemExit):
            continue
        for t in tasks:
            if skip != (name, t.id):
                return name, t.id
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
    if status != "green" and task in ids:
        return spec_path.name, task
    if task in ids:
        nxt = _next_after(ids, task)
        if nxt is not None:
            return spec_path.name, nxt
    elif ids:
        # Checkpoint task was marked [x] (or renamed): finish this spec first.
        return spec_path.name, ids[0]
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
    ids = [t.id for t in all_tasks]
    if start_task not in ids:
        raise SystemExit(f"No task {start_task} in {spec_prefix} (have: {ids})")
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
            task_id = _next_after(ids, task_id)
        # Spec done and green: advance to the next spec with tasks.
        spec_dir = _spec_after(REPO_ROOT, spec_dir) or ""
        if not spec_dir:
            return
        flow_spec = spec_dir
        _, all_tasks = load_spec_tasks(REPO_ROOT, spec_dir, None)
        ids = [t.id for t in all_tasks]
        task_id = ids[0] if ids else None


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
                    help="write the approval ledger for the given (or resumed) spec/task")
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
        p = grant_approval(args.spec, args.task)
        print(f"approved {args.spec} {args.task} → {p}")
        return
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
