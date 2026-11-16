# 034 Spec Folders — Plan

1. `git mv` each of the 31 specs into `specs/product/` (11) or
   `specs/harness/` (20), keyed on the existing `kind` marker; rewrite harness
   `kind` files from `control-plane` to `harness`.
2. Add `iter_spec_dirs()` and `resolve_spec_dir()` to `swarm/spec_loader.py` and
   route `spec_kind`/`spec_dir_name`/`load_spec_tasks` through them, keeping the
   legacy flat dir as a first-class input.
3. Point the queue (`_spec_after`, `_first_open_task`, `_runnable_spec`),
   preflight drift notes, `verify.py`, `plan_scope.py`, `prompts.py` and the
   corpus fallback at `resolve_spec_dir`.
4. Move `030-operator-runbooks` to harness (it documents the swarm) and register
   it in `HARNESS_SPECS`.
5. Update docs (AGENTS.md, swarm README, queue.md, changelog, spec template).

Risks: the done ledger and corpus key on *leaf* names, so `spec_dir_name` must
keep returning the leaf; the corpus's historical blob path stays `specs/<name>/`
because that is where the green commit found it.
