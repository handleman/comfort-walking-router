"""Offline scoring for the replay corpus (020 T1, AC-1).

The score is computed from text only: build the same CrewAI crew objects the
flow builds, read their `role`/`goal`/`backstory`/`description`/tool text, and
render the QA report through `evidence`. No model is called and nothing is
written, so a prompt or gate change is measured against frozen input.

The task-level number is an estimate of what one replay of the case costs in
prompt characters:

    steps  × step prompt
  + qa rounds × QA prompt          (fix_rounds + 1)
  + fix rounds × fix prompt        (only when the run had fix rounds)
  + 1 × verifier prompt            (019 is in the loop)

It is an estimate, not a token count: it deliberately excludes model output and
provider overhead so it stays stable and comparable. `run.json` remains the
source of truth for what a real run cost.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Prompt text is model-independent, but crew construction needs *an* LLM and a
# clean checkout has no keys. Force a local model for the duration of a build.
BENCH_ENV = {
    "SWARM_PLANNER_MODEL": "ollama/bench",
    "SWARM_CODER_MODEL": "ollama/bench",
    "SWARM_REVIEWER_MODEL": "ollama/bench",
    "SWARM_SENIOR_MODEL": "ollama/bench",
    "SWARM_VERIFIER_MODEL": "ollama/bench",
    "SWARM_ALLOW_PAID": "0",
}


@contextlib.contextmanager
def bench_env() -> Iterator[None]:
    saved = {key: os.environ.get(key) for key in BENCH_ENV}
    os.environ.update(BENCH_ENV)
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def crew_prompt(crew: Any) -> str:
    """The text a provider sees for one crew: agent block + task block + tools."""
    agent = crew.agents[0]
    task = crew.tasks[0]
    parts = [
        str(getattr(agent, "role", "") or ""),
        str(getattr(agent, "goal", "") or ""),
        str(getattr(agent, "backstory", "") or ""),
        str(getattr(task, "description", "") or ""),
        str(getattr(task, "expected_output", "") or ""),
    ]
    for tool in getattr(agent, "tools", None) or []:
        parts.append(str(getattr(tool, "description", "") or getattr(tool, "name", "") or ""))
    return "\n".join(parts)


def _spec_task(case: dict[str, Any]):
    from swarm.spec_loader import SpecTask

    return SpecTask(
        id=str(case.get("task") or "T1"),
        ac_refs=tuple(case.get("ac_refs") or ()),
        brief=str(case.get("brief") or ""),
    )


def prompts(case: dict[str, Any]) -> dict[str, int | str]:
    """Prompt characters for one step, one QA round, one fix round, one verify.

    Also records the stable-prefix hash (020 AC-2): a change that silently
    reassembles the head of the prompt shows up as a different prefix instead of
    a mystery in the character count.
    """
    from swarm.crew import (
        build_fix_crew,
        build_review_crew,
        build_step_crew,
        build_verify_crew,
    )
    from swarm.prompts import prompt_prefix

    task = _spec_task(case)
    spec = str(case.get("spec") or "")
    steps = list(case.get("steps") or [])
    first_step = steps[0] if steps else "Implement the task."
    with bench_env():
        step = crew_prompt(build_step_crew(spec, task, first_step, 1, max(1, len(steps))))
        qa = crew_prompt(build_review_crew(spec, task, _work_summary(case)))
        fix = crew_prompt(build_fix_crew(spec, task, report_fixture_text(case)[0]))
        verify = crew_prompt(build_verify_crew(spec, task, _verify_context(case)))
    prefix_text, prefix_hash = prompt_prefix(task, spec, "step")
    return {
        "step_prompt_chars": len(step),
        "qa_prompt_chars": len(qa),
        "fix_prompt_chars": len(fix),
        "verify_prompt_chars": len(verify),
        "prefix_chars": len(prefix_text),
        "prefix_sha256": prefix_hash,
    }


def _work_summary(case: dict[str, Any]) -> str:
    """What QA sees after the steps: the compacted step digest (020 T4).

    Writes to a temporary directory, never to the repository: the bench stays
    read-only. `SWARM_CONTEXT_COMPACT=0` restores the old full concatenation so
    the two behaviours can be measured with the same command.
    """
    import tempfile
    from pathlib import Path as _Path

    from swarm import compaction

    steps = list(case.get("steps") or [])
    with tempfile.TemporaryDirectory() as tmp:
        digest, _ = compaction.compact_steps(
            steps, _Path(tmp), enabled_flag=compaction.enabled()
        )
    return digest[:6000]


def _verify_context(case: dict[str, Any]) -> str:
    """A 019-shaped scenario context, reconstructed from the frozen case."""
    parts = ["## ACs"] + list(case.get("ac_text") or [])
    parts += ["## Plan"] + list(case.get("plan_text") or [])
    parts += ["## Files"]
    for entry in case.get("files") or []:
        parts.append(f"### {entry.get('path')}")
        parts.append(str(entry.get("content") or ""))
    return "\n".join(parts)[:60_000]


def report_fixture(case: dict[str, Any]) -> dict[str, Any]:
    """The QA report object for the frozen failing round."""
    from swarm.bench.corpus import failing_gate
    from swarm.evidence import qa_report, split_tails

    failing = failing_gate(case)
    gates = {str(k): int(v) for k, v in (case.get("gates") or {}).items()}
    gates[failing] = 1
    return qa_report(
        gates=gates,
        tails=split_tails(str(case.get("report_fixture") or "")),
        changed=list(case.get("changed") or []),
        verdict="fail",
        reason="the frozen failing round for report measurement",
    )


def report_fixture_text(case: dict[str, Any]) -> tuple[str, int]:
    """Render the report (with 020 T4 spilling) once; return (text, chars)."""
    import tempfile
    from pathlib import Path as _Path

    from swarm import compaction
    from swarm.evidence import report_text

    report = report_fixture(case)
    with tempfile.TemporaryDirectory() as tmp:
        report, _ = compaction.spill_report(
            report, _Path(tmp), enabled_flag=compaction.enabled()
        )
        text = report_text(report)
    return text, len(text)


def score_case(case: dict[str, Any]) -> dict[str, Any]:
    p = prompts(case)
    text, report_chars = report_fixture_text(case)
    steps = max(1, len(case.get("steps") or []))
    fix_rounds = int((case.get("recorded") or {}).get("fix_rounds") or 0)
    qa_rounds = fix_rounds + 1
    task_chars = (
        steps * p["step_prompt_chars"]
        + qa_rounds * p["qa_prompt_chars"]
        + fix_rounds * p["fix_prompt_chars"]
        + p["verify_prompt_chars"]
    )
    gates = [g for g in (case.get("gates") or {}) if g != "scope"]
    return {
        "id": str(case.get("id") or ""),
        "steps": steps,
        "fix_rounds": fix_rounds,
        "gates_per_round": len(gates),
        **p,
        "report_chars": report_chars,
        "task_prompt_chars": task_chars,
        "est_tokens": task_chars // 4,
        "report_sha256": hashlib.sha256(text.encode()).hexdigest()[:16],
    }


def score(cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [score_case(case) for case in cases]
    totals = {
        "cases": len(rows),
        "task_prompt_chars": sum(r["task_prompt_chars"] for r in rows),
        "report_chars": sum(r["report_chars"] for r in rows),
        "est_tokens": sum(r["est_tokens"] for r in rows),
        "gates_per_round": sum(r["gates_per_round"] for r in rows),
    }
    if rows:
        totals["mean_task_prompt_chars"] = totals["task_prompt_chars"] // len(rows)
        totals["mean_report_chars"] = totals["report_chars"] // len(rows)
    from swarm.bench.corpus import corpus_digest

    return {"cases": {r["id"]: r for r in rows}, "totals": totals, "corpus_digest": corpus_digest(cases)}


def compare(baseline: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-case delta on the two numbers 020 promises to move."""
    out: list[dict[str, Any]] = []
    base_cases = baseline.get("cases") or {}
    for cid, row in (current.get("cases") or {}).items():
        before = base_cases.get(cid)
        if not before:
            out.append({"id": cid, "before": None, "after": row, "task_delta_pct": None, "report_delta_pct": None})
            continue
        out.append(
            {
                "id": cid,
                "before": before,
                "after": row,
                "task_delta_pct": _pct(before.get("task_prompt_chars"), row.get("task_prompt_chars")),
                "report_delta_pct": _pct(before.get("report_chars"), row.get("report_chars")),
                "gates_delta": int(row.get("gates_per_round", 0)) - int(before.get("gates_per_round", 0)),
            }
        )
    return out


def _pct(before: Any, after: Any) -> float | None:
    try:
        b = float(before or 0)
        a = float(after or 0)
    except (TypeError, ValueError):
        return None
    if b <= 0:
        return None
    return round((a - b) / b * 100, 1)


def render_table(rows: list[dict[str, Any]], *, title: str = "bench") -> str:
    header = f"{'case':<28}{'task chars':>12}{'Δ task':>9}{'report':>9}{'Δ report':>10}{'gates':>7}"
    lines = [f"{title}: {len(rows)} cases", header, "-" * len(header)]
    for row in rows:
        after = row["after"]
        before = row.get("before") or {}
        task = int(after.get("task_prompt_chars") or 0)
        rep = int(after.get("report_chars") or 0)
        dt = row.get("task_delta_pct")
        dr = row.get("report_delta_pct")
        lines.append(
            f"{row['id']:<28}{task:>12,}"
            f"{(f'{dt:+.1f}%' if dt is not None else '—'):>9}"
            f"{rep:>9,}"
            f"{(f'{dr:+.1f}%' if dr is not None else '—'):>10}"
            f"{int(after.get('gates_per_round') or 0):>7}"
        )
        if before and row.get("gates_delta"):
            lines[-1] += f"  (gates {row['gates_delta']:+d})"
    return "\n".join(lines)


def load_baseline(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def write_baseline(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
