"""Risk classes for earned autonomy (024).

The credible dark-factory pattern is a ladder, not a switch: low-risk changes
may merge after the machine gates, high-risk changes wait for a human. This
module is the minimal classifier the harness needs:

| class | paths | merge |
| --- | --- | --- |
| 0 | docs/**, *.md | auto after gates + verifier (when autonomy is on) |
| 1 | tests/**, frontend/e2e/** | auto after gates + verifier |
| 2 | app/**, frontend/src/**, contracts/** | human |
| 3 | swarm/**, specs/**, migrations, auth/payments/infra, unknown | human |

Conservative by construction: an empty or unrecognised delta is class 3, never
class 0. The class is recorded in `run.json.autonomy` next to the auto-merge
decision, so an escape-rate ratio can be computed later.
"""

from __future__ import annotations

CLASS_LABELS = {
    0: "docs",
    1: "tests",
    2: "logic",
    3: "control",
}

# 024: any of these is control-plane or sensitive: never auto-merged.
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


def decision(
    *,
    changed: list[str],
    brief: str,
    gates: dict[str, int] | None,
    review_verdict: str,
    verifier_blocked: bool,
    autonomy: bool,
    max_class: int,
) -> dict:
    """The auto-merge decision for `run.json.autonomy`."""
    cls = classify(changed, brief)
    gates_green = bool(gates) and all(int(code) == 0 for code in gates.values())
    basis = {
        "class": cls,
        "label": label(cls),
        "gates_green": gates_green,
        "review_verdict": review_verdict,
        "verifier_blocked": verifier_blocked,
    }
    allowed = bool(
        autonomy
        and cls <= int(max_class)
        and gates_green
        and str(review_verdict).lower() == "pass"
        and not verifier_blocked
    )
    basis["auto_merge"] = allowed
    if not autonomy:
        basis["reason"] = "autonomy off"
    elif cls > int(max_class):
        basis["reason"] = f"class {cls} > max {max_class}"
    elif not gates_green:
        basis["reason"] = "gates not green"
    elif str(review_verdict).lower() != "pass":
        basis["reason"] = "reviewer did not pass"
    elif verifier_blocked:
        basis["reason"] = "scenario verifier blocked"
    else:
        basis["reason"] = "earned: low-risk class, gates + verifier green"
    return basis
