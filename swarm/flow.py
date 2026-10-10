"""SwarmFlow: load spec → run crew → gate → save run.json (009 T6)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

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
    transcript: str = ""
    plan_reused: bool = False


def plan_cache_path(spec_dir: str, task_id: str) -> Path:
    d = REPO_ROOT / "swarm" / "runs" / "plans"
    d.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{spec_dir}-{task_id}")
    return d / f"{safe}.md"


class SwarmFlow(Flow[SwarmState]):
    def __init__(self, spec_dir: str, task_id: str, no_tui: bool = True, allow_paid: bool = False, replan: bool = False) -> None:
        super().__init__()
        self._spec_dir = spec_dir
        self._task_id = task_id
        self._replan = replan
        self.run_dir = REPO_ROOT / "swarm" / "runs" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        # latest-run pointer: dash.sh attaches here (atomic write, before any LLM call)
        (REPO_ROOT / "swarm" / "runs" / "latest").write_text(self.run_dir.name)
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
        from swarm.tools_guarded import ShellTool

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
        return gates, "\n".join(tails)

    @listen(load_spec)
    def run_crew(self, ctx: dict[str, str]) -> str:
        from swarm.crew import MAX_FIX_ROUNDS, build_crew, build_exec_crew, build_fix_crew
        from swarm.events import SwarmListener
        from swarm.spec_loader import load_spec_tasks

        _, tasks = load_spec_tasks(REPO_ROOT, self._spec_dir, self._task_id)
        self.listener = SwarmListener(self.run_dir)  # always trace, TUI or headless
        cache = plan_cache_path(self._spec_dir, tasks[0].id)

        def _kickoff(crew: object) -> object:
            last_err: Exception | None = None
            for _ in (1, 2):  # one fresh re-kickoff on transient failure
                try:
                    return crew.kickoff()  # type: ignore[union-attr]
                except Exception as e:  # noqa: BLE001
                    last_err = e
            raise SystemExit(f"crew failed twice, trace in {self.run_dir}/run.json") from last_err

        last_crew: object = None
        try:
            if cache.is_file() and not self._replan:
                # Plan already proven good in a previous run: resume at coder.
                plan_text = cache.read_text()
                self.state.plan_reused = True
                last_crew = build_exec_crew(self._spec_dir, tasks[0], plan_text)
                out = _kickoff(last_crew)
            else:
                crew = build_crew(self._spec_dir, tasks[0])
                last_crew = crew
                out = _kickoff(crew)
                # Persist the approved plan for downstream retries (skip re-plan).
                try:
                    plan_out = getattr(crew.tasks[0], "output", None)
                    plan_text = getattr(plan_out, "raw", None) or str(plan_out)
                    if plan_text and plan_text != "None":
                        cache.write_text(plan_text[:8000])
                except Exception:
                    pass
        except SystemExit as e:
            self.state.result = str(e)[:4000]
            self.state.status = "crew_error"
            self.save_run("crew_error")
            raise
        self.state.result = str(out)[:8000]
        # Fix loop: gate fail → coder retry with transcript (bounded) → re-gate.
        gates, transcript = self._run_gates()
        while not all(v == 0 for v in gates.values()) and self.state.fix_rounds < MAX_FIX_ROUNDS:
            self.state.fix_rounds += 1
            self.state.transcript = transcript
            try:
                fix_crew = build_fix_crew(self._spec_dir, tasks[0], transcript)
                fix_out = fix_crew.kickoff()
                self.state.result = str(fix_out)[:8000]
            except Exception as e:  # noqa: BLE001
                self.state.result = f"FIX {self.state.fix_rounds} CREW_ERROR: {type(e).__name__}: {e}"[:4000]
                break
            gates, transcript = self._run_gates()
        self.state.gates = gates
        self.state.transcript = transcript
        self.state.status = "crew_done"
        try:
            usage = last_crew.usage_metrics  # type: ignore[union-attr]
            (self.run_dir / "usage.json").write_text(str(usage))
        except Exception:
            pass
        return self.state.result

    @listen(run_crew)
    def gate(self, result: str) -> str:
        # Gates already ran inside run_crew (fix loop needs them mid-stage);
        # this listener only maps them to a final status.
        self.state.status = "green" if all(v == 0 for v in self.state.gates.values()) else "needs_human"
        return self.state.status

    @listen(gate)
    def save_run(self, status: str) -> str:
        payload = {
            "spec": self.state.spec_dir,
            "task": self.state.task_id,
            "status": status,
            "gates": self.state.gates,
            "fix_rounds": self.state.fix_rounds,
            "plan_reused": self.state.plan_reused,
            "result_tail": self.state.result[-2000:],
            "gate_transcript_tail": self.state.transcript[-2000:],
            "cost": 0,
            "cost_note": "free-first: local + :free only unless allow_paid",
        }
        (self.run_dir / "run.json").write_text(json.dumps(payload, indent=2))
        return status


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="001-example-app")
    ap.add_argument("--task", default="T1")
    ap.add_argument("--no-tui", action="store_true", default=True)
    ap.add_argument("--allow-paid", action="store_true", default=False)
    ap.add_argument("--replan", action="store_true", default=False,
                    help="ignore cached plan and run the planner again")
    args = ap.parse_args()
    flow = SwarmFlow(args.spec, args.task, no_tui=args.no_tui, allow_paid=args.allow_paid, replan=args.replan)
    print(flow.kickoff())


if __name__ == "__main__":
    main()
