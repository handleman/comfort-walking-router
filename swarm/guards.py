"""Deterministic guards around model phases (026).

The first guard is the delta guard. Two 014-T10 runs spent 21 and 28 minutes,
produced `changed: []`, and then paid a verifier to tell us the files the brief
named were missing. 007-T10 and 014-T2 are the same shape: the module exists but
nothing mounts it.

The check is deliberately cheap and model-free:

* an empty in-scope delta is `no_delta`;
* a named path that does not exist before the run and is still absent is
  `delta_incomplete` (a *create* deliverable that was not created);
* a named path that already existed and was not touched is recorded as
  `untouched` but does not stop the run — briefs also name files for context,
  and the verifier still judges whether an update was required.

The other guards in this module are the cheap policies the flow applies around
a judge or a correction:

* `resolve_verdict` — parse a judge's answer, make **one** bounded repair call,
  then stop. A verdict the parser could not read is never a pass (014-T10
  committed green on an `unknown`).
* `correction_regressions` — a correction step that turns a green static check
  red cannot land (014-T11 appended a duplicate style block to `App.svelte`).
* `note_quota` — quota errors are counted per provider and a wall is terminal
  instead of a retry loop (54 `429 free-models-per-day` errors on 014-T10).

Every guard has an off switch; each one stops with a typed reason code and none
of them can make a green run red.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Container, Iterable, Mapping
from pathlib import Path
from typing import Any

DISABLE_ENV = "SWARM_DELTA_GUARD"
JUDGE_ENV = "SWARM_JUDGE_FAIL_CLOSED"
CORRECTION_ENV = "SWARM_CORRECTION_GUARD"
QUOTA_ENV = "SWARM_QUOTA_BREAKER"
QUOTA_LIMIT_ENV = "SWARM_QUOTA_LIMIT"
DEFAULT_QUOTA_LIMIT = 3

VALID_VERDICTS = frozenset({"pass", "blocked"})


def _on(name: str, env: Mapping[str, str] | None = None) -> bool:
    source: Mapping[str, str] = os.environ if env is None else env
    return str(source.get(name, "1")).strip().lower() not in {"0", "false", "no"}


def enabled(env: Mapping[str, str] | None = None) -> bool:
    return _on(DISABLE_ENV, env)


# ---------------------------------------------------------------------------
# T2: judges fail closed
# ---------------------------------------------------------------------------


def judge_fail_closed(env: Mapping[str, str] | None = None) -> bool:
    """True unless the fail-closed judge rule is switched off.

    `SWARM_JUDGE_FAIL_CLOSED=0` restores the 019-era behaviour where an
    unparseable verdict was advisory (and the verifier's `unknown` fell through
    as a pass). It exists for an A/B, not for normal operation.
    """
    return _on(JUDGE_ENV, env)


def resolve_verdict(
    *,
    kind: str,
    first_text: str,
    parse: Callable[[str], tuple[str, list[str]]],
    repair: Callable[[], str | None] | None = None,
) -> dict[str, Any]:
    """Parse → one bounded repair → terminal (AC-3).

    Returns `{kind, verdict, findings, repaired, terminal, raw}`. `terminal` is
    True only when the answer is still unparseable after the single repair, and
    the caller must then stop instead of reading `unknown` as anything close to
    a pass. `raw` is the tail of the text the parser actually read, so a run
    record can show what the model said.
    """
    verdict, findings = parse(first_text or "")
    record: dict[str, Any] = {
        "kind": kind,
        "verdict": verdict,
        "findings": findings,
        "repaired": False,
        "terminal": False,
        "raw": str(first_text or "")[-2000:],
    }
    if verdict in VALID_VERDICTS:
        return record
    if not judge_fail_closed():
        return record
    if repair is not None:
        record["repaired"] = True
        try:
            out = repair()
        except Exception as e:  # noqa: BLE001 - a failed repair is still terminal
            record["repair_error"] = f"{type(e).__name__}: {e}"[:500]
            out = None
        if out is not None:
            verdict, findings = parse(str(out))
            record["raw"] = str(out)[-2000:]
            record["verdict"] = verdict
            record["findings"] = findings
            if verdict in VALID_VERDICTS:
                return record
    record["terminal"] = True
    return record


# ---------------------------------------------------------------------------
# T3: a correction cannot regress the build
# ---------------------------------------------------------------------------


def correction_guard(env: Mapping[str, str] | None = None) -> bool:
    return _on(CORRECTION_ENV, env)


def correction_regressions(
    before: Mapping[str, int],
    after: Mapping[str, int],
) -> list[str]:
    """Checks that were green before a correction and are red after it.

    Only a green→red transition counts: a check that was already red is not the
    correction's fault, and a check that does not appear in `after` keeps its
    previous code (it was not run, so it cannot be called a regression).
    """
    regressed: list[str] = []
    for command, code in (before or {}).items():
        try:
            was_green = int(code) == 0
            now = int(after.get(command, code))
        except (TypeError, ValueError):
            continue
        if was_green and now != 0:
            regressed.append(str(command))
    return sorted(regressed)


# ---------------------------------------------------------------------------
# T4: quota is counted per provider and terminal
# ---------------------------------------------------------------------------


def quota_breaker(env: Mapping[str, str] | None = None) -> bool:
    return _on(QUOTA_ENV, env)


def quota_limit(env: Mapping[str, str] | None = None) -> int:
    source: Mapping[str, str] = os.environ if env is None else env
    try:
        value = int(str(source.get(QUOTA_LIMIT_ENV, DEFAULT_QUOTA_LIMIT)))
    except (TypeError, ValueError):
        value = DEFAULT_QUOTA_LIMIT
    return max(1, value)


def note_quota(
    hits: dict[str, int],
    provider: str,
    limit: int,
) -> bool:
    """Count one quota error for `provider`; True when the breaker should trip."""
    key = provider or "unknown"
    hits[key] = int(hits.get(key, 0)) + 1
    return hits[key] >= max(1, limit)


# 053 AC-3: files a task may write without being its own deliverable. A
# dependency install (`npm install`) touching a lockfile is not an off-scope
# product edit, and reverting it would break the build that just passed.
_ALWAYS_ALLOWED = frozenset(
    {
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "uv.lock",
        "poetry.lock",
        "requirements.txt",
        "requirements-dev.txt",
    }
)


def task_allowlist(brief: str, steps: Iterable[str] = ()) -> set[str]:
    """053 AC-3: the files this task may write (empty set = no restriction).

    Derived from the brief's *ownership* paths (+ the plan's step targets) and
    their parent directories, so a coder can add a sibling file but not wander
    into another area. On 2026-11-25 T23's coder edited
    `frontend/e2e/helpers.ts`, which flipped `e2e_required` on a map task and
    made a green map unreachable; the global scope (`frontend/`) was too coarse
    to catch it.
    """
    from swarm import evidence as _ev
    from swarm.prompts import brief_paths

    allow: set[str] = set()
    for text in [brief, *steps]:
        if not text:
            continue
        for path in brief_paths(str(text)):
            if path.startswith("specs/") or _ev.is_referenced(str(text), path):
                continue
            allow.add(path)
            parent = path.rsplit("/", 1)[0] if "/" in path else ""
            if parent:
                allow.add(parent + "/")
    return allow


def allowlist_violations(changed: Iterable[str], allow: Container[str]) -> list[str]:
    """Writes outside the task's own allowlist (053 AC-3); empty allow = none."""
    if not allow:
        return []
    bad: list[str] = []
    for raw in changed:
        path = str(raw).replace("\\", "/").strip()
        if not path or path in _ALWAYS_ALLOWED:
            continue
        if any(path == entry or path.startswith(entry) for entry in allow):
            continue
        bad.append(path)
    return bad


def summary_of(record: Mapping[str, Any]) -> str:
    """One line for `human_log.txt` for any guard record."""
    if "reason" in record:
        return summary(record)
    return ""


# ---------------------------------------------------------------------------
# T1: the delta guard
# ---------------------------------------------------------------------------


def delta_record(
    brief: str,
    changed: Iterable[str],
    repo_root: Path,
    *,
    expected: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Describe this run's delta against the files the brief names.

    `changed` must be the run's in-scope delta (not the whole dirty tree): an
    operator edit is not the coder's work and must not make a run look complete.
    """
    from swarm.prompts import brief_paths

    touched = sorted({str(path).strip() for path in changed if str(path).strip()})
    # A brief names files the coder must change *and* may reference spec files
    # for context. The coder never writes `specs/` (the swarm must not edit the
    # roster), so a path there can never be a missing deliverable — 028-T3 was
    # stopped for "plan.md" after a complete contract change (2026-11-15).
    if expected is not None:
        # A replay compares against the corpus's recorded delta: a historical
        # brief can name a file that did not exist yet at that base commit, and
        # the frozen case is the evidence of what a green run actually changed
        # (007-T2 stopped here on 2026-11-16).
        named = sorted({str(path).strip() for path in expected if str(path).strip()})
    else:
        from swarm import evidence as _ev

        # 053 AC-2: a bare filename that does not exist at the repo root is
        # shorthand for a reference ("... already in `helpers.ts`"), not a
        # deliverable. Only directory-qualified (or existing root) paths can be
        # `missing`; and a purely referenced path is never required.
        named = [
            path
            for path in brief_paths(brief)
            if not path.startswith("specs/")
            and ("/" in path or (repo_root / path).exists())
            and not _ev.is_referenced(brief, path)
        ]
    missing = [
        path for path in named if path not in touched and not (repo_root / path).exists()
    ]
    untouched = [
        path for path in named if path not in touched and (repo_root / path).exists()
    ]
    if not touched:
        reason = "no_delta"
    elif missing:
        reason = "delta_incomplete"
    else:
        reason = ""
    return {
        "reason": reason,
        "changed": touched,
        "named": named,
        "missing": missing,
        "untouched": untouched,
    }


def summary(record: Mapping[str, Any]) -> str:
    """One line for `human_log.txt` / the terminal."""
    reason = record.get("reason") or "ok"
    if reason == "no_delta":
        return "delta guard: the coding phase produced no in-scope change"
    if reason == "delta_incomplete":
        missing = ", ".join(record.get("missing") or [])
        return f"delta guard: brief-named files were not created: {missing}"
    untouched = record.get("untouched") or []
    tail = f" (named but untouched: {', '.join(untouched)})" if untouched else ""
    return f"delta guard: ok — {len(record.get('changed') or [])} changed path(s){tail}"
