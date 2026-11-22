# 043 Spec Acceptance — Spec

Harness spec (control plane; the queue never runs it).

## Problem

Every guard the swarm has judges **one task**: the verifier reads that task's
brief, QA runs that task's gates. Nothing looks at the **whole product** after a
batch and asks "do the specs still describe working software?". That gap is how
040 shipped "green" while the app could not plan a route, rendered the walk
controls twice, and left a dead `⋯` button — each task passed its own narrow
checks.

Manual QA found all of it in minutes. The harness needs that final pass as a
first-class, repeatable step.

## Goal

A **spec acceptance pass** (`swarm/acceptance.py`, `make swarm-accept`) that runs
at the end of a drained queue and on demand:

1. picks every **product** spec that has built work (at least one ticked task);
2. serves the **local build** with the fixture backend;
3. checks each acceptance criterion in a real browser (desktop + mobile) —
   deterministic probes first, a free vision model as the second opinion;
4. writes a per-spec `acceptance.md` (PASS/FAIL per AC + evidence);
5. appends **fix tasks** for the failing ACs so the queue can repair them;
6. exits non-zero when anything failed — the final greenlight.

This is not 042's per-task visual QA (still unimplemented): it judges the
**specs**, once, at the end of a batch.

## Investigation

- `frontend/node_modules/playwright` is importable from `frontend/`; the e2e
  suite already boots the fixture backend (`ROUTE_FIXTURES=1`) and `vite preview`.
  A standalone Node script can reuse both without the Python swarm depending on
  Playwright.
- The frontend proxy target is hard-coded to `:8000`; acceptance needs its own
  ports when the developer's servers are running, so the target becomes
  `process.env.VITE_BACKEND_URL` (default unchanged).
- `openrouter/nvidia/nemotron-3.5-super-vl:free` is available on the configured
  OpenRouter key and is $0; it accepts image parts. Vision is advisory-plus: a
  clear "broken" verdict fails the AC, an `unclear` does not.
- `spec_loader.parse_tasks_md(include_done=True)` already distinguishes ticked
  tasks, and `spec_kind()` already separates `product` from `harness`.
- `supervise.supervise()` knows when the queue is empty (`outcome.action ==
  "continue"`) — the natural hook for the greenlight.

## Acceptance criteria

- **AC-1 — Spec discovery.** The pass evaluates every `specs/product/*` spec with
  at least one ticked task; harness specs and unbuilt product specs are skipped.
  Each spec's `AC-n` headings/paragraphs are parsed into id, title and text.
- **AC-2 — Browser evidence.** The pass builds once and serves the app with the
  fixture backend, then captures desktop (1280×800) and mobile (390×844)
  screenshots plus deterministic facts: console/page errors, leaflet tile count,
  duplicate visible control labels, zero-size interactive elements, horizontal
  overflow.
- **AC-3 — Per-AC probes.** A spec may declare checks in `acceptance.toml`
  (`exists`, `absent`, `count`, `min_count`, `text`, `value_set`,
  `route_request`), each tied to an `AC-n` and optionally a viewport. A failing
  deterministic check fails the AC.
- **AC-4 — Vision second opinion.** Screenshots + the AC text go to
  `SWARM_ACCEPT_MODEL` (default the free vision model) as JSON; `fail` fails the
  AC, `unclear` is reported but does not. `SWARM_ACCEPT_VISION=0` or a missing
  key skips the pass without failing it.
- **AC-5 — Verdict + report.** Deterministic failures and vision `fail`s make
  the spec FAIL; an AC with no check and no vision verdict is **unverified**,
  never a silent PASS. The report is written to
  `specs/product/<spec>/acceptance.md` with a per-AC table and evidence.
- **AC-6 — Auto-queue fix tasks.** Each failing AC appends one unchecked
  `T<n>` task to that spec's `tasks.md` (next free id, evidence file named when
  known). An open task already mentioning the same AC and `acceptance` is not
  duplicated. Nothing else in the spec is edited.
- **AC-7 — Final greenlight.** `make swarm-accept` runs the pass; the supervisor
  runs it once when the queue drains, continues the queue if it queued fixes,
  and otherwise exits non-zero when the verdict is FAIL.
- **AC-8 — No regression + off switch.** `SWARM_ACCEPT=0` disables the
  supervisor hook; `make swarm-test` stays green; a spec without
  `acceptance.toml` still gets global checks + vision + a report.

## Out of scope

- Per-task visual QA (042).
- Pixel-diff baselines; real-GPS checks (still a human gate).
- Fixing the failures it finds (it queues tasks; the swarm implements them).
