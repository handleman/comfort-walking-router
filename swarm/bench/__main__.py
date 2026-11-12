"""`python -m swarm.bench` — offline replay bench (020 T1, AC-1).

    make swarm-bench                 score the committed corpus against baseline.json
    make swarm-bench-build           rebuild the corpus from git history
    make swarm-bench-baseline        snapshot the current score as the baseline

The bench never calls a model, never writes to the repository outside
`swarm/bench/`, and never mutates git. A nonzero exit means the corpus cannot
be trusted (missing case, digest changed): rebuild it and update the baseline
on purpose, not by accident.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from swarm.bench import corpus, score

BENCH_DIR = Path(__file__).resolve().parent
BASELINE = BENCH_DIR / "baseline.json"


def build(repo: Path) -> int:
    cases, rejected = corpus.select(repo)
    if rejected:
        print("rejected cases:", file=sys.stderr)
        for reason in rejected:
            print(f"  - {reason}", file=sys.stderr)
    if not cases:
        print("no corpus cases built", file=sys.stderr)
        return 2
    written = corpus.write_corpus(repo, cases)
    print(f"built {len(cases)} cases → {written[0].parent.relative_to(repo)}")
    if rejected:
        print("corpus is incomplete: fix the rejected cases or remove them from DEFAULT_CASES", file=sys.stderr)
        return 2
    print("next: make swarm-bench-baseline (snapshot before changing the harness)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="swarm.bench", description="offline replay bench")
    parser.add_argument("--repo", default=str(corpus.REPO_ROOT), help="repository root")
    parser.add_argument("--build", action="store_true", help="rebuild the corpus from git history")
    parser.add_argument("--update-baseline", action="store_true", help="snapshot the current score")
    parser.add_argument("--case", default="", help="score one case id")
    parser.add_argument("--json", action="store_true", help="print the score payload")
    parser.add_argument("--list", action="store_true", help="list corpus cases and exit")
    parser.add_argument("--live", default="", help="live replay of one case in a throwaway worktree")
    parser.add_argument("--cases", default="", help="comma-separated spec/Tn list for --build")
    args = parser.parse_args(argv)
    repo = Path(args.repo)

    if args.build:
        if args.cases:
            import os

            os.environ["SWARM_BENCH_CASES"] = args.cases
        return build(repo)

    if args.live:
        from swarm.bench import live

        result = live.run_case(args.live, repo=repo)
        print(live.render(result))
        if not result.get("ok"):
            print(json.dumps(result, indent=2, sort_keys=True), file=sys.stderr)
        return 0 if result.get("ok") else 1

    try:
        cases = corpus.load_corpus(repo)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not cases:
        print("no corpus: run `make swarm-bench-build` first", file=sys.stderr)
        return 1
    if args.case:
        cases = [case for case in cases if case.get("id") == args.case]
        if not cases:
            print(f"unknown case: {args.case}", file=sys.stderr)
            return 1
    if args.list:
        for case in cases:
            print(f"{case['id']:<28} {case['run']:<28} {case['green_sha'][:8]}")
        return 0

    current = score.score(cases)
    if args.json:
        print(json.dumps(current, indent=2, sort_keys=True))
        return 0

    baseline = score.load_baseline(BASELINE)
    if args.update_baseline:
        payload = {
            "schema": corpus.SCHEMA,
            "created": dt.datetime.now().isoformat(timespec="seconds"),
            "corpus_digest": current["corpus_digest"],
            "cases": current["cases"],
            "totals": current["totals"],
            "note": "pre-change snapshot: 020 T1, before prompts/compaction/gate selection",
        }
        score.write_baseline(BASELINE, payload)
        print(f"baseline written: {BASELINE.relative_to(repo)} ({len(current['cases'])} cases)")
        return 0

    rows = score.compare(baseline, current) if baseline else [
        {"id": cid, "before": None, "after": row, "task_delta_pct": None, "report_delta_pct": None}
        for cid, row in current["cases"].items()
    ]
    print(score.render_table(rows))
    totals = current["totals"]
    print(
        f"\ntotals: {totals['cases']} cases, task prompt {totals['task_prompt_chars']:,} chars "
        f"(~{totals['est_tokens']:,} tokens), report {totals['report_chars']:,} chars, "
        f"{totals['gates_per_round']} gate runs/round"
    )

    if not baseline:
        print("\nno baseline.json yet: review the table, then `make swarm-bench-baseline`")
        return 0
    if baseline.get("corpus_digest") != current["corpus_digest"]:
        print(
            "\ncorpus digest changed: the frozen cases do not match the baseline. "
            "Rebuild deliberately and re-snapshot (`--update-baseline`).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
