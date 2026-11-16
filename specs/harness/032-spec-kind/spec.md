# 032 Spec Kind — Spec

Control-plane spec (the queue never runs it; it changes *how* the queue reads
specs).

## Problem

`specs/` mixes two kinds of spec that are written and consumed differently, and
the only thing telling them apart is a hand-maintained name list:

- **Product specs** — the app the swarm is building (001, 004, 005, 006, 007,
  008, 010, 014, 028, 029, 030). The queue *digests* these.
- **Control-plane specs** — the swarm itself (009, 012–031). The queue must
  *never* run these, because the harness cannot rewrite its own judges and
  guards.

`HARNESS_SPECS` (a tuple of directory names in `swarm/flow.py`) is the separator,
and it has two failure modes:

1. **Forgotten entry** — a new control-plane spec not added to the list is a
   *product* spec as far as the queue is concerned, so the swarm would try to
   implement its own changes. The "Control-plane spec (added to HARNESS_SPECS)"
   first line is prose; nothing machine-reads it.
2. **Drift** — the list is not derived from the specs, so it can disagree with
   what a spec actually says, with no warning until a run does the wrong thing.

The distinction is real (the operator wrote specs both ways all session) but the
mechanism is a convention, not a property of the spec.

## Goal

Make the kind a **property of the spec directory**, machine-read, with the queue
skipping control-plane specs because the spec says so — and keep the name list
only as a safety net for directories that predate the marker. Add the marker to
every existing spec so the two kinds are self-describing, and to the template so
every future spec declares itself.

## Scope

- `specs/<name>/kind` — a one-line file whose trimmed content is `product` or
  `control-plane`. Absent → `product` (a spec that does not say it is
  control-plane is treated as product, which is the safe default for a learning
  repo and keeps existing product specs working untouched).
- `swarm/spec_loader.py::spec_kind(repo_root, name)` — reads it.
- `swarm/flow.py` — the queue skips a spec when `spec_kind(...) ==
  "control-plane"` **or** the name is in `HARNESS_SPECS` (the backstop); both
  checks remain so a marker-less legacy control-plane spec is still skipped.
- `swarm/preflight.py` — one informational line per inconsistency: a
  `control-plane` spec missing from `HARNESS_SPECS`, or a `HARNESS_SPECS` name
  whose `kind` file is absent/`product`. Informational, never a failure.
- `.specify/templates/spec-template.md` — gains the marker line.
- One `kind` file per existing spec directory (harness and product alike); the
  file is **not** part of `spec_plan_hash`, so adding it cannot reopen a green
  product task.

## Non-goals

- Two physical directories (`specs/` vs `swarm/specs/`): a `kind` file is the
  same separation without moving 30 directories and breaking every path.
- Deriving the kind from the directory name or the prose.
- Changing the done ledger, trailers, or `make swarm-record`.

## Acceptance criteria

- **AC-1 — The kind is a property.** `spec_kind` returns `product` for a missing
  file, and the trimmed content otherwise. A test covers missing, `product`,
  `control-plane` and a file with trailing whitespace.
- **AC-2 — The queue skips by kind, with a backstop.** A `control-plane` spec
  not in `HARNESS_SPECS` is still skipped; a `HARNESS_SPECS` name with no marker
  is still skipped. A test drives `_first_open_task`/`_next_open_spec` with a
  fake repo for all four combinations.
- **AC-3 — Preflight names the drift.** `make swarm-preflight` reports each
  direction of disagreement (control-plane-without-entry, entry-without-kind)
  without failing; a test checks the messages.
- **AC-4 — Every spec and the template carry the marker.** `git ls-files
  'specs/*/kind'` returns a file for every spec directory, and the template has
  the marker line. A `control-plane` file's content matches its directory.
- **AC-5 — Green and recorded.** `make swarm-test`, `ruff check .`,
  `mypy app tests` green; `032-spec-kind` is in `HARNESS_SPECS`; `changelog.md`
  records the change and the reason (the queue must not digest its own judges).

## Evidence

`swarm/flow.py` (`HARNESS_SPECS` and the two skip sites), the "Control-plane
spec" prose in every harness spec, `AGENTS.md` ("The swarm does not edit spec
files"), and the fact that 028/029/030 are product specs the queue ran while
009/012–031 are hand-implemented.

## Success definition

Forgetting to add a new control-plane spec to any list is impossible: the spec
says what it is, the queue reads it, and preflight tells the operator when the
two sources disagree.
