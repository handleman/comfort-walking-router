# 031 Dashboard Update — Plan

## Shape

Three touches to `swarm/tui.py`, one helper each, all exercised by unit tests
(the dashboard is hard to run headless, so the helpers are the testable seam):

```
short_model(model)           → strip `opencode-go/` too          (AC-1)
_status line                 → spec_dir_name(REPO_ROOT, spec)    (AC-2)
format_self_heal(payload)    → the 027 block or ""               (AC-3)
```

## Details

### AC-1 — the model label

```python
def short_model(model: str) -> str:
    for prefix in ("openrouter/", "zen/", "ollama/", "opencode-go/"):
        if model.startswith(prefix):
            model = model.removeprefix(prefix)
            break
    if len(model) > 30 and "/" in model:
        model = model.rsplit("/", 1)[1]
    return model
```

`ollama/` must remain special (the "local" suffix is keyed off it in
`format_metrics`, not off the stripped string — no change there). The "local"
suffix checks `model.startswith("ollama/")` on the *unstripped* id, which the
caller keeps, so it is unaffected.

### AC-2 — the canonical directory

In `_refresh_status`, compute once:

```python
from swarm.spec_loader import spec_dir_name
spec_dir = spec_dir_name(REPO_ROOT, self._spec) or self._spec
```

and render `f"{spec_dir} {self._task_id}"` where the status line currently prints
`{self._spec} {self._task_id}`. `spec_dir_name` returns the input when no
directory matches, so a wrong prefix degrades to today's output rather than
crashing. Keep `self._spec` for the queue list and history filtering (those
already prefix-match).

### AC-3 — the inner roster

```python
def format_self_heal(payload: dict) -> Text | str:
    heal = payload.get("e2e_self_heal") or {}
    if not (heal.get("class") or heal.get("failed") or heal.get("stop")):
        return ""
    out = [f"e2e self-heal: class {heal.get('class') or '?'} "
           f"· {len(heal.get('failed') or [])} failing "
           f"· {heal.get('rounds', 0)} round(s) "
           f"· {heal.get('stop') or 'healed'}"]
    for task in (heal.get("roster") or {}).get("tasks", []):
        out.append(f"  · {task.get('id')} {task.get('brief', '')[:48]}")
    return "\n".join(out)
```

Wired into `_refresh_status` (live) and the tail view after the gates block; the
block is a plain `Static` update, so no layout change. The strings match
`human_log.py`'s `e2e self-heal: class …` line (018: one formatter, not two).

## Tests

`swarm/tests/test_tui_format.py`:

- `short_model` for the four routing prefixes + a bare id + a long `org/repo/model`
  id;
- `format_self_heal` for a healed `drift` with a roster, a `e2e_weakened` stop,
  and an empty payload → `""`;
- a helper-level test that `spec_dir_name` is what the status line uses (call the
  function directly, not the screen).

No TUI instance is constructed: the screen methods are thin wrappers over these
helpers, so the helpers are the unit of truth.
