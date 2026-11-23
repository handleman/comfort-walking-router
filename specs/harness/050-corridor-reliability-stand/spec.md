# 050 Corridor Reliability Test Stand — Spec

Harness spec (control plane; the queue never runs it).

## Problem

The comfort corridor (`app/comfort.py` → `app/providers/overpass.py`) is the only
part of the route pipeline that depends on a live third party (Overpass), and it
is the least observable. Three gaps:

1. **No hermetic test of the real parse path.** `tests/test_comfort*.py` and
   `test_overpass_provider.py` exercise the pipeline against hand-built dicts,
   and `ROUTE_FIXTURES=1` (`app/fixtures.py`) replays a *hand-recorded* corridor
   — neither proves the code parses what Overpass actually returns today.
2. **The live check is manual.** `make smoke-live` (`swarm/smoke.py`) hits real
   providers but is run by a human; there is no repeatable "is the corridor
   healthy right now, and which mirror served?" command or schedule.
3. **Geolocation is mocked only incidentally.** The walk/GPS scenarios rely on
   Playwright `setGeolocation`/`grantPermissions` already, but the four states
   (allowed / denied / unavailable / moved) are not stated as a contract, so the
   040 auto-centre/pre-fill work has no single place that pins them.

This leaves "does a real route get a real comfort profile?" answerable only by
deploying and eyeballing it — exactly the human touch the dark factory is meant
to remove.

## Goal

A **corridor reliability test stand**: deterministic, network-free coverage of
the parse path and the failover/timeout paths, plus a scheduled live probe that
answers "corridor OK / which mirror served" — all without a human in the loop.
Reuses the market-standard tools the repo already leans on (vcrpy for record/
replay, `unittest.mock`/`requests` for fault injection, Playwright for
geolocation).

## Layers

### 1. Recorded cassettes (vcrpy) — real parse path, hermetic

- Add `vcrpy` to the app dev/test deps.
- Record one real `[out:json]` Overpass corridor response (a Munich route,
  ~3 km corridor with trees/ways) into `tests/cassettes/` once, with the
  `User-Agent` + endpoint name; replay in CI with `--block-network`
  (record-mode `none`).
- Assert the corridor→factors pipeline (`app/comfort.py`) on that real-shaped
  data: `shade_factor`, `quiet_factor`, `lit_share`, segment split.

### 2. Fault-injection tests (mocked `requests`) — failover & timeout

- The multi-mirror order (`overpass-api.de` → `overpass.kumi.systems` →
  `overpass.private.coffee`), per-endpoint attempt logging, and the
  "data gap, never a 5xx" fallback — mocked, one test per shape
  (timeout, 5xx, empty, partial). Extends `tests/test_overpass_retry.py`.

### 3. Live probe (`corridor-check`) — scheduled, human-free

- A `make corridor-check` command (extends `swarm/smoke.py`) that POSTs one fixed
  route against the real mirrors and prints/records: corridor present (bool),
  profile segment count, which mirror served, per-mirror latency/status.
- Optionally a GitHub Actions schedule (nightly) running it, so uptime is
  observed without a human.

### 4. Geolocation contract (Playwright) — the four states

- One spec (`frontend/e2e/geolocation.spec.ts`) that pins allowed / denied
  (`clearPermissions`) / unavailable (`setGeolocation(null)`) / moved
  (`setGeolocation` mid-session), asserting origin pre-fill + auto-centre and the
  fallback modal, so 040 T4/T18 regressions fail here.

## Non-goals

- Not the 039 code change itself (multi-mirror retry, 90 s timeout) — that stays
  in 039; this spec only builds the stand that proves it.
- Not a monitoring/alerting SaaS, no load/chaos beyond basic fault injection.
- Not rewriting `app/comfort.py`; the stand is test/observability code.

## Acceptance criteria

- [ ] **AC-1 — cassette.** `tests/cassettes/` holds a recorded real Overpass
  response; a test runs offline (`--block-network`) and asserts the
  corridor→factors pipeline on it.
- [ ] **AC-2 — failover.** Mocked-`requests` tests cover the three-mirror order,
  per-endpoint logging, timeout and 5xx shapes, and the "data gap, never 5xx"
  fallback.
- [ ] **AC-3 — live probe.** `make corridor-check` reports corridor-present,
  segment count, which mirror served, and per-mirror status for a fixed route.
- [ ] **AC-4 — geolocation contract.** `geolocation.spec.ts` covers allowed /
  denied / unavailable / moved and asserts the auto-centre/origin pre-fill and
  the denied fallback.
- [ ] **AC-5 — no regression.** `make test`, `make e2e`, `make swarm-test` green;
  cassettes and fixtures are secret-free (no live keys/`User-Agent` tokens
  committed).

## Files

- `tests/cassettes/` (new), `tests/test_corridor_parse.py` (new),
  `tests/test_overpass_retry.py` (extend).
- `requirements-dev.txt` — add `vcrpy` (+ `pytest-recording`).
- `swarm/smoke.py` + `Makefile` — `corridor-check`.
- `frontend/e2e/geolocation.spec.ts` (new) + `frontend/e2e/helpers.ts` (extend).

## Success definition

`pytest -m corridor --block-network` proves the real parse path offline;
`make corridor-check` answers "corridor healthy, served by `overpass.kumi.systems`"
from a cron/GHA run; and a geolocation regression in 040 fails
`geolocation.spec.ts` before it reaches a human.
