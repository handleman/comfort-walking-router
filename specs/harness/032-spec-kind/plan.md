# 032 Spec Kind — Plan

## Shape

```
specs/<name>/kind            one line: product | control-plane   (absent = product)
spec_loader.spec_kind(...)   reads it, trims, defaults
flow queue skip              kind == control-plane  OR  name in HARNESS_SPECS
preflight                    informational drift lines
.specify/templates           the marker line
```

## Why a file and not frontmatter

`spec_plan_hash` hashes `spec.md` + `plan.md` and the done ledger reopens a
green task when they change. Editing a product `spec.md` to add a marker would
reopen every green task in that spec. A sidecar `kind` file is outside the hash,
so it is declarative without being destructive — and it is trivially greppable.

## The default

Absent → `product`. A learning repo's worst outcome is the queue *not* running a
spec it should have run; the catastrophic outcome is the opposite (running a
control-plane spec). Defaulting the unknown to `product` keeps the safe case
safe, and the `HARNESS_SPECS` backstop still catches every known control-plane
directory even if its marker is missing.

## Placement of the read

`spec_loader.spec_kind(repo_root, name)` — next to `spec_dir_name`, because both
are "what is this spec directory" questions and the queue already imports
`spec_loader`. Returns `"product"` for a missing/unreadable file.

## Queue change

Both skip sites (`_spec_after` and `_first_open_task`) replace
`p.name not in HARNESS_SPECS` with a helper:

```python
def _runnable(name: str) -> bool:
    return name not in HARNESS_SPECS and spec_kind(REPO_ROOT, name) != "control-plane"
```

`HARNESS_SPECS` stays: a marker-less legacy control-plane spec must still be
skipped. The tuple becomes a backstop rather than the source of truth.

## Preflight

`spec_kind_notes(repo_root) -> list[str]`:

- `control-plane` spec whose name is missing from `HARNESS_SPECS` →
  "`<name>` is control-plane but not in HARNESS_SPECS (queue still skips it by
  kind)";
- a name in `HARNESS_SPECS` whose `kind` is absent or `product` →
  "`<name>` is in HARNESS_SPECS but declares no control-plane kind".

Both are printed once, informational; `make swarm-preflight` still exits clean.

## Retrofit

Add a `kind` file to every existing spec directory (product and harness). For
harness specs this also removes the reliance on the tuple over time; for product
specs it is self-documentation. The files are one line and never part of a hash.
