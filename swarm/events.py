"""CrewAI event listener → normalized queue + JSONL (009 T6/T7).

Instantiating SwarmListener auto-registers on CrewAI's singleton event bus,
so it captures any crew run in the same process. TUI drains .events live;
--tail mode replays events.jsonl across processes.
"""

from __future__ import annotations

import json
import queue
from pathlib import Path
from typing import Any


def _agent_name(obj: Any) -> str:
    for attr in ("role", "name"):
        v = getattr(obj, attr, None)
        if isinstance(v, str) and v:
            return v
    return str(obj)[:60] if obj is not None else "?"


def pane_for(name: str) -> str:
    n = name.lower()
    if "plan" in n:
        return "planner"
    if "qa" in n or "review" in n or "gate" in n:
        return "reviewer"
    if "cod" in n or "scaffold" in n or "python" in n:
        return "coder"
    return "crew"


class SwarmListener:
    """Plain listener (no CrewAI ABC import at module load; registers on init)."""

    def __init__(self, run_dir: Path) -> None:
        from crewai.events import BaseEventListener, crewai_event_bus

        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self._handlers: list[tuple[Any, Any]] = []
        outer = self

        class _L(BaseEventListener):
            def setup_listeners(self, bus: Any) -> None:
                from crewai.events import (
                    AgentExecutionCompletedEvent,
                    AgentExecutionErrorEvent,
                    AgentExecutionStartedEvent,
                    CrewKickoffCompletedEvent,
                    CrewKickoffFailedEvent,
                    CrewKickoffStartedEvent,
                    LLMCallFailedEvent,
                    LLMCallStartedEvent,
                    LLMStreamChunkEvent,
                    TaskCompletedEvent,
                    TaskFailedEvent,
                    TaskStartedEvent,
                )

                def _listen(event_type: Any) -> Any:
                    """Register + remember the handler so teardown can unregister it."""

                    def deco(fn: Any) -> Any:
                        bus.on(event_type)(fn)
                        outer._handlers.append((event_type, fn))
                        return fn

                    return deco

                @_listen(CrewKickoffStartedEvent)
                def _cs(source: Any, event: Any) -> None:
                    outer._append({"type": "crew_started"})

                @_listen(CrewKickoffCompletedEvent)
                def _cc(source: Any, event: Any) -> None:
                    outer._append({"type": "crew_done"})

                @_listen(CrewKickoffFailedEvent)
                def _cf(source: Any, event: Any) -> None:
                    outer._append({"type": "crew_failed", "text": str(event)[:500]})

                @_listen(TaskStartedEvent)
                def _ts(source: Any, event: Any) -> None:
                    task = getattr(event, "task", None)
                    desc = getattr(task, "description", str(event)[:200])
                    outer._append({"type": "task_started", "text": str(desc)[:200]})

                @_listen(TaskCompletedEvent)
                def _tc(source: Any, event: Any) -> None:
                    task = getattr(event, "task", None)
                    out = getattr(task, "output", None)
                    outer._append({"type": "task_done", "text": str(out)[-500:]})

                @_listen(TaskFailedEvent)
                def _tf(source: Any, event: Any) -> None:
                    outer._append({"type": "task_failed", "text": str(event)[:500]})

                @_listen(AgentExecutionStartedEvent)
                def _as(source: Any, event: Any) -> None:
                    name = _agent_name(getattr(event, "agent", None) or source)
                    outer._append({"type": "agent_started", "agent": name, "pane": pane_for(name)})

                @_listen(AgentExecutionCompletedEvent)
                def _ac(source: Any, event: Any) -> None:
                    name = _agent_name(getattr(event, "agent", None) or source)
                    outer._append({"type": "agent_done", "agent": name, "pane": pane_for(name)})

                @_listen(AgentExecutionErrorEvent)
                def _ae(source: Any, event: Any) -> None:
                    name = _agent_name(getattr(event, "agent", None) or source)
                    outer._append({"type": "agent_error", "agent": name, "pane": pane_for(name), "text": str(event)[:500]})

                @_listen(LLMCallStartedEvent)
                def _ls(source: Any, event: Any) -> None:
                    outer._append({"type": "llm_started"})

                @_listen(LLMCallFailedEvent)
                def _lf(source: Any, event: Any) -> None:
                    outer._append({"type": "llm_failed", "text": str(getattr(event, "error", event))[:300]})

                @_listen(LLMStreamChunkEvent)
                def _chunk(source: Any, event: Any) -> None:
                    outer._append({"type": "chunk", "text": str(getattr(event, "chunk", ""))[:2000]})

        self._impl = _L()
        # validate_dependencies may complain without tracing config; ignore
        try:
            crewai_event_bus.validate_dependencies()
        except Exception:
            pass

    def teardown(self) -> None:
        """Unregister this listener from the global bus (012 T15).

        Without this, every flow in a long autonomous loop leaves its handlers
        registered, so events leak into old run dirs and memory grows.
        """
        try:
            from crewai.events import crewai_event_bus
        except Exception:
            self._handlers.clear()
            return
        for event_type, handler in self._handlers:
            try:
                crewai_event_bus.off(event_type, handler)
            except Exception:
                pass
        self._handlers.clear()

    def _append(self, payload: dict[str, Any]) -> None:
        self.events.put(payload)
        try:
            with (self.run_dir / "events.jsonl").open("a") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception:
            pass
