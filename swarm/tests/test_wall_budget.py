"""Wall-budget tests (022 T2): stop between phases, never mid-call."""

from __future__ import annotations

import time
import types
from pathlib import Path

import pytest

from swarm import flow


def _stub(*, budget: int, started_ago: float) -> types.SimpleNamespace:
    stub = types.SimpleNamespace(
        state=types.SimpleNamespace(wall_budget_note=""),
        _wall_budget=budget,
        _task_started=time.monotonic() - started_ago,
    )
    stub._check_wall_budget = types.MethodType(flow.SwarmFlow._check_wall_budget, stub)
    return stub


def test_a_task_inside_the_budget_continues():
    _stub(budget=900, started_ago=10)._check_wall_budget("step 1")


def test_a_task_over_the_budget_raises_with_the_phase():
    stub = _stub(budget=10, started_ago=11)
    with pytest.raises(flow._WallBudget) as exc:
        stub._check_wall_budget("verifier")
    assert "verifier" in str(exc.value)
    assert stub.state.wall_budget_note


def test_zero_disables_the_budget():
    _stub(budget=0, started_ago=10_000)._check_wall_budget("qa")


def test_the_reason_code_is_machine_readable():
    state = types.SimpleNamespace(wall_budget_note="qa: 901s of 900s")
    assert flow._reason_code("needs_human", {"gates": {}}, state) == "wall_budget"


def test_the_budget_is_checked_before_every_crew_and_retry():
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert 'self._wall_budget = env_int("SWARM_TASK_WALL_BUDGET", 900)' in source
    assert 'self._check_wall_budget(role or "crew")' in source
    # the stop is terminal: it is re-raised, not retried
    assert "except (_BudgetExhausted, _WallBudget):" in source
    assert 'reason_code=wall_budget' in source or '"wall_budget"' in source


def test_the_human_log_names_the_phase():
    from swarm.humanlog import format_human_report

    payload = {
        "spec": "007-live-position",
        "task": "T2",
        "status": "needs_human",
        "reason_code": "wall_budget",
        "wall_budget_note": "qa: 901s of 900s",
    }
    text = format_human_report(payload, [])
    assert "wall budget: qa: 901s of 900s" in text


def test_each_agent_is_capped_at_the_remaining_wall_budget():
    stub = _stub(budget=900, started_ago=100)
    agents = [types.SimpleNamespace(max_execution_time=None) for _ in range(2)]
    crew = types.SimpleNamespace(agents=agents)
    stub._apply_wall_cap = types.MethodType(flow.SwarmFlow._apply_wall_cap, stub)
    stub._apply_wall_cap(crew)
    assert all(agent.max_execution_time is not None for agent in agents)
    assert all(5 <= agent.max_execution_time <= 900 for agent in agents)


def test_no_cap_without_a_budget():
    stub = _stub(budget=0, started_ago=10_000)
    agent = types.SimpleNamespace(max_execution_time=None)
    stub._apply_wall_cap = types.MethodType(flow.SwarmFlow._apply_wall_cap, stub)
    stub._apply_wall_cap(types.SimpleNamespace(agents=[agent]))
    assert agent.max_execution_time is None
