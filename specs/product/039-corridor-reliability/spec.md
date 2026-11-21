# 039 Corridor Reliability — Spec

Product spec (the comfort route guide).

## Problem

On the deployed app a real route returns **"Comfort data: OSM corridor
unavailable — weather-only score"** — the comfort profile is missing because the
Overpass corridor fetch (`app/comfort.py::_overpass_features`) returns nothing
from either endpoint. The local smoke run (2026-11-15) got 23 profile segments
and 6961 ways, so the fetch works in principle; on Render's free tier (0.1 CPU,
shared egress) the query is slow or the public endpoints are busy/rate-limiting,
and the corridor times out or 502s into a data gap.

## Goal

A real route on the deployed app gets an OSM corridor and a comfort profile as
often as the local smoke does, with the "never reject a route" contract intact —
a full failure is still a stated data gap, never a failed route.

## Scope

- `app/comfort.py` — log *which* endpoint failed and why, then make the fetch
  reliable: more public mirrors, a longer outer HTTP timeout, and a shorter
  Overpass QL timeout so the query gives up before the HTTP layer does.
- `OVERPASS_TIMEOUT_SECONDS` / `OVERPASS_MIRROR_URL` stay as the knobs.

## Non-goals

- Changing the scoring, the profile segmentation, or the fixtures.
- Making the corridor hard-required (a gap must still degrade gracefully).

## Acceptance criteria

- **AC-1 — Profile present on a live route.** A real Munich route on the deployed
  app returns a non-empty `comfort_profile` (the live map look shows bands, not
  "no OSM data").
- **AC-2 — Failure is visible.** When Overpass is genuinely down, the log says
  which endpoint failed and why, and the response still degrades to a
  weather-only score (no 5xx).
- **AC-3 — Tests.** The corridor fetch is covered for the multi-mirror retry and
  the timeout behaviour (mocked endpoints); `make test` stays green.

## Success definition

The deployed app shows the comfort bands for a real route, and the "data gap"
fallback only appears when Overpass itself is down.
