"""Frozen replay corpus for harness changes (020 T1, AC-1).

A case is one historical green run reduced to what a prompt and a report are
built from: the brief, the acceptance criteria it references, the plan lines
that name its files, the delta file contents at the green commit, the recorded
gate results and a bounded gate transcript. Nothing here calls a model, writes
to the repository or mutates git: the corpus is data, and `score.py` measures it.

Why frozen: 86 historical runs are evidence about the past but not a baseline
for a harness change — the tasks, models and repo state all differ. A picked
case is pinned by run id, green SHA and a per-file content hash, so a prompt or
gate change can be A/B'd against the same input twice.

Cases are rejected on purpose when the commit does not touch a file the brief
names (the 014-T2 lesson: a green commit that never mounted the endpoint). The
corpus is about prompt economics, but replaying a case whose scenario is known
to be wrong would make a live replay meaningless.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BENCH_DIR = REPO_ROOT / "swarm" / "bench"
CORPUS_DIR = BENCH_DIR / "corpus"

SCHEMA = 1
MAX_FILE_CHARS = 40_000
MAX_CASE_CHARS = 90_000
MAX_TRANSCRIPT_CHARS = 12_000
MAX_STEPS = 8
REPORT_FIXTURE_CHARS = 3_000

# A deliberate, documented selection: one or two cases per spec, spanning the
# backend, contracts, migrations, API, frontend libs, e2e and a multi-file
# wiring task. Cases the 019 investigation flags as green-but-wrong
# (014 T2/T7/T8) are excluded by construction: their commits do not do what
# the brief says, so they cannot replay green.
DEFAULT_CASES: tuple[tuple[str, str, str], ...] = (
    ("001-example-app", "T8", "python: comfort scorer + tests"),
    ("004-weather-sun", "T2", "python: auto preference rule"),
    ("004-weather-sun", "T4", "python: multi-file wiring into /route"),
    ("005-saved-routes", "T2", "sql: up/down migrations (many files)"),
    ("005-saved-routes", "T6", "python: saved-routes API endpoints"),
    ("006-comfort-plus", "T3", "contract + scoring: two new factors"),
    ("007-live-position", "T2", "frontend lib + vitest: snap"),
    ("007-live-position", "T6", "frontend store + component"),
    ("008-mapbox-routing", "T4", "python: five-file provider injection"),
    ("010-e2e-playwright", "T2", "python: fixtures mode"),
    ("010-e2e-playwright", "T5", "e2e: walk-mode scenario"),
    ("014-walk-guidance-ux", "T4", "frontend: map icons"),
)

_TRAILER_RE = re.compile(r"^Swarm-Task:\s*(\S+)/(T\d+)\s*$", re.MULTILINE)
_BACKTICK_PATH_RE = re.compile(r"`([A-Za-z0-9_./-]+\.[A-Za-z0-9]+)`")
_BARE_PATH_RE = re.compile(r"(?<![\w/`])((?:app|tests|frontend|contracts|docs|swarm)/[\w./-]+\.[A-Za-z0-9]+)")


@dataclass(frozen=True)
class CaseRef:
    spec: str
    task: str
    reason: str

    @property
    def id(self) -> str:
        return f"{self.spec}-{self.task}"


def case_id(spec: str, task: str) -> str:
    return f"{spec}-{task}".replace("/", "-")


def git(repo: Path, *args: str) -> tuple[int, str]:
    """Run git read-only; never raises (a shallow clone is a bench problem)."""
    try:
        p = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return p.returncode, p.stdout


def brief_paths(brief: str) -> list[str]:
    """Paths the brief names, in first-mention order, de-duplicated.

    Briefs use both shapes: a backticked path and a bare `app/main.py`. Only
    things that look like files are kept; a directory is not evidence that the
    commit did the work.
    """
    found: list[str] = []
    for match in _BACKTICK_PATH_RE.finditer(brief or ""):
        found.append(match.group(1))
    for match in _BARE_PATH_RE.finditer(brief or ""):
        found.append(match.group(1))
    out: list[str] = []
    seen: set[str] = set()
    for raw in found:
        path = raw.removeprefix("./").strip()
        if not path or path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def green_commits(repo: Path) -> dict[str, str]:
    """`<spec-dir>/<task>` → commit SHA, newest first, from the ledger trailers.

    Trailers written before the queue learned to canonicalise carry the
    invocation prefix (`Swarm-Task: 007/T6`), so the key is normalised exactly
    as `done.py` does it — otherwise a green task looks missing (007-T5).
    """
    from swarm.spec_loader import spec_dir_name

    rc, out = git(repo, "log", "-n800", "--format=%H%x00%B%x00", "--grep=Swarm-Task:")
    if rc != 0:
        return {}
    blocks = out.split("\0")
    entries: dict[str, str] = {}
    index = 0
    while index + 1 < len(blocks):
        sha = blocks[index].strip()
        body = blocks[index + 1]
        match = _TRAILER_RE.search(body)
        if sha and match:
            key = f"{spec_dir_name(repo, match.group(1))}/{match.group(2)}"
            entries.setdefault(key, sha)
        index += 2
    return entries


def commit_files(repo: Path, sha: str) -> list[str]:
    rc, out = git(repo, "show", "--name-only", "--format=", sha)
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def blob(repo: Path, sha: str, path: str) -> str | None:
    rc, out = git(repo, "show", f"{sha}:{path}")
    return out if rc == 0 else None


def _read_run(run_dir: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads((run_dir / "run.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def find_run(runs_dir: Path, spec: str, task: str, sha: str) -> Path | None:
    """Newest green run whose recorded spec/task and commit match the case.

    `run.json` is authoritative for which task a run was (the 007-T4 trap: a
    queue prefix can differ from the spec dir name). A run that cannot name its
    commit is still usable when it is the only candidate: the SHA comes from the
    trailer, not from the run.
    """
    from swarm.spec_loader import spec_dir_name

    repo = runs_dir.parent.parent
    best: Path | None = None
    for path in sorted(runs_dir.iterdir(), reverse=True):
        if not path.is_dir() or not path.name[:1].isdigit():
            continue
        payload = _read_run(path)
        if not payload or payload.get("status") != "green":
            continue
        if payload.get("task") != task:
            continue
        if spec_dir_name(repo, str(payload.get("spec") or "")) != spec:
            continue
        recorded = str((payload.get("done") or {}).get("green_sha") or "")
        if recorded and recorded != sha:
            continue
        if best is None:
            best = path
    return best


def _bounded_content(repo: Path, sha: str, path: str, budget: list[int]) -> dict[str, Any] | None:
    text = blob(repo, sha, path)
    if text is None:
        return None
    chars = len(text)
    digest = hashlib.sha256(text.encode()).hexdigest()
    if budget[0] <= 0:
        return {"path": path, "sha256": digest, "chars": chars, "content": "", "omitted": True}
    allowed = min(MAX_FILE_CHARS, budget[0])
    kept = text[:allowed]
    budget[0] -= len(kept)
    return {
        "path": path,
        "sha256": digest,
        "chars": chars,
        "content": kept,
        "truncated": len(kept) < chars,
    }


def _spec_artifacts(repo: Path, sha: str, spec: str) -> tuple[str, str]:
    """`spec.md` and `plan.md` as the run saw them (green commit, then worktree)."""
    spec_text = blob(repo, sha, f"specs/{spec}/spec.md")
    plan_text = blob(repo, sha, f"specs/{spec}/plan.md")
    for name, current in (("spec", spec_text), ("plan", plan_text)):
        if current is None:
            try:
                fallback = (REPO_ROOT / "specs" / spec / f"{name}.md").read_text()
            except OSError:
                fallback = ""
            if name == "spec":
                spec_text = fallback
            else:
                plan_text = fallback
    return spec_text or "", plan_text or ""


def step_fixture(changed: list[str], task: str, ac_refs: list[str]) -> list[str]:
    """One micro-step per changed file, capped like the planner's budget.

    The planner's own step text is not recorded in `run.json`, so the fixture is
    generated from the delta: it keeps the per-step *overhead* (role, goal,
    backstory, rules, tools) measurable and frozen. T2 changes the assembly, not
    this fixture, so before/after stays comparable.
    """
    acs = ",".join(ac_refs) or "the task"
    steps = [f"Edit `{path}` — satisfy {task} ({acs}) per the plan." for path in changed]
    if not steps:
        steps = [f"Implement {task} ({acs}) per the plan."]
    return steps[:MAX_STEPS]


def failing_gate(case: dict[str, Any]) -> str:
    """The gate the frozen failing round marks red.

    Chosen lexicographically so it does not depend on dict order: the corpus is
    written with sorted keys, and a build-time and score-time choice must agree.
    """
    gates = dict(case.get("gates") or {})
    commands = sorted(c for c in gates if c != "scope") or ["pytest -q"]
    return commands[-1]


def failing_transcript(case: dict[str, Any]) -> str:
    """A deterministic failing round for the report measurement.

    Green runs have no failing tail, but the fix report is exactly what 020
    shrinks. The fixture marks the last gate red and gives it a bounded,
    realistic body: the recorded transcript when it names that gate, otherwise
    a pseudo-log built from the case's first file. The fixture is stored in the
    corpus, so the same report input is measured before and after.
    """
    gates: dict[str, int] = dict(case.get("gates") or {})
    failing = failing_gate(case)
    recorded = str(case.get("transcript") or "")
    body = ""
    for block in recorded.split("$ ")[1:]:
        head, _, rest = block.partition("\n")
        if head.strip() == failing:
            body = rest
            break
    if len(body.strip()) < 800:
        # The recorded tail of a green run is short (or the gate passed). The
        # report is measured against the size a real failure produces.
        files = list(case.get("files") or [])
        path = str((files[0] or {}).get("path") or "app/main.py") if files else "app/main.py"
        body = "\n".join(
            [
                *("  " + "trace detail " * 12 for _ in range(150)),
                f"{path}:12: error: expected value, found no implementation",
                *(
                    f"{path}:{line}: note: context line {line}"
                    for line in range(13, 13 + 12)
                ),
            ]
        )
    body = body[-REPORT_FIXTURE_CHARS:]
    commands = [c for c in gates if c != "scope"] or [failing]
    blocks = [f"$ {command}\nexit=0\n(clean)" for command in commands if command != failing]
    blocks.append(f"$ {failing}\nexit=1\n{body}")
    return "\n".join(blocks)[:MAX_TRANSCRIPT_CHARS]


def build_case(repo: Path, spec: str, task: str, sha: str, run_dir: Path) -> dict[str, Any]:
    run = _read_run(run_dir) or {}
    brief = str(run.get("brief") or "")
    ac_refs = [str(a) for a in (run.get("ac_refs") or [])]
    touched = commit_files(repo, sha)
    named = brief_paths(brief)
    changed = sorted(set(named) & set(touched)) or sorted(touched)
    spec_md, plan_md = _spec_artifacts(repo, sha, spec)

    budget = [MAX_CASE_CHARS]
    files = []
    for path in changed:
        entry = _bounded_content(repo, sha, path, budget)
        if entry is not None:
            files.append(entry)

    gates = {str(k): int(v) for k, v in (run.get("evidence", {}).get("gates") or {}).items()}
    usage = run.get("usage") or {}
    case: dict[str, Any] = {
        "id": case_id(spec, task),
        "schema": SCHEMA,
        "run": run_dir.name,
        "spec": spec,
        "task": task,
        "green_sha": sha,
        "base_sha": f"{sha}^",
        "brief": brief,
        "ac_refs": ac_refs,
        "ac_text": _ac_paragraphs(spec_md, ac_refs),
        "plan_text": _plan_lines(plan_md, task, changed),
        "steps": step_fixture(changed, task, ac_refs),
        "changed": changed,
        "files": files,
        "gates": gates,
        "transcript": str(run.get("gate_transcript_tail") or "")[:MAX_TRANSCRIPT_CHARS],
        "recorded": {
            "status": run.get("status"),
            "fix_rounds": int(run.get("fix_rounds") or 0),
            "duration_seconds": int(usage.get("duration_seconds") or 0),
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "cost_usd": float(run.get("cost") or 0.0),
        },
    }
    case["report_fixture"] = failing_transcript(case)
    return case


def _ac_paragraphs(spec_md: str, ac_refs: list[str]) -> list[str]:
    from swarm.verify import ac_paragraphs

    return ac_paragraphs(spec_md, ac_refs)


def _plan_lines(plan_md: str, task: str, changed: list[str]) -> list[str]:
    from swarm.spec_loader import SpecTask
    from swarm.verify import plan_lines

    probe = SpecTask(id=task, ac_refs=(), brief="")
    return plan_lines(plan_md, probe, changed)


def corpus_digest(cases: list[dict[str, Any]]) -> str:
    """Stable hash of exactly the inputs a replay depends on."""
    payload = [
        {
            "id": case["id"],
            "sha": case["green_sha"],
            "files": [[f["path"], f["sha256"]] for f in case.get("files") or []],
            "brief": case.get("brief"),
            "ac_refs": case.get("ac_refs"),
        }
        for case in sorted(cases, key=lambda c: c["id"])
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def case_digest(case: dict[str, Any]) -> str:
    payload = [
        case.get("id"),
        case.get("green_sha"),
        [[f["path"], f["sha256"]] for f in case.get("files") or []],
        case.get("brief"),
        case.get("gates"),
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def select(repo: Path, cases: tuple[tuple[str, str, str], ...] = DEFAULT_CASES) -> tuple[list[dict[str, Any]], list[str]]:
    """Build the default corpus; return (cases, rejected reasons)."""
    commits = green_commits(repo)
    runs_dir = repo / "swarm" / "runs"
    built: list[dict[str, Any]] = []
    rejected: list[str] = []
    for spec, task, reason in cases:
        sha = commits.get(f"{spec}/{task}")
        if not sha:
            rejected.append(f"{spec}/{task}: no Swarm-Task trailer found")
            continue
        run_dir = find_run(runs_dir, spec, task, sha)
        if run_dir is None:
            rejected.append(f"{spec}/{task}: no green run.json")
            continue
        case = build_case(repo, spec, task, sha, run_dir)
        named = set(brief_paths(case["brief"]))
        touched = set(commit_files(repo, sha))
        if not (named & touched):
            rejected.append(
                f"{spec}/{task}: commit {sha[:8]} touches none of the files the brief names "
                f"({reason})"
            )
            continue
        case["reason"] = reason
        built.append(case)
    return built, rejected


def write_corpus(repo: Path, cases: list[dict[str, Any]]) -> list[Path]:
    """Write one JSON per case; the corpus is committed, not generated at test time."""
    out_dir = repo / "swarm" / "bench" / "corpus"
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    keep = {f"{case['id']}.json" for case in cases}
    for stale in out_dir.glob("*.json"):
        if stale.name not in keep:
            stale.unlink()
    for case in cases:
        path = out_dir / f"{case['id']}.json"
        path.write_text(json.dumps(case, indent=2, sort_keys=True) + "\n")
        written.append(path)
    return written


def load_corpus(repo: Path) -> list[dict[str, Any]]:
    out_dir = repo / "swarm" / "bench" / "corpus"
    cases: list[dict[str, Any]] = []
    for path in sorted(out_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"unreadable corpus case {path}: {exc}") from exc
        if isinstance(payload, dict):
            payload["_path"] = str(path)
            cases.append(payload)
    return cases
