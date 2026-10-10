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

                @bus.on(CrewKickoffStartedEvent)
                def _cs(source: Any, event: Any) -> None:
                    outer._append({"type": "crew_started"})

                @bus.on(CrewKickoffCompletedEvent)
                def _cc(source: Any, event: Any) -> None:
                    outer._append({"type": "crew_done"})

                @bus.on(CrewKickoffFailedEvent)
                def _cf(source: Any, event: Any) -> None:
                    outer._append({"type": "crew_failed", "text": str(event)[:500]})

                @bus.on(TaskStartedEvent)
                def _ts(source: Any, event: Any) -> None:
                    task = getattr(event, "task", None)
                    desc = getattr(task, "description", str(event)[:200])
                    outer._append({"type": "task_started", "text": str(desc)[:200]})

                @bus.on(TaskCompletedEvent)
                def _tc(source: Any, event: Any) -> None:
                    task = getattr(event, "task", None)
                    out = getattr(task, "output", None)
                    outer._append({"type": "task_done", "text": str(out)[-500:]})

                @bus.on(TaskFailedEvent)
                def _tf(source: Any, event: Any) -> None:
                    outer._append({"type": "task_failed", "text": str(event)[:500]})

                @bus.on(AgentExecutionStartedEvent)
                def _as(source: Any, event: Any) -> None:
                    name = _agent_name(getattr(event, "agent", None) or source)
                    outer._append({"type": "agent_started", "agent": name, "pane": pane_for(name)})

                @bus.on(AgentExecutionCompletedEvent)
                def _ac(source: Any, event: Any) -> None:
                    name = _agent_name(getattr(event, "agent", None) or source)
                    outer._append({"type": "agent_done", "agent": name, "pane": pane_for(name)})

                @bus.on(AgentExecutionErrorEvent)
                def _ae(source: Any, event: Any) -> None:
                    name = _agent_name(getattr(event, "agent", None) or source)
                    outer._append({"type": "agent_error", "agent": name, "pane": pane_for(name), "text": str(event)[:500]})

                @bus.on(LLMCallStartedEvent)
                def _ls(source: Any, event: Any) -> None:
                    outer._append({"type": "llm_started"})

                @bus.on(LLMCallFailedEvent)
                def _lf(source: Any, event: Any) -> None:
                    outer._append({"type": "llm_failed", "text": str(getattr(event, "error", event))[:300]})

                @bus.on(LLMStreamChunkEvent)
                def _chunk(source: Any, event: Any) -> None:
                    outer._append({"type": "chunk", "text": str(getattr(event, "chunk", ""))[:2000]})

        self._impl = _L()
        # validate_dependencies may complain without tracing config; ignore
        try:
            crewai_event_bus.validate_dependencies()
        except Exception:
            pass

    def _append(self, payload: dict[str, Any]) -> None:
        self.events.put(payload)
        try:
            with (self.run_dir / "events.jsonl").open("a") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception:
            pass
