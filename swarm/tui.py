"""Operator dashboard for the swarm (009 T7, 012 Phase 1).

Modes:
  live:  python -m swarm.tui --spec 001 --task T1
         runs SwarmFlow in a worker thread, streams bus events into panes.
  tail:  python -m swarm.tui --tail swarm/runs/<ts>
         follows events.jsonl + run.json of any run, even another process.

Layout: spec queue (with per-task outcomes from run history) + models/budget +
gates on the left; crew + planner/coder/reviewer log panes on the right.

Keys: a=approve, r=retry (live), h=history, p/n=older/newer run,
t=back to latest, q=quit.

Fresh session: tail mode skips events logged before attach; panes are empty
apart from status context. History is opt-in (h) or by browsing runs (p/n).

Prior art (2026-11-08): LLM tracers (Phoenix/Langfuse/AgentOps) are great for
per-call spans but do not know specs, ACs, gates or the merge queue; factory
control planes (Myrmecia, AgentFactory, herdr-dagr) duplicate run state. This
dashboard stays a *view* over `run.json`/`events.jsonl` and never owns state.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
from pathlib import Path
from typing import Any, ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, ListItem, ListView, Log, Static

REPO_ROOT = Path(__file__).resolve().parent.parent
PANES = ("crew", "planner", "coder", "reviewer")
ROLE_VARS = (
    ("planner", "SWARM_PLANNER_MODEL"),
    ("coder", "SWARM_CODER_MODEL"),
    ("reviewer", "SWARM_REVIEWER_MODEL"),
    ("senior", "SWARM_SENIOR_MODEL"),
)

STATUS_STYLE = {
    "green": "bold green",
    "crew_done": "green",
    "needs_human": "bold yellow",
    "awaiting_approval": "bold yellow",
    "commit_failed": "bold red",
    "push_failed": "bold red",
    "crew_error": "bold red",
    "quota_exhausted": "bold red",
    "budget_exhausted": "bold red",
    "preflight_failed": "bold red",
    "interrupted": "yellow",
    "init": "dim",
}

STATUS_MARK = {
    "green": ("✓", "green"),
    "needs_human": ("✗", "yellow"),
    "awaiting_approval": ("⏸", "yellow"),
    "commit_failed": ("✗", "red"),
    "push_failed": ("✗", "red"),
    "crew_error": ("⚠", "red"),
    "quota_exhausted": ("⛔", "red"),
    "budget_exhausted": ("⛔", "red"),
    "preflight_failed": ("⚠", "red"),
    "interrupted": ("■", "yellow"),
}


# ---- pure formatting helpers (kept testable, no widgets) ----
def fmt_tokens(n: int | None) -> str:
    if not n:
        return "0"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def fmt_cost(cost: float | None) -> str:
    if cost is None:
        return "unknown"
    if cost == 0:
        return "$0"
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def pct(used: float, limit: float) -> str:
    if limit <= 0:
        return "off"
    return f"{min(999.0, used / limit * 100):.1f}%"


def status_style(status: str) -> str:
    return STATUS_STYLE.get(status, "white")


def status_mark(status: str) -> tuple[str, str]:
    return STATUS_MARK.get(status, ("·", "dim"))


def short_model(model: str) -> str:
    """Compact model label for the narrow side column."""
    m = model
    for prefix in ("openrouter/", "zen/", "ollama/"):
        if m.startswith(prefix):
            m = m.removeprefix(prefix)
            break
    if len(m) > 30 and "/" in m:
        m = m.rsplit("/", 1)[1]
    return m


def _parse_iso(value: str) -> float | None:
    import datetime as dt

    try:
        return dt.datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return None


def elapsed_seconds(payload: dict[str, Any] | None, run_dir: Path | None = None) -> float | None:
    """Recorded duration, else now − started_at (for in-progress runs)."""
    import time

    payload = payload or {}
    usage = payload.get("usage") or {}
    if usage.get("duration_seconds") is not None:
        return float(usage["duration_seconds"])
    started = usage.get("started_at") or payload.get("started_at")
    if not started and run_dir is not None:
        try:
            started = json.loads((run_dir / "meta.json").read_text()).get("started_at")
        except (OSError, json.JSONDecodeError):
            started = None
    ts = _parse_iso(started) if isinstance(started, str) else None
    return max(0.0, time.time() - ts) if ts else None


def format_gates(gates: dict[str, int] | None) -> Text:
    if not gates:
        return Text("gates  not run yet", style="dim")
    out = Text()
    for name, code in gates.items():
        ok = code == 0
        out.append("✓ " if ok else "✗ ", style="green" if ok else "bold red")
        out.append(f"{name} ", style="")
        out.append(f"{code}", style="green" if ok else "red")
        out.append("  ")
    return out


def format_metrics(
    payload: dict[str, Any] | None,
    *,
    models: list[tuple[str, str]] | None = None,
    fallback: bool = False,
    elapsed: float | None = None,
) -> Text:
    payload = payload or {}
    usage = payload.get("usage") or {}
    limits = {
        "tokens": _env_int("SWARM_MAX_TOKENS", 2_000_000),
        "cost": _env_float("SWARM_MAX_COST_USD", 0.05),
        "seconds": _env_int("SWARM_MAX_RUNTIME_SECONDS", 7200),
    }
    out = Text()
    out.append("models\n", style="bold")
    if models:
        for role, model in models:
            out.append(f"  {role:<8} ", style="dim")
            label = short_model(model)
            out.append(label, style="cyan" if model.startswith("ollama/") else "")
            if model.startswith("ollama/"):
                out.append(" local", style="dim")
            out.append("\n")
    else:
        out.append("  (waiting for a run)\n", style="dim")

    if fallback:
        out.append("fallback  ", style="dim")
        out.append("ON — quota/429 switched models\n", style="bold yellow")

    out.append("\nbudget\n", style="bold")
    out.append(f"  tokens  {fmt_tokens(usage.get('total_tokens'))} / {fmt_tokens(limits['tokens'])}", style="")
    out.append(f"  {pct(usage.get('total_tokens') or 0, limits['tokens'])}\n", style="dim")
    out.append(f"  cost    {fmt_cost(usage.get('cost_usd', payload.get('cost')))} / ${limits['cost']:.2f}", style="")
    out.append(f"  {pct(usage.get('cost_usd') or 0, limits['cost'])}\n", style="dim")
    elapsed = elapsed if elapsed is not None else usage.get("duration_seconds")
    out.append(f"  time    {fmt_duration(elapsed)} / {fmt_duration(limits['seconds'])}", style="")
    out.append(f"  {pct(elapsed or 0, limits['seconds'])}\n", style="dim")

    if usage.get("llm_calls"):
        out.append(f"\nllm calls {usage['llm_calls']}", style="dim")
    return out


def format_recent(runs: list[dict[str, Any]], spec: str, limit: int = 5) -> Text:
    out = Text()
    out.append("recent runs\n", style="bold")
    seen: set[tuple[str, str]] = set()
    shown = 0
    for r in runs:  # newest first
        if not _same_spec(str(r.get("spec", "")), spec):
            continue
        key = (str(r.get("spec")), str(r.get("task")))
        if key in seen:
            continue
        seen.add(key)
        shown += 1
        if shown > limit:
            break
        mark, style = status_mark(str(r.get("status", "")))
        usage = r.get("usage") or {}
        out.append(f"  {mark} ", style=style)
        out.append(f"{r.get('task', '?'):<4}", style="bold")
        out.append(f" {r.get('status', '')!s:<17}", style=status_style(str(r.get("status", ""))))
        out.append(f" {fmt_tokens(usage.get('total_tokens')):>7} {fmt_cost(usage.get('cost_usd', r.get('cost'))):>8}", style="dim")
        out.append("\n")
    if not shown:
        out.append("  (none yet)", style="dim")
    return out


def _same_spec(run_spec: str, spec: str) -> bool:
    if not spec or not run_spec:
        return False
    if run_spec == spec:
        return True
    # A bare prefix ("001") matches its directory; two full names match exactly.
    if "-" not in run_spec or "-" not in spec:
        return _spec_prefix(run_spec) == _spec_prefix(spec)
    return False


def queue_marks(runs: list[dict[str, Any]], spec: str) -> dict[str, str]:
    """task id → newest known status for this spec."""
    marks: dict[str, str] = {}
    for r in runs:  # newest first
        if not _same_spec(str(r.get("spec", "")), spec):
            continue
        task = str(r.get("task", ""))
        if task and task not in marks:
            marks[task] = str(r.get("status", ""))
    return marks


def scan_runs(repo_root: Path, limit: int = 300) -> list[dict[str, Any]]:
    """All run.json records, newest first (read-only; skips unreadable dirs)."""
    runs_dir = repo_root / "swarm" / "runs"
    if not runs_dir.is_dir():
        return []
    dirs = sorted(
        (p for p in runs_dir.iterdir() if p.is_dir() and p.name[:1].isdigit()),
        reverse=True,
    )[:limit]
    out: list[dict[str, Any]] = []
    for d in dirs:
        rec_any: Any = {}
        for name in ("run.json", "meta.json"):
            try:
                rec_any = json.loads((d / name).read_text())
                break
            except (OSError, json.JSONDecodeError):
                rec_any = {}
        if not isinstance(rec_any, dict) or not rec_any:
            continue
        rec: dict[str, Any] = rec_any
        rec.setdefault("run", d.name)
        out.append(rec)
    return out


def _spec_prefix(spec: str) -> str:
    return spec.split("-", 1)[0] if spec else spec


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def run_dirs(repo_root: Path, limit: int = 200) -> list[Path]:
    """Run directories, newest first (excludes plans/probes/approvals)."""
    runs = repo_root / "swarm" / "runs"
    if not runs.is_dir():
        return []
    return sorted(
        (p for p in runs.iterdir() if p.is_dir() and p.name[:1].isdigit()),
        reverse=True,
    )[:limit]


def shift_run(dirs: list[Path], current: Path | None, delta: int) -> Path | None:
    """Move through history: delta −1 = older run, +1 = newer run."""
    if not dirs:
        return None
    try:
        i = dirs.index(current) if current is not None else 0
    except ValueError:
        i = 0 if delta < 0 else len(dirs) - 1
    j = i - delta  # newest-first list: newer means a lower index
    return dirs[j] if 0 <= j < len(dirs) else None


class SwarmTUI(App[None]):
    TITLE = "swarm"
    SUB_TITLE = "dark factory console"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("a", "approve", "approve"),
        Binding("r", "retry", "retry"),
        Binding("h", "history", "history"),
        Binding("p", "prev_run", "prev run"),
        Binding("n", "next_run", "next run"),
        Binding("t", "tail_latest", "tail latest"),
        Binding("q", "quit", "quit"),
    ]

    CSS = """
    #status { height: 3; padding: 0 1; background: $panel; }
    #side { width: 46; border-right: solid $primary; }
    #side > .pane-h { background: $panel; color: $text; padding: 0 1; text-style: bold; }
    #tasklist { height: 11; padding: 0 1; }
    #metrics { height: 12; padding: 0 1; }
    #gates { height: 3; padding: 0 1; }
    #recent { height: 8; padding: 0 1; }
    #side-scroll { height: 1fr; }
    #right { width: 1fr; }
    Log { height: 1fr; padding: 0 1; }
    """

    def __init__(self, spec: str, task: str, tail: str | None = None) -> None:
        super().__init__()
        self._spec, self._task_id, self._tail = spec, task, tail
        self._flow: object = None
        self._run_dir: Path | None = Path(tail) if tail else None
        self._tail_pos = 0
        self._tail_buf = b""
        self._active = "crew"
        self._tasks: list[str] = []
        self._plan_noted = False
        self._meta_dir: Path | None = None
        self._poll_count = 0
        self._history: list[dict[str, Any]] = []
        self._payload: dict[str, Any] = {}
        self._queue_sig: tuple[Any, ...] | None = None
        self._pinned = False      # browsing an older run (stop following latest)
        self._history_open = False  # panes currently show replayed history

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="status")
        with Horizontal():
            with Vertical(id="side"):
                yield Static("queue", classes="pane-h")
                yield ListView(id="tasklist")
                with VerticalScroll(id="side-scroll"):
                    yield Static("", id="metrics")
                    yield Static("", id="gates")
                    yield Static("", id="recent")
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
            self._tasks = [t.id for t in tasks]
        except Exception as e:
            self._set_status(f"spec load failed: {e}")
            return
        self._refresh_history()
        self._rebuild_tasklist()
        if self._tail:
            self._seek_end()
            self._pane_log("crew", "attached — new events only (h history · p/n runs · t latest)")
            self._set_status(f"tailing {self._run_dir.name if self._run_dir else self._tail}")
            self.set_interval(0.5, self._poll_tail)
        else:
            self._set_status("run starting in worker thread… (r=retry a=approve h=history q=quit)")
            self.set_interval(0.2, self._poll_live)
            threading.Thread(target=self._run_flow, daemon=True).start()

    # ---- live mode ----
    def _run_flow(self) -> None:
        from swarm.flow import run_tasks

        try:
            for flow, status in run_tasks(self._spec, self._task_id):
                self._flow = flow
                self._run_dir = flow.run_dir
                self._task_id = flow.state.task_id or self._task_id
                if flow.state.spec_dir:
                    self._spec = flow.state.spec_dir
                self.call_from_thread(self._clear_logs)
                self.call_from_thread(setattr, self, "_history_open", False)
                self.call_from_thread(self._rebuild_tasklist, True)
                self._plan_noted = False
                self.call_from_thread(self._pane_log, "crew", f"── task {self._task_id}: {status} ──")
                if status != "green":
                    break
            self.call_from_thread(self._pane_log, "crew", "flow finished")
        except SystemExit as e:
            self.call_from_thread(self._pane_log, "crew", f"flow stopped: {e}")
        except Exception as e:
            self.call_from_thread(self._pane_log, "crew", f"flow crashed: {type(e).__name__}: {e}")
        self.call_from_thread(self._refresh_status)

    def _poll_live(self) -> None:
        self._poll_count += 1
        flow = self._flow
        listener = getattr(flow, "listener", None) if flow else None
        if listener is not None:
            drained = 0
            while drained < 200:
                try:
                    ev = listener.events.get_nowait()
                except Exception:
                    break
                self._handle(ev)
                drained += 1
        self._note_plan_cache()
        if self._poll_count % 10 == 0:
            self._refresh_history()
            self._rebuild_tasklist()
        self._refresh_status()

    def _note_plan_cache(self) -> None:
        """Planner pane must never look dead: report cached vs fresh plan."""
        if self._plan_noted:
            return
        # Tail mode is launched with default spec/task args: prefer the tailed
        # run's own meta.json so the note matches the run being watched.
        spec, task_id = self._spec, self._task_id
        if self._tail and self._run_dir:
            try:
                meta = json.loads((self._run_dir / "meta.json").read_text())
                spec, task_id = meta.get("spec", spec), meta.get("task", task_id)
            except Exception:
                pass
        plans = REPO_ROOT / "swarm" / "runs" / "plans"
        cached: Path | None = None
        if plans.is_dir():
            cands = sorted(plans.glob(f"*-{task_id}.md"))
            match = [c for c in cands if spec in c.stem]
            cached = (match + cands + [None])[0]
        if cached is None and self._run_dir is None:
            return  # run hasn't started, nothing to report yet
        self._plan_noted = True
        if cached is not None:
            self._pane_log("planner", f"plan cached, planner skipped ({cached.name})")
            try:
                from swarm.crew import parse_steps

                for i, step in enumerate(parse_steps(cached.read_text()), 1):
                    self._pane_log("planner", f"STEP {i}: {step[:120]}")
            except Exception:
                pass
        else:
            self._pane_log("planner", "no cached plan — planner running")

    # ---- queue / history ----
    def _refresh_history(self) -> None:
        self._history = scan_runs(REPO_ROOT)

    def _rebuild_tasklist(self, force: bool = False) -> None:
        """Refresh the queue with newest per-task outcome + current marker.

        Rebuilding on a timer duplicated rows (ListView.clear is deferred), so
        the signature gate + in-place update keeps the list stable.
        """
        try:
            from swarm.spec_loader import load_spec_tasks

            _, tasks = load_spec_tasks(REPO_ROOT, self._spec, None)
            marks = queue_marks(self._history, self._spec)
            sig = (self._spec, self._task_id, tuple(t.id for t in tasks), tuple(sorted(marks.items())))
            if not force and sig == self._queue_sig:
                return
            self._queue_sig = sig
            lv = self.query_one("#tasklist", ListView)
            existing = list(lv.children)
            lines: list[Text] = []
            for t in tasks:
                if t.id == self._task_id:
                    mark, style = "▶", "bold cyan"
                else:
                    mark, style = status_mark(marks.get(t.id, ""))
                line = Text()
                line.append(f"{mark} ", style=style)
                line.append(f"{t.id:<3} ", style="bold")
                line.append(t.brief[:52], style="" if t.id == self._task_id else "dim")
                lines.append(line)
            if len(existing) == len(lines):
                for item, line in zip(existing, lines):
                    child = item.children[0] if item.children else None
                    if child is not None:
                        child.update(line)
                return
            lv.clear()
            for line in lines:
                lv.append(ListItem(Static(line)))
        except Exception:
            pass

    # ---- tail mode ----
    def _seek_end(self) -> None:
        """Fresh attach: skip whatever was already logged before this session."""
        self._tail_buf = b""
        self._tail_pos = 0
        if self._run_dir:
            try:
                self._tail_pos = (self._run_dir / "events.jsonl").stat().st_size
            except OSError:
                pass

    def _clear_logs(self) -> None:
        for pane in PANES:
            try:
                self.query_one(f"#log-{pane}", Log).clear()
            except Exception:
                pass

    def _replay_history(self, run_dir: Path, limit: int = 300) -> None:
        """Load this run's last `limit` events into the panes on request."""
        self._clear_logs()
        fp = run_dir / "events.jsonl"
        try:
            lines = fp.read_text(errors="replace").splitlines()[-limit:]
        except OSError:
            self._pane_log("crew", "no events recorded for this run")
        else:
            self._pane_log("crew", f"── history: {run_dir.name} ({len(lines)} events) ──")
            for line in lines:
                try:
                    self._handle(json.loads(line))
                except Exception:
                    pass
        try:
            self._tail_pos = fp.stat().st_size
        except OSError:
            self._tail_pos = 0
        self._tail_buf = b""
        self._history_open = True

    def _load_run(self, run_dir: Path) -> None:
        """Pin the dashboard to a historical run and show its tail."""
        self._run_dir = run_dir
        self._pinned = True
        self._sync_tail_meta()
        self._refresh_history()
        self._rebuild_tasklist(force=True)
        self._replay_history(run_dir)
        self._refresh_status()

    def _step_run(self, delta: int) -> None:
        nxt = shift_run(run_dirs(REPO_ROOT), self._run_dir, delta)
        if nxt is None:
            self._pane_log("crew", "no older/newer run")
            return
        self._load_run(nxt)
        self._pane_log("crew", f"viewing {nxt.name} (t = back to latest)")

    def _sync_tail_meta(self) -> None:
        """Adopt the tailed run's spec/task so tasklist + plan note match it."""
        if self._meta_dir == self._run_dir or self._run_dir is None:
            return
        self._meta_dir = self._run_dir
        try:
            meta = json.loads((self._run_dir / "meta.json").read_text())
        except Exception:
            return
        self._spec = str(meta.get("spec", self._spec))
        self._task_id = str(meta.get("task", self._task_id))
        self._rebuild_tasklist()

    def _poll_tail(self) -> None:
        assert self._run_dir
        self._sync_tail_meta()
        # Follow the loop across tasks: jump when a newer run becomes latest.
        # While pinned to history (p/n), never yank the view forward.
        if not self._pinned:
            try:
                cur = (REPO_ROOT / "swarm" / "runs" / "latest").read_text().strip()
                want = self._run_dir.parent / cur
                if cur and want.is_dir() and want != self._run_dir:
                    self._run_dir = want
                    self._tail_pos = 0
                    self._tail_buf = b""
                    self._plan_noted = False
                    self._history_open = False
                    self._clear_logs()
                    self._sync_tail_meta()
                    self._refresh_history()
                    self._rebuild_tasklist(force=True)
                    self._pane_log("crew", f"── following {cur} ──")
            except Exception:
                pass
        fp = self._run_dir / "events.jsonl"
        if fp.is_file():
            # Incremental read: seek to the last offset, keep a partial-line
            # buffer, and parse only complete lines. Re-reading the whole file
            # every 0.5 s got slower as events accumulated (012 T15).
            try:
                with fp.open("rb") as f:
                    f.seek(self._tail_pos)
                    chunk = f.read()
                    self._tail_pos = f.tell()
                if chunk:
                    self._tail_buf += chunk
                    while b"\n" in self._tail_buf:
                        raw, self._tail_buf = self._tail_buf.split(b"\n", 1)
                        try:
                            self._handle(json.loads(raw.decode("utf-8", "replace")))
                        except Exception:
                            pass
            except OSError:
                pass
        self._poll_count += 1
        if self._poll_count % 4 == 0:
            self._refresh_history()
            self._rebuild_tasklist()
        self._note_plan_cache()
        self._refresh_status()

    # ---- event handling ----
    def _handle(self, ev: dict) -> None:
        t = ev.get("type", "")
        if t == "agent_started":
            self._active = ev.get("pane", "crew")
            self._pane_log(self._active, f"▶ {ev.get('agent', '?')} started")
        elif t == "agent_done":
            self._pane_log(ev.get("pane", "crew"), f"✔ {ev.get('agent', '?')} done")
        elif t in ("agent_error", "llm_failed", "task_failed", "crew_failed"):
            text = str(ev.get("text", t))
            if text.startswith("timestamp="):
                text = t  # old events stored a raw repr before _event_error
            self._pane_log(ev.get("pane", "crew"), f"✘ {text[:200]}")
        elif t == "chunk":
            pane = self._active if self._active in PANES else "crew"
            self._pane_log(pane, ev.get("text", "")[:500])
        elif t == "task_started":
            self._pane_log("crew", f"task: {ev.get('text', '')[:120]}")
        elif t == "task_done":
            self._pane_log("crew", "task done")
        elif t == "crew_done":
            self._pane_log("crew", "crew done")
            self._refresh_status()

    def _pane_log(self, pane: str, text: str) -> None:
        if pane not in PANES:
            pane = "crew"
        try:
            self.query_one(f"#log-{pane}", Log).write_line(text)
        except Exception:
            pass

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#status", Static).update(text)
        except Exception:
            pass

    def _set_markup(self, widget_id: str, renderable: Text) -> None:
        try:
            self.query_one(f"#{widget_id}", Static).update(renderable)
        except Exception:
            pass

    def _refresh_status(self) -> None:
        if not self._run_dir:
            return
        payload: dict[str, Any] = {}
        rj = self._run_dir / "run.json"
        if rj.is_file():
            try:
                payload = json.loads(rj.read_text())
            except Exception:
                payload = {}
        self._payload = payload
        usage = payload.get("usage") or {}
        elapsed = elapsed_seconds(payload, self._run_dir)
        status = str(payload.get("status", "running"))
        style = status_style(status)
        fallback = False
        if not self._tail:
            try:
                from swarm.llms import fallbacks_active

                fallback = fallbacks_active()
            except Exception:
                pass

        line = Text()
        line.append(f"{self._spec} {self._task_id}", style="bold")
        line.append("  ")
        line.append(f" {status} ", style=f"reverse {style}")
        line.append(f"  {self._run_dir.name}", style="dim")
        if payload.get("plan_reused"):
            line.append("  plan=cached", style="dim")
        if payload.get("dev_attempts"):
            line.append(f"  attempt={payload['dev_attempts']}", style="dim")
        if payload.get("senior_used"):
            line.append("  senior", style="magenta")
        if payload.get("approval_required"):
            line.append("  approval=", style="dim")
            line.append("approved" if payload.get("approved") else "waiting", style="green" if payload.get("approved") else "yellow")
        line.append("\n")
        line.append(f"tok {fmt_tokens(usage.get('total_tokens'))}", style="")
        line.append(f"  cost {fmt_cost(usage.get('cost_usd', payload.get('cost')))}", style="")
        line.append(f"  time {fmt_duration(elapsed)}", style="")
        if usage.get("llm_calls"):
            line.append(f"  calls {usage['llm_calls']}", style="dim")
        if payload.get("budget_note"):
            line.append(f"  {payload['budget_note']}", style="bold red")
        elif payload.get("quota_note"):
            line.append(f"  {payload['quota_note']}", style="bold red")
        self._set_markup("status", line)

        models: list[tuple[str, str]] | None = None
        if self._tail:
            models = [(str(m), str(m)) for m in usage.get("models") or []]
        if not models:
            models = [(role, os.getenv(var, "?")) for role, var in ROLE_VARS]
        self._set_markup("metrics", format_metrics(payload, models=models, fallback=fallback, elapsed=elapsed))
        self._set_markup("gates", format_gates(self._payload.get("gates")))
        self._set_markup("recent", format_recent(self._history or scan_runs(REPO_ROOT), self._spec))

    # ---- keys ----
    def action_approve(self) -> None:
        if not self._run_dir:
            return
        status = ""
        try:
            status = str(json.loads((self._run_dir / "run.json").read_text()).get("status", ""))
        except (OSError, json.JSONDecodeError):
            status = ""
        if status == "awaiting_approval":
            from swarm.flow import approve_held_run

            result = approve_held_run(REPO_ROOT, self._spec, self._task_id)
            if result.get("ok") == "1":
                self._set_status(f"approved+committed {self._run_dir.name}")
                self._refresh_status()
            else:
                self._set_status(f"approval refused: {result.get('note')}")
            return
        (self._run_dir / "approved.json").write_text('{"approved": true}')
        try:
            from swarm.flow import grant_approval

            grant_approval(self._spec, self._task_id)
        except Exception:
            pass
        self._set_status(f"approved {self._run_dir.name} (ledger written)")

    def action_retry(self) -> None:
        if self._tail:
            self._pane_log("crew", "retry is only available in live mode")
            return
        self._pane_log("crew", "── retry: new run, same spec/task ──")
        threading.Thread(target=self._run_flow, daemon=True).start()

    def action_history(self) -> None:
        """Toggle this run's replayed event log (off by default: fresh session)."""
        if not self._run_dir:
            return
        if self._history_open:
            self._history_open = False
            self._clear_logs()
            self._seek_end()
            self._pane_log("crew", "history hidden — live events only")
            return
        self._replay_history(self._run_dir)

    def action_prev_run(self) -> None:
        self._step_run(-1)

    def action_next_run(self) -> None:
        self._step_run(1)

    def action_tail_latest(self) -> None:
        dirs = run_dirs(REPO_ROOT)
        if not dirs:
            return
        self._run_dir = dirs[0]
        self._pinned = False
        self._history_open = False
        self._sync_tail_meta()
        self._clear_logs()
        self._seek_end()
        self._refresh_history()
        self._rebuild_tasklist(force=True)
        self._refresh_status()
        self._pane_log("crew", f"tailing latest {dirs[0].name} — new events only")


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
