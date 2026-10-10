"""SwarmFlow: load spec → run crew → gate → save run.json (009 T6)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent


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


def plan_cache_path(spec_dir: str, task_id: str) -> Path:
    d = REPO_ROOT / "swarm" / "runs" / "plans"
    d.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{spec_dir}-{task_id}")
    return d / f"{safe}.md"


def _resolve_scope() -> tuple[str, ...]:
    """Coder scope: SWARM_SCOPE (comma-separated) overrides, else DEFAULT_SCOPE."""
    import os as _os

    from swarm.tools_guarded import DEFAULT_SCOPE

    return tuple(s for s in _os.getenv("SWARM_SCOPE", "").split(",") if s) or DEFAULT_SCOPE


def _commit_changes(spec_id: str, task_id: str, brief: str) -> dict[str, str]:
    """Commit + push in-scope worktree changes. Out-of-scope files are never added."""
    from swarm.tools_guarded import _git_changed, scope_violations

    rec: dict[str, str] = {}
    scope = _resolve_scope()
    changed = _git_changed()
    in_scope = [p for p in changed if p not in scope_violations([p], scope)]
    if any(".env" in p for p in in_scope):
        rec["commit"] = "refused: .env-looking path in scope set"
        return rec
    if not in_scope:
        rec["commit"] = "clean (nothing in scope changed)"
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
    return rec


class SwarmFlow(Flow[SwarmState]):
    def __init__(self, spec_dir: str, task_id: str, no_tui: bool = True, allow_paid: bool = False, replan: bool = False, commit: bool = True) -> None:
        super().__init__()
        self._spec_dir = spec_dir
        self._task_id = task_id
        self._replan = replan
        self._commit = commit
        self.run_dir = REPO_ROOT / "swarm" / "runs" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        # latest-run pointer: dash.sh attaches here (atomic write, before any LLM call)
        (REPO_ROOT / "swarm" / "runs" / "latest").write_text(self.run_dir.name)
        # meta.json: TUI tail mode reads the run's own spec/task from here.
        (self.run_dir / "meta.json").write_text(json.dumps({"spec": spec_dir, "task": task_id}))
        print(f"run_dir={self.run_dir}", flush=True)

    @start()
    def load_spec(self) -> dict[str, str]:
        from swarm.spec_loader import load_spec_tasks

        spec_path, tasks = load_spec_tasks(REPO_ROOT, self._spec_dir, self._task_id)
        if not tasks:
            raise SystemExit(f"No task {self._task_id} in {self._spec_dir}")
        self.state.spec_dir, self.state.task_id = self._spec_dir, tasks[0].id
        return {"spec_path": str(spec_path), "task": tasks[0].id, "brief": tasks[0].brief}

    def _run_gates(self) -> tuple[dict[str, int], str]:
        """Run constitution gates independently (never trust agent claims)."""
        from swarm.tools_guarded import (
            ShellTool,
            _git_changed,
            scope_violations,
        )

        shell = ShellTool()
        gates: dict[str, int] = {}
        tails: list[str] = []
        for cmd in ("pytest -q", "ruff check .", "mypy ."):
            out = shell._run(cmd)
            try:
                gates[cmd] = int(out.split("exit=")[1].split()[0])
            except Exception:
                gates[cmd] = 99
            tails.append(f"$ {cmd}\n{out[-1200:]}")
        # Scope: coder may only touch scaffold paths (SWARM_SCOPE overrides).
        bad = scope_violations(_git_changed(), _resolve_scope())
        gates["scope"] = 0 if not bad else 1
        tails.append("$ scope\nOK" if not bad else f"$ scope\nVIOLATIONS: {bad}")
        return gates, "\n".join(tails)

    def _commit_green(self, brief: str) -> dict[str, str]:
        """Commit + push in-scope changes after a green run. Never touches out-of-scope files."""
        return _commit_changes(self.state.spec_dir, self.state.task_id, brief)

    @listen(load_spec)
    def run_crew(self, ctx: dict[str, str]) -> str:
        from swarm.crew import (
            DEV_ATTEMPTS,
            MAX_FIX_ROUNDS,
            SENIOR_ATTEMPTS,
            build_fix_crew,
            build_plan_crew,
            build_review_crew,
            build_senior_crew,
            build_step_crew,
            parse_steps,
        )
        from swarm.events import SwarmListener
        from swarm.spec_loader import load_spec_tasks

        task = load_spec_tasks(REPO_ROOT, self._spec_dir, self._task_id)[1][0]
        self.listener = SwarmListener(self.run_dir)  # always trace, TUI or headless
        cache = plan_cache_path(self._spec_dir, task.id)

        def _kickoff(crew: Any) -> tuple[Any, str]:
            last_err: Exception | None = None
            for _ in (1, 2):  # one fresh re-kickoff on transient failure
                try:
                    out = crew.kickoff()
                    return crew, str(out)[:8000]
                except Exception as e:
                    last_err = e
            raise SystemExit(f"crew failed twice, trace in {self.run_dir}/run.json") from last_err

        def _plan_text(crew: Any) -> str:
            try:
                plan_out = getattr(crew.tasks[0], "output", None)
                text = getattr(plan_out, "raw", None) or str(plan_out)
                return text if text != "None" else ""
            except Exception:
                return ""

        try:
            if cache.is_file() and not self._replan:
                # Proven plan: resume at micro-steps, skip re-planning.
                plan_text = cache.read_text()
                self.state.plan_reused = True
            else:
                plan_crew, _ = _kickoff(build_plan_crew(self._spec_dir, task))
                plan_text = _plan_text(plan_crew)
                if plan_text:
                    cache.write_text(plan_text[:8000])
            steps = parse_steps(plan_text) or ([plan_text] if plan_text else [])
            if not steps:
                raise SystemExit("planner returned no usable plan")
            gates: dict[str, int] = {}
            transcript = ""
            # Dev phase (micro-steps + review + gates + fix round), up to
            # DEV_ATTEMPTS; then senior escalation, then human.
            while True:
                self.state.dev_attempts += 1
                # Micro-execution: fresh coder (fresh context) per step; reviewer only at the end.
                step_outs: list[str] = []
                for i, step in enumerate(steps, 1):
                    _, step_out = _kickoff(build_step_crew(self._spec_dir, task, step, i, len(steps)))
                    step_outs.append(f"--- step {i}/{len(steps)} ---\n{step_out}")
                work_summary = "\n".join(step_outs)
                _, review_out = _kickoff(build_review_crew(self._spec_dir, task, work_summary))
                self.state.result = f"{work_summary}\n--- review ---\n{review_out}"[:8000]
                # Fix loop: gate fail → coder retry with transcript (bounded) → re-gate.
                base_rounds = self.state.fix_rounds
                gates, transcript = self._run_gates()
                while not all(v == 0 for v in gates.values()) and self.state.fix_rounds - base_rounds < MAX_FIX_ROUNDS:
                    self.state.fix_rounds += 1
                    self.state.transcript = transcript
                    try:
                        _, fix_out = _kickoff(build_fix_crew(self._spec_dir, task, transcript))
                        self.state.result = str(fix_out)[:8000]
                    except SystemExit as e:
                        self.state.result = str(e)[:4000]
                        break
                    gates, transcript = self._run_gates()
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
                        _, senior_out = _kickoff(build_senior_crew(self._spec_dir, task, transcript))
                        self.state.result = str(senior_out)[:8000]
                    except SystemExit as e:
                        self.state.result = str(e)[:4000]
                        raise
                    _, review_out = _kickoff(build_review_crew(self._spec_dir, task, self.state.result))
                    self.state.result = f"{self.state.result}\n--- senior review ---\n{review_out}"[:8000]
                    gates, transcript = self._run_gates()
        except SystemExit as e:
            self.state.result = str(e)[:4000]
            self.state.status = "crew_error"
            self.save_run("crew_error")
            raise
        self.state.gates = gates
        self.state.transcript = transcript
        self.state.status = "crew_done"
        return self.state.result

    @listen(run_crew)
    def gate(self, result: str) -> str:
        # Gates already ran inside run_crew (fix loop needs them mid-stage);
        # this listener only maps them to a final status.
        self.state.status = "green" if all(v == 0 for v in self.state.gates.values()) else "needs_human"
        return self.state.status

    @listen(gate)
    def save_run(self, status: str) -> str:
        payload: dict[str, Any] = {
            "spec": self.state.spec_dir,
            "task": self.state.task_id,
            "status": status,
            "gates": self.state.gates,
            "fix_rounds": self.state.fix_rounds,
            "dev_attempts": self.state.dev_attempts,
            "senior_used": self.state.senior_used,
            "senior_rounds": self.state.senior_rounds,
            "plan_reused": self.state.plan_reused,
            "result_tail": self.state.result[-2000:],
            "gate_transcript_tail": self.state.transcript[-2000:],
            "cost": 0,
            "cost_note": "free-first: local + :free only unless allow_paid",
        }
        if status == "green" and self._commit:
            from swarm.spec_loader import load_spec_tasks

            task = load_spec_tasks(REPO_ROOT, self._spec_dir, self._task_id)[1][0]
            payload["autocommit"] = self._commit_green(task.brief)
        (self.run_dir / "run.json").write_text(json.dumps(payload, indent=2))
        return status


def _next_after(ids: list[str], current: str) -> str | None:
    """Next task id in spec order after `current`; None when done."""
    try:
        nxt = ids[ids.index(current) + 1]
    except (ValueError, IndexError):
        return None
    return nxt


# The harness never implements itself: pilots stay out of the swarm spec.
HARNESS_SPECS = ("009-swarm-harness",)


def _spec_after(repo_root: Path, current_dir: str) -> str | None:
    """Next spec dir (directory order) that has tasks, skipping the harness spec."""
    specs = repo_root / "specs"
    names = sorted(
        p.name
        for p in specs.iterdir()
        if p.is_dir() and (p / "tasks.md").is_file() and p.name not in HARNESS_SPECS
    )
    return _next_after(names, current_dir)


def run_tasks(spec_prefix: str, start_task: str, *, allow_paid: bool = False, replan: bool = False, commit: bool = True, single: bool = False) -> Any:
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
            flow = SwarmFlow(flow_spec, task_id, allow_paid=allow_paid, replan=replan, commit=commit)
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
    ap.add_argument("--spec", default="001-example-app")
    ap.add_argument("--task", default="T1")
    ap.add_argument("--no-tui", action="store_true", default=True)
    ap.add_argument("--allow-paid", action="store_true", default=False)
    ap.add_argument("--replan", action="store_true", default=False,
                    help="ignore cached plan and run the planner again")
    ap.add_argument("--no-commit", action="store_true", default=False,
                    help="skip autocommit+push after green runs")
    ap.add_argument("--single", action="store_true", default=False,
                    help="run only the given task, do not loop to the next one")
    args = ap.parse_args()
    for flow, status in run_tasks(args.spec, args.task, allow_paid=args.allow_paid, replan=args.replan, commit=not args.no_commit, single=args.single):
        print(f"{flow.state.task_id}: {status}")


if __name__ == "__main__":
    main()
