"""026 AC-6: one retry authority — the harness, not CrewAI's agent loop.

CrewAI retries inside the harness's own three attempts, so one provider outage
cost 20 LLM calls on 014-T10. Every agent is built with `max_retry_limit=0`; the
harness owns retries, backoff and typed stops.
"""

from __future__ import annotations

import inspect

from swarm import crew


def test_every_agent_disables_CrewAI_retries():
    source = inspect.getsource(crew)
    agents = source.count("Agent(")
    pinned = source.count("max_retry_limit=AGENT_RETRY_LIMIT")
    # 045 dedup consolidated two duplicated pairs (senior step/fix, merge/stash
    # resolvers) into shared factories, so the number of literal Agent(...)
    # construction sites dropped from 9 to 7. Every site must still pin the limit.
    assert agents >= 7
    assert pinned == agents, f"{agents - pinned} Agent(s) still let CrewAI retry"


def test_the_limit_is_zero():
    assert crew.AGENT_RETRY_LIMIT == 0
