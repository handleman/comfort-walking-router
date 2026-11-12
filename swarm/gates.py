"""Test-impact gate selection (020 T5, AC-4).

A frontend-only delta does not need `pytest`, and a Python delta does not need
`svelte-check`; running the whole suite in every fix round is the slowest part
of the loop (p50 7 min, p90 28 min). Selection is an *inner-loop* optimisation
only:

- the first QA round and the round that can make the run green always run the
  full suite;
- a fix round runs the commands the changed paths can affect;
- an unmapped path selects **everything** (fail-open): a new area must never
  get a narrower gate set by accident.

QA stays the only gate executor. Selection changes which commands QA is asked
to run; evidence and green are still derived from the recorded executions.

Mapping syntax (`SWARM_GATE_MAP`, newline separated):

    app/**=pytest -q;ruff check .;mypy app tests
    frontend/**=npm --prefix frontend run check;npm --prefix frontend run lint

`SWARM_GATE_SELECT=0` disables selection (always the full suite).
"""

from __future__ import annotations

import fnmatch
import os

# Sensible defaults for this repo (overridable with SWARM_GATE_MAP). Paths not
# covered here select every command: fail-open is the safe direction.
DEFAULT_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("app/**", ("pytest -q", "ruff check .", "mypy app tests")),
    ("tests/**", ("pytest -q", "ruff check .", "mypy app tests")),
    ("contracts/**", ("pytest -q",)),
    (
        "frontend/**",
        (
            "npm --prefix frontend run check",
            "npm --prefix frontend run lint",
            "npm --prefix frontend test -- --run",
        ),
    ),
)


def enabled(env: dict[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return str(source.get("SWARM_GATE_SELECT", "1")).strip().lower() not in {"0", "false", "no"}


def parse_map(raw: str) -> list[tuple[str, list[str]]]:
    """`glob=cmd;cmd` lines → [(glob, [cmd, ...]), ...]; blank lines ignored."""
    out: list[tuple[str, list[str]]] = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        glob, _, commands = line.partition("=")
        glob = glob.strip()
        parsed = [c.strip() for c in commands.split(";") if c.strip()]
        if glob and parsed:
            out.append((glob, parsed))
    return out


def gate_map(env: dict[str, str] | None = None) -> list[tuple[str, list[str]]]:
    """The configured map: `SWARM_GATE_MAP`, else this repo's default."""
    source = os.environ if env is None else env
    raw = source.get("SWARM_GATE_MAP", "")
    parsed = parse_map(raw)
    if parsed:
        return parsed
    return [(glob, list(commands)) for glob, commands in DEFAULT_MAP]


def _match(path: str, glob: str) -> bool:
    norm = path.replace("\\", "/").lstrip("./")
    return fnmatch.fnmatch(norm, glob) or fnmatch.fnmatch(norm, glob.rstrip("*").rstrip("/"))


def select_gates(
    changed: list[str],
    commands: list[str],
    *,
    mapping: list[tuple[str, list[str]]] | None = None,
    enabled_flag: bool | None = None,
) -> tuple[list[str], list[str]]:
    """(selected, skipped) for this delta. Unmapped paths select every command."""
    on = enabled() if enabled_flag is None else enabled_flag
    full = list(commands)
    if not on or not changed:
        return full, []

    rules = gate_map() if mapping is None else mapping
    selected: list[str] = []
    for path in changed:
        hits = [(glob, cmds) for glob, cmds in rules if _match(path, glob)]
        if not hits:
            # Fail-open: an unknown area is a reason to run everything, never a
            # reason to run less.
            return full, []
        for _, cmds in hits:
            for command in cmds:
                if command in full and command not in selected:
                    selected.append(command)
    if not selected:
        return full, []
    # Keep the configured order, so the report reads the same way every round.
    selected = [command for command in full if command in selected]
    skipped = [command for command in full if command not in selected]
    return selected, skipped


def record(mode: str, selected: list[str], skipped: list[str], gates: dict[str, int] | None = None) -> dict:
    """The `run.json.gate_selection` object for one round."""
    out = {"mode": mode, "selected": list(selected), "skipped": list(skipped)}
    if gates is not None:
        out["affected_gates" if mode == "affected" else "full_gates"] = dict(gates)
    return out
