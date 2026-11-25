"""Per-run usage accounting (012 T11/T14).

Tokens come from CrewAI's `CrewOutput.token_usage`; cost is derived from a tiny
price table. Local Ollama and `:free` models are exactly $0. A paid model with
no known price yields `None` (unknown) instead of a fake number.
"""

from __future__ import annotations

import os

# USD per 1M tokens: (input, output). Only models we have actually measured or
# seen priced belong here; everything else is "unknown" rather than guessed.
PRICES_USD_PER_M: dict[str, tuple[float, float]] = {
    # Zen balance billing, re-measured 2026-11-09 against `usage.cost` from the
    # gateway (reasoning tokens are billed as output): 169 in / 35 out = $4.285e-05
    # → $0.15/M in, $0.50/M out. The earlier (0.10, 0.30) under-reported by ~50%.
    "zen/glm-5.3-flash": (0.15, 0.50),
    "zen/deepseek-v4.1-flash": (0.25, 1.00),
    # OpenCode Go subscription (console pricing, 2026-11-15). DeepSeek V4.1
    # Flash is peak/off-peak; the peak rate is used so a cap never under-reads.
    "opencode-go/glm-5.3-flash": (0.15, 0.50),
    "opencode-go/deepseek-v4.1-flash": (0.30, 1.20),
    "opencode-go/qwen3.8-flash": (0.15, 0.47),
    "opencode-go/minimax-m3.1-flash": (0.15, 0.60),
    "opencode-go/kimi-k2.7-code": (0.95, 4.00),
    "opencode-go/glm-5.3": (1.40, 4.40),
    # Read from the Go catalogue (`/models`, 2026-11-22). DeepSeek V4 Pro doubles
    # on weekday peaks (01:00-04:00, 06:00-10:00 UTC): the peak rate is stored so
    # a per-task cap never under-reads. hy4-flash-free is a $0 tier.
    "opencode-go/mimo-v2.6-flash": (0.14, 0.28),
    "opencode-go/deepseek-v4-pro": (1.32, 3.96),
    "opencode-go/claude-haiku-5-5": (0.10, 0.50),
    "opencode-go/hy4-flash-free": (0.0, 0.0),
    # OpenRouter list price (2026-11-14). The planner uses this id because the
    # free Nvidia planner 503s on its safety screener; an unknown price would
    # silently disable the per-task cost cap.
    "openrouter/deepseek/deepseek-v4.1-flash-1017": (0.038, 0.50),
    "openrouter/~deepseek/deepseek-v4-flash-latest": (0.0434, 0.30),
}


def _rate(model: str) -> tuple[float, float] | None:
    """Price lookup tolerant of CrewAI stripping the routing prefix."""
    if model in PRICES_USD_PER_M:
        return PRICES_USD_PER_M[model]
    for prefix in ("opencode-go/", "zen/", "openrouter/"):
        if prefix + model in PRICES_USD_PER_M:
            return PRICES_USD_PER_M[prefix + model]
    return None


def is_free(model: str) -> bool:
    """047: delegate to the one predicate in swarm.model_config."""
    from swarm.model_config import is_free as _is_free

    return _is_free(model)


def estimate_cost(per_model: dict[str, tuple[int, int]]) -> float | None:
    """`{model: (prompt_tokens, completion_tokens)}` → USD, or None if unknown."""
    total = 0.0
    for model, (prompt, completion) in per_model.items():
        if is_free(model):
            continue
        rate = _rate(model)
        if rate is None:
            return None
        total += prompt / 1_000_000 * rate[0] + completion / 1_000_000 * rate[1]
    return round(total, 6)


def unpriced_models(per_model: dict[str, tuple[int, int]]) -> list[str]:
    """Paid models the price table cannot price (the reason cost is unknown).

    026 AC-7: an unpriced model must be named. `None` cost is honest but silent —
    it also disables the per-task dollar cap, and a run record that says
    `cost: null` without the model makes that impossible to diagnose.
    """
    return sorted(
        {model for model in (per_model or {}) if not is_free(model) and _rate(model) is None}
    )


def estimate_run_cost(
    models: list[str], prompt_tokens: int, completion_tokens: int
) -> float | None:
    """Cost for an aggregated run when attribution is unambiguous.

    All-free → 0.0. Exactly one paid model among free ones → priced with all
    tokens attributed to it (slight over-estimate). Multiple paid models → None.
    """
    paid = [m for m in models if not is_free(m)]
    if not paid:
        return 0.0
    if len(set(paid)) != 1:
        return None
    rate = _rate(paid[0])
    if rate is None:
        return None
    total = prompt_tokens / 1_000_000 * rate[0] + completion_tokens / 1_000_000 * rate[1]
    return round(total, 6)


def budget_note(
    *,
    total_tokens: int,
    cost_usd: float | None,
    elapsed_seconds: float,
    max_tokens: int,
    max_cost_usd: float,
    max_seconds: int,
) -> str:
    """Human-readable reason when a budget is exceeded; '' when within budget."""
    if max_tokens > 0 and total_tokens > max_tokens:
        return f"token budget exceeded: {total_tokens} > {max_tokens}"
    if max_cost_usd > 0 and cost_usd is not None and cost_usd > max_cost_usd:
        return f"cost budget exceeded: ${cost_usd:.4f} > ${max_cost_usd:.4f}"
    if max_seconds > 0 and elapsed_seconds > max_seconds:
        return f"time budget exceeded: {elapsed_seconds:.0f}s > {max_seconds}s"
    return ""


def env_int(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
