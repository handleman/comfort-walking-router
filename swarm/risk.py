"""Risk labels for recorded runs (024).

The swarm is autonomous: a green, gated, verifier-passed run merges. There is no
autonomy switch and no risk ceiling to configure, so this module is
*measurement*, not policy. Every run carries a label, and `make swarm-report`
turns later reverts into an escape rate per label (`docs/risk-classes.md`).

| class | paths |
| --- | --- |
| 0 | docs/**, *.md |
| 1 | tests/**, frontend/e2e/** |
| 2 | app/**, frontend/src/**, contracts/** |
| 3 | swarm/**, specs/**, migrations, auth/payments/infra, config, unknown, empty |

Conservative by construction: an empty or unrecognised delta is class 3, never
class 0, so the measurement never flatters the autonomous path.
"""

from __future__ import annotations

from typing import Any

CLASS_LABELS = {
    0: "docs",
    1: "tests",
    2: "logic",
    3: "control",
}

# Any of these is control-plane or sensitive.
_CLASS_3 = (
    "swarm/",
    "specs/",
    ".github/",
    "docker/",
    "requirements",
    "pyproject.toml",
    "app/auth",
    "auth",
    "migrations",
    "payments",
    "secrets",
    "infra",
)
_CLASS_2 = ("app/", "frontend/src/", "frontend/lib/", "contracts/")
_CLASS_1 = ("tests/", "frontend/e2e/", "e2e/")


def classify(changed: list[str], brief: str = "") -> int:
    """0 docs, 1 tests, 2 logic, 3 control/unknown. Unknown is always 3."""
    paths = [str(path).replace("\\", "/").lstrip("./") for path in changed or []]
    if not paths:
        return 3
    text = (brief or "").lower()
    if any(marker in text for marker in ("auth", "payment", "migration", "infra", "secret")):
        return 3
    if any(path.startswith(prefix) for path in paths for prefix in _CLASS_3):
        return 3
    if any("migrations" in path or "/auth/" in path or path.endswith("/auth.py") for path in paths):
        return 3
    if any(path == "pyproject.toml" or path.startswith("requirements") for path in paths):
        return 3
    if all(path.startswith("docs/") or path.endswith(".md") for path in paths):
        return 0
    if all(path.startswith(_CLASS_1) for path in paths):
        return 1
    if all(path.startswith(_CLASS_2) for path in paths):
        return 2
    return 3


def label(cls: int) -> str:
    return CLASS_LABELS.get(int(cls), "unknown")


def record(changed: list[str], brief: str = "") -> dict[str, Any]:
    """The risk label this run carries in `run.json.risk` (telemetry only)."""
    cls = classify(changed, brief)
    return {"class": cls, "label": label(cls)}
