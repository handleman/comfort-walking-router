# 054 Signal Integrity — Tasks

Each task maps to one acceptance criterion.

- [ ] T1 (AC-1): e2e always builds first (`pretest:e2e` or a preview webServer build); a raw `npx playwright test` sees current source; the record carries the build time.
- [ ] T2 (AC-2): a reviewer PASS with a required evidence command unrun is `review_unsupported` (one re-ask first) and never green; the judge record names the command.
- [ ] T3 (AC-3): `make swarm-accept --selftest` proves every declared check passes on the build and fails on a mutated target; criteria without checks are a configuration error.
- [ ] T4 (AC-4): acceptance-generated fix tasks whose AC now passes are closed with the verdict instead of being re-queued.
- [ ] T5 (AC-5): `make factory-audit` rejects tracked caches/binaries/secrets/large blobs and missing hygiene files; 048 Phase 7 runs it before the push.
- [ ] T6 (AC-6): a UI fix whose evidence names a spec is test-first against that spec (prompt + gate + success = spec green).
- [ ] T7 (AC-7): factory tests carry core/driver markers; `pytest -m "not driver"` is green with no app tree; driver tests skip with a reason.
- [ ] T8 (AC-1..7): `pytest swarm/tests/`, `ruff`, `mypy app tests` green; one test per AC.
