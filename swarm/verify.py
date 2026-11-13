"""Scenario verifier (019): does the implemented scenario do what the brief says?

Green means *the gates passed* — a statement about the code that exists, not
about the task that was asked for. Six 014 tasks were committed green while
three of them did not do what their brief said (T2's `GET /geocode` was never
mounted, T7's client targeted an endpoint the contract does not define, T8
wired no selection) and T6/T9 never landed at all: a *missing* piece produces
no failing assertion, so every gate exits 0 and QA says PASS.

This module builds the one thing the loop never had: the whole scenario for a
single task — the brief, the acceptance criteria it references, the plan
lines that mention its files, the **full content** of every file in the run
delta and a best-effort import/imported-by view that makes a duplicate
implementation visible.

It is deliberate text, not a model: the harness composes the context, the
verifier crew answers `VERDICT: PASS|BLOCKED` with `FINDING:` lines and, when
blocked, a correction plan in the planner's own `STEP n:` format. The flow
executes that plan with the coder crews and verifies again. Nothing here runs
a gate or decides green — QA still owns the evidence.

The phase is bounded: `MAX_VERIFY_ROUNDS` (2), `MAX_VERIFY_FILES` (12),
`MAX_CONTEXT_CHARS` (60000) and the planner's `MAX_STEPS`, so a verifier can
never turn one task into an unbounded loop.
"""

from __future__ import annotations

import os
import posixpath
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

DISABLE_ENV = "SWARM_VERIFY"
READ_CHARS_ENV = "SWARM_VERIFY_READ_CHARS"
DEFAULT_READ_CHARS = 60000

# Rounds of *verification* (each may be followed by one correction pass).
MAX_VERIFY_ROUNDS = 2
MAX_VERIFY_FILES = 12
MAX_CONTEXT_CHARS = 60000
MAX_PLAN_LINES = 40
MAX_FINDINGS = 20
MAX_REPORT_CHARS = 14000

# ---------------------------------------------------------------------------
# knobs
# ---------------------------------------------------------------------------


def concurrent_enabled(env: Mapping[str, str] | None = None) -> bool:
    """022 AC-3: run the first read-only verifier pass with QA (default off)."""
    source: Mapping[str, str] = os.environ if env is None else env
    return str(source.get("SWARM_VERIFY_CONCURRENT", "0")).strip().lower() in {"1", "true", "yes"}


def enabled(env: Mapping[str, str] | None = None) -> bool:
    """True unless the phase is switched off (`SWARM_VERIFY=0`)."""
    source: Mapping[str, str] = os.environ if env is None else env
    return source.get(DISABLE_ENV, "1") != "0"


def read_chars(env: Mapping[str, str] | None = None) -> int:
    """Observation cap for the verifier's whole-file read (default 60000)."""
    source: Mapping[str, str] = os.environ if env is None else env
    raw = source.get(READ_CHARS_ENV, "").strip()
    try:
        value = int(raw) if raw else DEFAULT_READ_CHARS
    except ValueError:
        value = DEFAULT_READ_CHARS
    return max(1000, value)


def model_name(env: Mapping[str, str] | None = None) -> str:
    """The model the verifier will run: its own role, else the senior/free brain."""
    source: Mapping[str, str] = os.environ if env is None else env
    return (
        source.get("SWARM_VERIFIER_MODEL", "").strip()
        or source.get("SWARM_SENIOR_MODEL", "").strip()
        or "?"
    )


# ---------------------------------------------------------------------------
# the scenario: brief + ACs + plan lines
# ---------------------------------------------------------------------------

# Both shapes the specs use: `- **AC-1** — …` and `- [ ] AC-1: …`.
_AC_LINE_RE = re.compile(
    r"^\s*[-*]\s*(?:\[[ xX]\]\s*)?(?:\*\*)?(AC-\d+)(?:\*\*)?\s*[—:–-]?\s*(.*)$"
)


_FINDING_FILE_RE = re.compile(r"`?([\w./-]+\.(?:py|ts|tsx|js|jsx|svelte|json|sql|md))(?::\d+)?")


def finding_files(findings: list[str]) -> set[str]:
    """The files a finding names, for detecting a re-litigated round."""
    out: set[str] = set()
    for finding in findings or []:
        out.update(match.group(1) for match in _FINDING_FILE_RE.finditer(str(finding)))
    return out


def task_line(spec_dir: str, task_id: str) -> str:
    """The task's own queue line from `tasks.md` (its brief), or empty."""
    from swarm import prompts

    try:
        text = (prompts.REPO_ROOT / "specs" / spec_dir / "tasks.md").read_text()
    except OSError:
        return ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- [ ] ", "- [x] ")) and f" {task_id} " in stripped + " ":
            return stripped
    return ""


def ac_paragraphs(spec_md: str, ac_refs: Iterable[str]) -> list[str]:
    """The acceptance-criteria bullets the task references, continuation included.

    The specs wrap an AC over several lines; the verifier must see the whole
    paragraph, not the first sentence, or "the AC is addressed" becomes a
    question about a headline.
    """
    wanted = {ref.strip().upper() for ref in ac_refs if ref.strip()}
    if not wanted or not spec_md:
        return []
    lines = spec_md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        m = _AC_LINE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        ref = m.group(1).upper()
        parts = [lines[i].strip()]
        j = i + 1
        # Continuation lines are indented; a blank line or a new bullet ends it.
        while j < len(lines):
            nxt = lines[j]
            if not nxt.strip() or not nxt[:1].isspace():
                break
            parts.append(nxt.strip())
            j += 1
        if ref in wanted:
            out.append(" ".join(parts))
        i = max(j, i + 1)
    return out


def plan_lines(plan_md: str, task: Any, changed: Iterable[str]) -> list[str]:
    """Plan lines that mention a file of this task (best-effort section view)."""
    if not plan_md:
        return []
    needles = {str(path) for path in changed if path}
    needles |= {posixpath.basename(path) for path in changed if path}
    task_id = str(getattr(task, "id", "") or "")
    out: list[str] = []
    for line in plan_md.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        hit = any(needle and needle in stripped for needle in needles)
        if not hit and task_id:
            hit = re.search(rf"\b{re.escape(task_id)}\b", stripped) is not None
        if hit:
            out.append(stripped)
            if len(out) >= MAX_PLAN_LINES:
                break
    return out


# ---------------------------------------------------------------------------
# the connection view: a dependency-free static import scan
# ---------------------------------------------------------------------------

_SOURCE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".svelte")
_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "runs",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "coverage",
}
_MAX_SCAN_FILES = 4000

_PY_FROM_RE = re.compile(r"^\s*from\s+(\.*[\w.]*)\s+import\b", re.MULTILINE)
_PY_IMPORT_RE = re.compile(r"^\s*import\s+([\w.]+)", re.MULTILINE)
_JS_FROM_RE = re.compile(r"""\bfrom\s+['"]([^'"]+)['"]""")
_JS_REQUIRE_RE = re.compile(r"""\brequire\(\s*['"]([^'"]+)['"]\s*\)""")
_JS_DYNAMIC_RE = re.compile(r"""\bimport\(\s*['"]([^'"]+)['"]\s*\)""")

_JS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".svelte")


def _iter_sources(root: Path) -> Iterable[Path]:
    """Repo source files, pruning dependency/build trees and bounding the walk."""
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")
        )
        for name in sorted(filenames):
            if Path(name).suffix not in _SOURCE_SUFFIXES:
                continue
            yield Path(dirpath) / name
            count += 1
            if count >= _MAX_SCAN_FILES:
                return


def _js_candidates(spec: str, src_rel: str) -> list[str]:
    if spec.startswith("$lib/"):
        base = posixpath.join("frontend", "src", "lib", spec[len("$lib/") :])
    elif spec.startswith("."):
        base = posixpath.normpath(posixpath.join(posixpath.dirname(src_rel), spec))
    elif spec.startswith("src/"):
        base = spec
    else:
        return []  # a package, an alias, or a framework virtual module
    out = [base]
    out += [base + suffix for suffix in _JS_SUFFIXES]
    out += [posixpath.join(base, "index" + suffix) for suffix in _JS_SUFFIXES]
    return out


def _py_candidates(spec: str, src_rel: str) -> list[str]:
    if spec.startswith("."):
        dots = len(spec) - len(spec.lstrip("."))
        module = spec[dots:]
        base = posixpath.dirname(src_rel)
        for _ in range(max(0, dots - 1)):
            base = posixpath.dirname(base)
        stem = posixpath.join(base, module.replace(".", "/")) if module else base
    else:
        stem = spec.replace(".", "/")
    if not stem:
        return []
    return [stem + ".py", posixpath.join(stem, "__init__.py")]


def imports_of(root: Path, relative: str) -> list[str]:
    """Repo-relative paths a file imports (best-effort; [] when unreadable)."""
    target = root / relative
    try:
        text = target.read_text(errors="replace")
    except OSError:
        return []
    specifiers: list[str] = []
    candidates: list[str] = []
    if target.suffix == ".py":
        for match in _PY_FROM_RE.finditer(text):
            candidates += _py_candidates(match.group(1), relative)
        for match in _PY_IMPORT_RE.finditer(text):
            candidates += _py_candidates(match.group(1), relative)
    else:
        for regex in (_JS_FROM_RE, _JS_REQUIRE_RE, _JS_DYNAMIC_RE):
            specifiers += regex.findall(text)
        for spec in specifiers:
            candidates += _js_candidates(spec, relative)
    resolved: set[str] = set()
    for candidate in candidates:
        norm = posixpath.normpath(candidate)
        if norm.startswith(("../", "/")) or norm in ("", "."):
            continue
        if (root / norm).is_file():
            resolved.add(norm)
    resolved.discard(relative)
    return sorted(resolved)


def connections(root: Path, paths: Iterable[str]) -> dict[str, dict[str, list[str]]]:
    """For each delta file, what it imports and what imports it.

    A missing edge is a hint, not a proof: a dynamic import or a path alias
    will not appear here. It is what makes a duplicate implementation visible
    (007-T9 wrote `frontend/src/lib/navigation/walkMode.ts` next to the real
    `frontend/src/lib/walkMode.ts`) and a contract drift worth a second look.
    """
    root = Path(root)
    targets = sorted({str(p) for p in paths if p})
    view: dict[str, dict[str, list[str]]] = {
        path: {"imports": [], "imported_by": []} for path in targets
    }
    if not targets:
        return view
    wanted = set(targets)
    for path in targets:
        view[path]["imports"] = imports_of(root, path)
    for source in _iter_sources(root):
        rel = source.relative_to(root).as_posix()
        if rel in wanted:
            continue
        for imported in imports_of(root, rel):
            if imported in wanted:
                view[imported]["imported_by"].append(rel)
    for entry in view.values():
        entry["imported_by"] = sorted(set(entry["imported_by"]))
    return view


# ---------------------------------------------------------------------------
# the context bundle
# ---------------------------------------------------------------------------


def _read_text(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def scenario_context(
    repo_root: Path,
    spec_dir: str,
    task: Any,
    changed: Iterable[str],
) -> dict[str, Any]:
    """The whole scenario for one task, bounded by files and characters.

    `changed` is this run's in-scope delta (already attributed by the flow).
    Every file that fits is included *whole*; every file that does not is
    listed by name and size, never silently dropped.
    """
    from swarm.tools_guarded import is_secret_path

    root = Path(repo_root)
    spec_path = root / "specs" / spec_dir
    brief = str(getattr(task, "brief", "") or "")
    ac_refs = [str(ref) for ref in getattr(task, "ac_refs", ()) or ()]
    acs = ac_paragraphs(_read_text(spec_path / "spec.md"), ac_refs)
    plan = plan_lines(_read_text(spec_path / "plan.md"), task, changed)

    files: list[dict[str, Any]] = []
    included: list[str] = []
    skipped: list[dict[str, Any]] = []
    spent = 0
    seen: set[str] = set()
    for raw in changed:
        path = str(raw or "").replace("\\", "/").strip()
        if not path or path in seen or is_secret_path(path):
            continue
        seen.add(path)
        full = root / path
        if full.is_dir():
            skipped.append({"path": path, "chars": 0, "note": "directory"})
            continue
        try:
            content = full.read_text(errors="replace") if full.is_file() else ""
        except OSError:
            content = ""
        size = len(content)
        if not content:
            # A deleted or unreadable file is itself evidence, and it is cheap.
            files.append({"path": path, "content": "(deleted or unreadable)", "lines": 0})
            included.append(path)
            continue
        if len(included) >= MAX_VERIFY_FILES or spent + size > MAX_CONTEXT_CHARS:
            skipped.append({"path": path, "chars": size})
            continue
        spent += size
        files.append({"path": path, "content": content, "lines": content.count("\n") + 1})
        included.append(path)

    return {
        "spec": spec_dir,
        "task": str(getattr(task, "id", "") or ""),
        "ac_refs": ac_refs,
        "brief": brief,
        "acs": acs,
        "plan": plan,
        "files": included,
        "contents": files,
        "skipped": skipped,
        "connections": connections(root, included),
        "chars": spent,
    }


def render_context(context: Mapping[str, Any]) -> str:
    """The bounded prompt text the verifier crew reads."""
    lines: list[str] = []
    lines.append(f"spec={context.get('spec')} task={context.get('task')} "
                 f"ac={','.join(context.get('ac_refs') or [])}")
    lines += ["", "## TASK BRIEF", str(context.get("brief") or "")]
    acs = list(context.get("acs") or [])
    lines += ["", "## REFERENCED ACCEPTANCE CRITERIA"]
    lines += [f"- {ac}" for ac in acs] or ["(none referenced)"]
    plan = list(context.get("plan") or [])
    lines += ["", "## PLAN LINES FOR THIS TASK"]
    lines += [f"- {line}" for line in plan] or ["(no plan lines mention this task's files)"]

    contents = list(context.get("contents") or [])
    lines += [
        "",
        f"## RUN DELTA — FULL CONTENT ({len(contents)} file(s), whole files, not a head)",
    ]
    if not contents:
        lines.append("(the run changed no in-scope file)")
    for entry in contents:
        lines += [
            "",
            f"### {entry.get('path')} ({entry.get('lines')} lines)",
            "```",
            str(entry.get("content") or ""),
            "```",
        ]

    skipped = list(context.get("skipped") or [])
    if skipped:
        lines += ["", "## FILES NOT INCLUDED (too large or over the file budget)"]
        for entry in skipped:
            note = f" — {entry['note']}" if entry.get("note") else ""
            lines.append(f"- {entry.get('path')} ({entry.get('chars', 0)} chars){note}")

    links = context.get("connections") or {}
    lines += [
        "",
        "## CONNECTIONS (best-effort static scan; a missing edge is a hint, not a proof)",
    ]
    if not links:
        lines.append("(no delta files to connect)")
    for path, entry in links.items():
        lines.append(f"- {path}")
        lines.append("  imports: " + (", ".join(entry.get("imports") or []) or "(none found)"))
        lines.append(
            "  imported by: " + (", ".join(entry.get("imported_by") or []) or "(none found)")
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# the answer: verdict, findings, correction plan
# ---------------------------------------------------------------------------

_VERDICT_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?\s*VERDICT\s*:?\s*\**\s*(PASS|BLOCKED)\b",
    re.IGNORECASE | re.MULTILINE,
)
_FINDING_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?\s*FINDING\s*[:—–-]\s*(.+?)(?:\*\*)?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_verdict(text: str) -> tuple[str, list[str]]:
    """`("pass"|"blocked"|"unknown", findings)` from the verifier's answer."""
    body = text or ""
    hits = _VERDICT_RE.findall(body)
    verdict = hits[-1].lower() if hits else "unknown"
    findings = [m.group(1).strip() for m in _FINDING_RE.finditer(body) if m.group(1).strip()]
    return verdict, findings[:MAX_FINDINGS]


def parse_plan(text: str) -> list[str]:
    """Correction steps in the planner's own format (one definition of STEP_RE)."""
    from swarm.crew import MAX_STEPS, STEP_RE

    steps = [
        match.group(2).strip()
        for match in STEP_RE.finditer(text or "")
        if match.group(2).strip()
    ]
    return [step for step in steps if len(step) <= 500][:MAX_STEPS]


def render_report(
    context: Mapping[str, Any],
    findings: Iterable[str],
    plan: Iterable[str],
) -> str:
    """The bounded report the coder receives with the correction plan."""
    lines = ["SCENARIO VERIFIER: BLOCKED — the brief is not fully implemented."]
    lines.append(f"spec={context.get('spec')} task={context.get('task')}")
    brief = str(context.get("brief") or "").strip()
    if brief:
        lines.append(f"brief: {brief}")
    lines += ["", "findings:"]
    lines += [f"  - {finding}" for finding in findings] or ["  - (none)"]
    lines += ["", "correction plan (apply exactly; smallest coherent diff):"]
    lines += [f"  {step}" for step in plan] or ["  (none)"]
    changed = list(context.get("files") or [])
    if changed:
        lines += ["", "this run changed: " + ", ".join(changed)]
    return "\n".join(lines)[:MAX_REPORT_CHARS]
