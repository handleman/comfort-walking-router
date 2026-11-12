"""Outcome replay suite (021 T1, AC-1).

020's offline bench measures prompt characters. This measures what a harness
change does to *outcomes*: does a frozen case still reach green, how long does it
take, how many tokens and fix rounds does it cost. It is the number 022
(parallelism) and 023 (earned autonomy) have to move.

Each case runs through the 020 T7 live path (`live.run_case`): a throwaway
worktree at `green_sha^`, the current harness, pinned models, no commit. The
suite is opt-in (models required) and never part of `make swarm-test`.

    make swarm-replay                 # selected cases, compare to the baseline
    make swarm-replay-off             # same cases with every 021 knob at its 020 value
    make swarm-replay-one CASE=<id>   # one case, details printed
    python -m swarm.bench.replay --baseline   # snapshot the first run
"""

from __future__ import annotations

import datetime as dt
import json
import os
import statistics
from pathlib import Path
from typing import Any

from swarm.bench import corpus, live

REPO_ROOT = corpus.REPO_ROOT
BASELINE = Path(__file__).resolve().parent / "replay_baseline.json"

# One case per verified area, small enough to keep a suite under ~45 minutes.
# 004-weather-sun-T2 is the case the 020 T8 replay failed on; it stays in the
# set because it is the loop's current worst case, not because it is easy.
DEFAULT_CASES: tuple[str, ...] = (
    "004-weather-sun-T2",
    "005-saved-routes-T2",
    "006-comfort-plus-T3",
    "007-live-position-T2",
    "010-e2e-playwright-T5",
)

# Every 021 behaviour has a 020 value. This is the off side of the A/B: setting
# these makes the suite measure the loop as it was before 021.
OFF_ENV: dict[str, str] = {
    "SWARM_STYLE_PRE_QA": "0",
    "SWARM_TESTS_FIRST": "0",
    "SWARM_CODER_ACS": "0",
}


def selected_cases(env: dict[str, str] | None = None) -> tuple[str, ...]:
    """`SWARM_REPLAY_CASES` (`case,case`) overrides the default suite."""
    source = os.environ if env is None else env
    raw = str(source.get("SWARM_REPLAY_CASES", "")).strip()
    if not raw:
        return DEFAULT_CASES
    picked = tuple(part.strip() for part in raw.replace("\n", ",").split(",") if part.strip())
    return picked or DEFAULT_CASES


def off_env(off: bool) -> dict[str, str]:
    """The env overrides for the old-loop side of the A/B."""
    return dict(OFF_ENV) if off else {}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-case results. Green is a count, never an average."""
    durations = [int(r.get("duration_seconds") or 0) for r in rows if r.get("ok")]
    greens = [r for r in rows if r.get("ok")]
    return {
        "cases": len(rows),
        "green": len(greens),
        "green_rate": round(100 * len(greens) / len(rows), 1) if rows else 0.0,
        "duration_p50": int(statistics.median(durations)) if durations else 0,
        "duration_total": sum(int(r.get("duration_seconds") or 0) for r in rows),
        "prompt_tokens": sum(int(r.get("prompt_tokens") or 0) for r in rows),
        "cached_prompt_tokens": sum(int(r.get("cached_prompt_tokens") or 0) for r in rows),
        "cost_usd": round(sum(float(r.get("cost_usd") or 0.0) for r in rows), 4),
        "fix_rounds": sum(int(r.get("fix_rounds") or 0) for r in rows),
    }


def run_suite(
    cases: list[str] | tuple[str, ...] | None = None,
    *,
    repo: Path = REPO_ROOT,
    off: bool = False,
    runner: Any = None,
    timeout: int = live.DEFAULT_TIMEOUT_SECONDS,
    keep_failures: bool = False,
    on_row: Any = None,
) -> dict[str, Any]:
    """Run every case sequentially; return the rows and their aggregate.

    `runner` is injectable so the suite's bookkeeping is testable without a
    model. The real runner is `live.run_case`.
    """
    chosen = list(cases or selected_cases())
    run = runner or (lambda case, **kw: live.run_case(case, **kw))
    overrides = off_env(off)
    rows: list[dict[str, Any]] = []
    for case in chosen:
        try:
            result = run(
                case,
                repo=repo,
                env_overrides=overrides,
                timeout=timeout,
                keep_on_failure=keep_failures,
            )
        except (OSError, RuntimeError, ValueError, KeyError) as exc:  # a measurement, not a gate
            result = {"ok": False, "case": case, "error": f"{type(exc).__name__}: {exc}"}
        rows.append(_row(case, result))
        print(f"  {case}: {'green' if rows[-1]['ok'] else rows[-1]['status']}", flush=True)
        if on_row is not None:
            on_row(
                {
                    "created": dt.datetime.now().isoformat(timespec="seconds"),
                    "off": bool(off),
                    "cases": chosen,
                    "rows": rows,
                    "totals": summarize(rows),
                }
            )
    return {
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "off": bool(off),
        "cases": chosen,
        "rows": rows,
        "totals": summarize(rows),
    }


def _row(case: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "case": case,
        "ok": bool(result.get("ok")),
        "status": result.get("status") or ("green" if result.get("ok") else "failed"),
        "error": result.get("error") or result.get("reason_code") or "",
        "duration_seconds": int(result.get("duration_seconds") or 0),
        "prompt_tokens": int(result.get("prompt_tokens") or 0),
        "cached_prompt_tokens": int(result.get("cached_prompt_tokens") or 0),
        "cost_usd": float(result.get("cost_usd") or 0.0),
        "fix_rounds": int(result.get("fix_rounds") or 0),
        "gates": sorted((result.get("gates") or {}).keys()),
        "changed_files": list(result.get("changed_files") or []),
    }


def compare(baseline: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-case green/time/token delta against the committed baseline."""
    before = {row["case"]: row for row in baseline.get("rows") or []}
    out: list[dict[str, Any]] = []
    for row in current.get("rows") or []:
        old = before.get(row["case"]) or {}
        out.append(
            {
                "case": row["case"],
                "green_before": bool(old.get("ok")),
                "green_after": bool(row["ok"]),
                "duration_delta": int(row["duration_seconds"]) - int(old.get("duration_seconds") or 0),
                "tokens_delta": int(row["prompt_tokens"]) - int(old.get("prompt_tokens") or 0),
                "fix_rounds_delta": int(row["fix_rounds"]) - int(old.get("fix_rounds") or 0),
            }
        )
    return out


def render(suite: dict[str, Any], baseline: dict[str, Any] | None = None) -> str:
    totals = suite["totals"]
    lines = [
        f"replay suite: {totals['cases']} cases"
        + (" (021 knobs off)" if suite.get("off") else ""),
        f"{'case':<28}{'status':<14}{'time':>7}{'tokens':>10}{'fix':>5}{'cached':>9}",
        "-" * 75,
    ]
    for row in suite["rows"]:
        status = "green" if row["ok"] else (row["status"] or "failed")
        lines.append(
            f"{row['case']:<28}{status:<14}{row['duration_seconds']:>6}s"
            f"{row['prompt_tokens']:>10,}{row['fix_rounds']:>5}{row['cached_prompt_tokens']:>9,}"
        )
    lines.append(
        f"\ntotals: green {totals['green']}/{totals['cases']} ({totals['green_rate']}%), "
        f"p50 {totals['duration_p50']}s, {totals['prompt_tokens']:,} prompt tokens "
        f"({totals['cached_prompt_tokens']:,} cached), ${totals['cost_usd']:.4f}, "
        f"{totals['fix_rounds']} fix rounds"
    )
    if baseline:
        base = baseline.get("totals") or {}
        lines.append(
            f"baseline: green {base.get('green')}/{base.get('cases')}, "
            f"p50 {base.get('duration_p50')}s, {base.get('prompt_tokens', 0):,} tokens, "
            f"{base.get('fix_rounds')} fix rounds"
        )
        for delta in compare(baseline, suite):
            flag = "" if delta["green_before"] == delta["green_after"] else "  <-- green changed"
            lines.append(
                f"  {delta['case']:<28} time {delta['duration_delta']:+6d}s "
                f"tokens {delta['tokens_delta']:+9,d} fix {delta['fix_rounds_delta']:+d}{flag}"
            )
    return "\n".join(lines)


def load_baseline(path: Path = BASELINE) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def write_baseline(path: Path, suite: dict[str, Any], repo: Path = REPO_ROOT) -> None:
    payload = dict(suite)
    payload["commit"] = live._git(repo, "rev-parse", "HEAD")[1].strip() or None
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="swarm.bench.replay", description="outcome replay suite")
    parser.add_argument("--repo", default=str(REPO_ROOT))
    parser.add_argument("--case", default="", help="run one case")
    parser.add_argument("--cases", default="", help="comma-separated case ids")
    parser.add_argument("--off", action="store_true", help="every 021 knob at its 020 value")
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--keep", action="store_true", help="keep failed worktrees for inspection")
    args = parser.parse_args(argv)
    repo = Path(args.repo)
    cases = [args.case] if args.case else (
        [c.strip() for c in args.cases.split(",") if c.strip()] or list(selected_cases())
    )
    partial = Path(__file__).resolve().parent / "replay_last.json"

    def save_partial(snapshot: dict[str, Any]) -> None:
        partial.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")

    suite = run_suite(
        cases,
        repo=repo,
        off=args.off,
        keep_failures=args.keep,
        on_row=save_partial,
    )
    if args.update_baseline:
        write_baseline(BASELINE, suite, repo=repo)
        print(f"replay baseline written: {BASELINE}")
    if args.json:
        print(json.dumps(suite, indent=2, sort_keys=True))
        return 0
    baseline = {} if args.update_baseline else load_baseline()
    print(render(suite, baseline or None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
