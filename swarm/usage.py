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
    # Zen balance billing, measured 2026-11-08 (small calls, rounded up).
    "zen/glm-5.3-flash": (0.10, 0.30),
    "zen/deepseek-v4.1-flash": (0.25, 1.00),
}


def is_free(model: str) -> bool:
    return (
        model.startswith("ollama/")
        or ":free" in model
        or model.endswith("-free")
        or "contributor-free" in model
    )


def estimate_cost(per_model: dict[str, tuple[int, int]]) -> float | None:
    """`{model: (prompt_tokens, completion_tokens)}` → USD, or None if unknown."""
    total = 0.0
    for model, (prompt, completion) in per_model.items():
        if is_free(model):
            continue
        rate = PRICES_USD_PER_M.get(model)
        if rate is None:
            return None
        total += prompt / 1_000_000 * rate[0] + completion / 1_000_000 * rate[1]
    return round(total, 6)


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
    rate = PRICES_USD_PER_M.get(paid[0])
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
