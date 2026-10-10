"""Dynamic parallel dashboard (009 T7): per-agent panes + task list, live.

Modes:
  live:  python -m swarm.tui --spec 001 --task T1
         runs SwarmFlow in a worker thread, streams bus events into panes.
  tail:  python -m swarm.tui --tail swarm/runs/<ts>
         follows events.jsonl + run.json of any run, even another process.

Keys: a=approve (writes approved.json), r=retry (new run, same spec/task), q=quit.
"""

from __future__ import annotations

import argparse
import json
import threading
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, ListItem, ListView, Log, Static

REPO_ROOT = Path(__file__).resolve().parent.parent
PANES = ("planner", "coder", "reviewer")


class SwarmTUI(App[None]):
    def __init__(self, spec: str, task: str, tail: str | None = None) -> None:
        super().__init__()
        self._spec, self._task_id, self._tail = spec, task, tail
        self._flow: object = None
        self._run_dir: Path | None = Path(tail) if tail else None
        self._tail_off = 0
        self._active = "crew"
        self._tasks: list[str] = []
        self._plan_noted = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="status")
        with Horizontal():
            with Vertical(id="left"):
                yield Static("tasks", id="tasks-h")
                yield ListView(id="tasklist")
            with Vertical(id="right"):
                for p in PANES:
                    yield Static(p, classes="pane-h")
                    yield Log(id=f"log-{p}", classes="pane")
        yield Footer()

    def on_mount(self) -> None:
        self._set_status("starting…")
        try:
            from swarm.spec_loader import load_spec_tasks

            _, tasks = load_spec_tasks(REPO_ROOT, self._spec, None)
            lv = self.query_one("#tasklist", ListView)
            for t in tasks:
                mark = "▶" if t.id == self._task_id else "·"
                self._tasks.append(t.id)
                lv.append(ListItem(Static(f"{mark} {t.id}: {t.brief[:60]}")))
        except Exception as e:
            self._set_status(f"spec load failed: {e}")
            return
        if self._tail:
            self._set_status(f"tailing {self._tail} (a=approve q=quit)")
            self.set_interval(0.5, self._poll_tail)
        else:
            self._set_status("run starting in worker thread… (r=retry a=approve q=quit)")
            self.set_interval(0.2, self._poll_live)
            threading.Thread(target=self._run_flow, daemon=True).start()

    # ---- live mode ----
    def _run_flow(self) -> None:
        from swarm.flow import SwarmFlow

        flow = SwarmFlow(self._spec, self._task_id)
        self._flow = flow
        self._run_dir = flow.run_dir
        try:
            status = flow.kickoff()
            self.call_from_thread(self._log, "crew", f"flow finished: {status}")
        except SystemExit as e:
            self.call_from_thread(self._log, "crew", f"flow stopped: {e}")
        except Exception as e:  # noqa: BLE001
            self.call_from_thread(self._log, "crew", f"flow crashed: {type(e).__name__}: {e}")
        self.call_from_thread(self._refresh_status)

    def _poll_live(self) -> None:
        flow = self._flow
        listener = getattr(flow, "listener", None) if flow else None
        if listener is None:
            return
        drained = 0
        while drained < 200:
            try:
                ev = listener.events.get_nowait()
            except Exception:
                break
            self._handle(ev)
            drained += 1
        self._note_plan_cache()
        self._refresh_status()

    def _note_plan_cache(self) -> None:
        """Planner pane must never look dead: report cached vs fresh plan."""
        if self._plan_noted:
            return
        plans = REPO_ROOT / "swarm" / "runs" / "plans"
        cached = None
        if plans.is_dir():
            cands = sorted(plans.glob(f"*-{self._task_id}.md"))
            match = [c for c in cands if self._spec in c.stem]
            cached = (match or cands or [None])[0]
        if cached is None and self._run_dir is None:
            return  # run hasn't started, nothing to report yet
        self._plan_noted = True
        if cached is not None:
            self._log("planner", f"plan cached, planner skipped ({cached.name})")
        else:
            self._log("planner", "no cached plan — planner running")

    # ---- tail mode ----
    def _poll_tail(self) -> None:
        assert self._run_dir
        fp = self._run_dir / "events.jsonl"
        if fp.is_file():
            lines = fp.read_text().splitlines()
            for line in lines[self._tail_off :]:
                try:
                    self._handle(json.loads(line))
                except Exception:
                    pass
            self._tail_off = len(lines)
        rj = self._run_dir / "run.json"
        if rj.is_file():
            try:
                r = json.loads(rj.read_text())
                self._set_status(f"tail {self._run_dir.name}: {r.get('status')} gates={r.get('gates')}")
            except Exception:
                pass

    # ---- event handling ----
    def _handle(self, ev: dict) -> None:
        t = ev.get("type", "")
        if t == "agent_started":
            self._active = ev.get("pane", "crew")
            self._log(self._active, f"▶ {ev.get('agent', '?')} started")
        elif t == "agent_done":
            self._log(ev.get("pane", "crew"), f"✔ {ev.get('agent', '?')} done")
        elif t in ("agent_error", "llm_failed", "task_failed", "crew_failed"):
            self._log(ev.get("pane", "crew"), f"✘ {ev.get('text', t)[:200]}")
        elif t == "chunk":
            pane = self._active if self._active in PANES else "coder"
            self._log(pane, ev.get("text", "")[:500])
        elif t == "task_started":
            self._log("crew", f"task: {ev.get('text', '')[:120]}")
        elif t == "task_done":
            self._log("crew", "task done")
        elif t == "crew_done":
            self._log("crew", "crew done")
            self._refresh_status()

    def _log(self, pane: str, text: str) -> None:
        if pane not in PANES:
            pane = "coder"
        try:
            self.query_one(f"#log-{pane}", Log).write_line(text)
        except Exception:
            pass

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#status", Static).update(text)
        except Exception:
            pass

    def _refresh_status(self) -> None:
        if not self._run_dir:
            return
        rj = self._run_dir / "run.json"
        extra = ""
        if rj.is_file():
            try:
                r = json.loads(rj.read_text())
                extra = f" status={r.get('status')} gates={r.get('gates')}"
                if r.get("plan_reused"):
                    extra += " plan=cached"
            except Exception:
                pass
        elif self._plan_noted:
            plans = REPO_ROOT / "swarm" / "runs" / "plans"
            if plans.is_dir() and list(plans.glob(f"*-{self._task_id}.md")):
                extra = " plan=cached (planner skipped)"
        self._set_status(f"spec={self._spec} task={self._task_id} run={self._run_dir.name}{extra} cost=$0")

    # ---- keys ----
    def on_key(self, event: object) -> None:
        key = getattr(event, "key", "")
        if key == "q":
            self.exit()
        elif key == "a" and self._run_dir:
            (self._run_dir / "approved.json").write_text('{"approved": true}')
            self._set_status(f"approved {self._run_dir.name}")
        elif key == "r" and not self._tail:
            self._log("crew", "── retry: new run, same spec/task ──")
            threading.Thread(target=self._run_flow, daemon=True).start()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="001-example-app")
    ap.add_argument("--task", default="T1")
    ap.add_argument("--tail", default=None, help="follow swarm/runs/<ts> of another process")
    ap.add_argument("--no-tui", action="store_true", default=False)
    args = ap.parse_args()
    if args.no_tui:
        print(f"no-tui mode: spec={args.spec} task={args.task}")
        return
    SwarmTUI(args.spec, args.task, tail=args.tail).run()


if __name__ == "__main__":
    main()
