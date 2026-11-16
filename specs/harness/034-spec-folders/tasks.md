# 034 Spec Folders — Tasks

- [x] T1 (AC-1, AC-2): Add `iter_spec_dirs`/`resolve_spec_dir` to `swarm/spec_loader.py`; `spec_kind` reads the folder, `kind` file is the legacy-flat backstop (`control-plane` aliased to `harness`).
- [x] T2 (AC-3, AC-4): Route the queue, verifier, plan_scope, prompts and corpus fallback through `resolve_spec_dir`; keep `spec_dir_name` returning the leaf name so ledger keys and historical blobs are unchanged.
- [x] T3 (AC-1): `git mv` all 31 specs into `specs/product/` (11) and `specs/harness/` (20); rewrite harness `kind` files to `harness`; move `030-operator-runbooks` to harness and register it in `HARNESS_SPECS`.
- [x] T4 (AC-5): Preflight drift notes read the folders; update AGENTS.md, swarm README, queue.md, changelog and the spec template.
