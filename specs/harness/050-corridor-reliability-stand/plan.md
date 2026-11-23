# 050 Corridor Reliability Test Stand — Plan

References `specs/harness/050-corridor-reliability-stand/spec.md` AC-1–AC-5.

## Approach

Four independent layers, each with its own test entry point, so any one can land
alone. Order: cassettes (proves parse) → fault injection (proves failover) →
live probe (proves uptime) → geolocation contract (pins GPS). The first two are
pure Python and land together; the last two are smoke/e2e and land after.

## Steps

1. **Cassettes (AC-1).** Add `vcrpy` + `pytest-recording` to
   `requirements-dev.txt`. Record a real Munich-corridor `[out:json]` response
   into `tests/cassettes/overpass_corridor.json` (record-mode `once`, then
   verify `--record-mode=none --block-network`). Write
   `tests/test_corridor_parse.py` asserting `shade_factor`, `quiet_factor`,
   `lit_share` and segment split on that real data.

2. **Failover (AC-2).** Extend `tests/test_overpass_retry.py`: mock `requests.get`
   with a side-effect sequence per mirror (timeout → 5xx → success; all fail →
   empty corridor) and assert the mirror order, the per-endpoint attempt log
   line, and the "data gap, never 5xx" result.

3. **Live probe (AC-3).** Add a `corridor-check` path to `swarm/smoke.py` (or a
   small `swarm/corridor_check.py`) that POSTs one fixed route against the three
   real mirrors and prints corridor-present, segment count, serving mirror,
   per-mirror status/latency. Wire `make corridor-check`.

4. **Geolocation contract (AC-4).** Add `frontend/e2e/geolocation.spec.ts` using
   `setGeolocation`/`grantPermissions`/`clearPermissions` to cover allowed,
   denied, unavailable (`null`), and moved; assert auto-centre/origin pre-fill
   and the denied fallback modal. Reuse `frontend/e2e/helpers.ts`.

5. **Verify (AC-5).** `make test`, `make e2e`, `make swarm-test`, ruff + mypy
   green; confirm cassettes/fixtures contain no live key or token.

## Risks

| Risk | Mitigation |
| --- | --- |
| Cassette goes stale as Overpass schema drifts | Record-mode `none` in CI fails loudly on a changed response; re-record intentionally (`rewrite`) with review |
| Cassette captures PII/location from live data | Munich corridor is public OSM; scrub `User-Agent`/any token before commit; CI blocks network |
| Live probe is flaky (mirrors rate-limit) | Probe is a report, not a gate; it records per-mirror status, never fails the build on a single mirror |
| Overpass JSON shape differs from the hand-built mocks | AC-1's real cassette is the source of truth the parse path must satisfy |

## Rollback

Each layer is additive (new files + a dep); reverting a commit removes it with
no change to the app or the swarm core.
