# 034 Spec Folders — Spec

Harness spec (control plane; the queue never runs it).

## Problem

032 separated product from harness with a one-line `kind` sidecar in a flat
`specs/<name>/` tree. That works, but the separation is invisible: nothing in
the directory layout tells an operator that `009` is harness and `028` is
product without opening a `kind` file. The operator asked for the two kinds to
live in different folders.

## Goal

`specs/product/` (the comfort route guide's work items) and `specs/harness/`
(the swarm's own machinery). The folder is authoritative; the `kind` file stays
as the backstop for a legacy flat dir.

## Non-goals

- Renaming the product folder beyond `product` (the operator chose to keep it).
- Removing `HARNESS_SPECS` (it is a second backstop, still useful for a
  marker-less flat dir).

## Acceptance criteria

- AC-1 — Every spec dir is under `specs/product/` or `specs/harness/`; none
  remain flat.
- AC-2 — `spec_kind()` returns the folder (`product`/`harness`); a legacy flat
  dir falls back to its `kind` file, with `control-plane` accepted as the old
  value for `harness`.
- AC-3 — `spec_dir_name`/`load_spec_tasks`/the queue/verifier/prompts/corpus all
  resolve through one `resolve_spec_dir()`, and a flat test tree still works.
- AC-4 — The done ledger keys (leaf names) and historical git blobs are
  unchanged by the move.
- AC-5 — Preflight reports drift between the folders and `HARNESS_SPECS`.
