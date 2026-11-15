# 031 Dashboard Update — Spec

Control-plane spec (add `031-dashboard-update` to `HARNESS_SPECS`): the dashboard
is the operator's view, never run by the swarm.

## Problem

The dashboard is a *view over `run.json`/`events.jsonl`* and it has drifted from
the state it renders. Three gaps, each found by reading the screen against the
changes of 2026-11-15:

1. **The model prefix is inconsistent.** `short_model()` strips `openrouter/`,
   `zen/` and `ollama/`, but the `opencode-go/` routing prefix (added when the
   operator moved to the Go subscription) is not in the list — so the planner
   line renders `opencode-go/deepseek-v4.1-flash` while the other four roles
   render the bare id. The column no longer means "which model" at a glance.
2. **The spec path is not shown.** The status line prints the invocation prefix
   (`028`), not the directory the queue actually keys on
   (`specs/028-route-comfort-profile`). `spec_dir_name()` already exists and is
   what the done ledger uses; the dashboard should show the same path so the
   screen and the queue cannot disagree.
3. **The inner roster is invisible.** A red e2e suite now triages and writes
   `<run>/inner/{spec,plan,tasks}.md`, and `run.json.e2e_self_heal` records the
   class, the failing titles, the roster and the stop — but the dashboard
   renders none of it, so the operator cannot see *why* a run is self-healing or
   what the inner tasks are.

## Goal

Make the dashboard show the same three things the run actually records, in the
same words the run uses, without owning state:

- every model role shows the **bare provider-agnostic id** (prefix stripped),
  with the provider shown as a suffix when it is not `openrouter`/`zen`/`go`-style
  routing (i.e. `ollama/` stays "local");
- the status line shows the **canonical spec directory** next to the task id;
- a small **self-heal block** in the left column names the triage class, the stop
  (or "healed"), the failing count, the rounds and the roster task briefs, and
  disappears when no e2e self-heal happened.

## Scope

`swarm/tui.py` only, plus `swarm/humanlog.py` if a formatting helper belongs
there (the dashboard and the written report must not format the same number two
different ways — 018). `swarm/tests/test_tui_format.py` and any `test_humanlog`
cover the new strings. No changes to `run.json`, the flow, or the roster writer.

## Non-goals

- A richer inner-roster panel (file viewer, live tail of the repair crew). A
  one-line-per-task summary is enough; the full roster is one `<run>/inner/` away.
- Rendering `queue_reasons` for every skipped task in the queue list (that is a
  separate, larger view and not in these gaps).
- Changing how the dashboard discovers specs or matches runs to specs.

## Acceptance criteria

- **AC-1 — One model, one label.** `short_model()` strips `opencode-go/` too, and
  a model row never shows a routing prefix. A test pins `short_model` for
  `openrouter/`, `zen/`, `ollama/`, `opencode-go/` and a bare id, and the
  "local"/"fallback" suffixes still work.
- **AC-2 — The path the ledger uses.** The status line shows
  `specs/<dir>/<task>` (via `spec_dir_name`) — for a prefix invocation (`028`)
  and a full directory alike, it renders the directory. A test covers both
  inputs. The prefix remains visible in compact contexts where it already is
  (queue list), but the *status* line shows the directory.
- **AC-3 — The inner roster is visible.** A `format_self_heal(payload)` helper
  renders, from `run.json.e2e_self_heal`: `e2e self-heal: class drift · 2
  failing · 1 round · healed` (or the stop), then one line per roster task
  (`· T1 <brief…>`). It returns empty when the field is absent, and it is wired
  into the live and tail views. Tests: a healed case, a `e2e_weakened` stop with
  roster, and an absent field.
- **AC-4 — Green tests.** `make swarm-test`, `ruff check .`, `mypy app tests`
  green; `031-dashboard-update` is in `HARNESS_SPECS`; `changelog.md` records it.

## Evidence

`swarm/tui.py` (`short_model`, `_refresh_status`, `format_metrics`),
`swarm/llms.py` (`opencode-go/` prefix, 2026-11-15), `swarm/spec_loader.py`
(`spec_dir_name`), `swarm/e2e_triage.py`/`swarm/inner.py` (the roster the run
already records). The gaps are visible in `python -m swarm.tui --tail
swarm/runs/<any 029 run>`: the planner row and the `028` status line.

## Success definition

An operator watching a Go run sees four bare model ids, the spec directory the
ledger keys on, and — when a red e2e suite triages — the class, the stop and the
inner tasks in the same words `human_log.txt` uses.
