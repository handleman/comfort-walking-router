# 028 Route Comfort Profile — Spec

Product spec (the swarm queue runs it). Extends `001` (comfort score) and `004`
(weather preference) with *where* the comfort is.

## Problem

`POST /route` returns one `comfort_score` for the whole walk and a list of
factors that reads like a verdict without evidence of place: "shade 0.60, quiet
0.80". A comfort-first walking router has to answer the question a walker actually
asks — **"which part of this walk is shady, and which part bakes?"** — and today
they cannot: the OSM corridor is fetched (001 AC-2), normalised into one number,
and thrown away.

Two consequences are visible in the product:

1. The map draws one uniform line, so a route that is 90 % shaded with 200 m of
   full sun on a busy road looks identical to a pleasant one.
2. The score cannot be checked: a walker who knows the street cannot tell whether
   the number is about their route or a generic average.

## Goal

Return a **comfort profile**: an ordered list of segments along the route
geometry, each with a score, its dominant factor and the distance it covers, in
one extra cached field. Draw it on the map with a legend, and say plainly when
the data is missing.

## Scope

- `app/comfort.py`: `profile(geometry, factors, ...)` splits the LineString into
  segments of at most `PROFILE_SEGMENT_M` (200 m) and scores each one from the
  corridor features sampled near it (trees/green, quiet vs busy class, lit), 0–100,
  with the dominant factor name.
- `POST /route` (via `_build_response` in `app/main.py`): adds
  `comfort_profile: [{from_m, to_m, score, factor, label} | …]` to the response
  and to the explanation ("Profile: 3 of 7 segments shaded, 1 sunny at 400–600 m").
- `contracts/route.json`: the pinned response contract gains the optional
  `comfort_profile` array (ADR-005 stays the source of truth).
- `frontend/src/App.svelte`: the route line is drawn per segment with a comfort
  band (three colours), a small legend, and an accessible label (colour is never
  the only signal); a segment's score appears on hover/click.
- `app/cache.py`: `CACHE_VERSION` bump (a cached response without the profile
  must not be served).

## Non-goals

- A heat map of the whole city, or per-point scoring beyond the route corridor.
- New data sources: the profile uses the corridor query 001 already makes (one
  Overpass call per route, unchanged).
- Changing the single `comfort_score` (it stays the mean of the profile so the
  two can never disagree).
- Accessibility rework of the rest of the page.

## Acceptance criteria

- **AC-1 — Profile in the contract.** `POST /route` returns `comfort_profile`
  covering the full route in order: `from_m`/`to_m` are contiguous, start at 0,
  end at the route distance (±1 m), and no segment exceeds `PROFILE_SEGMENT_M`
  (200 m). Each entry has `score` 0–100, `factor` ∈ {`shade`, `sun`, `quiet`,
  `traffic`, `lit`, `unknown`} and a short human `label`. `comfort_score` equals
  the distance-weighted mean of the profile (±0.5). `contracts/route.json`
  documents the field; `tests/test_route_contract.py` asserts it.
- **AC-2 — One corridor query, cached.** The profile adds no Overpass call: the
  existing corridor fetch feeds it, and a repeated identical request is served
  from the cache with the profile intact (`CACHE_VERSION` bumped so an old row
  cannot answer). `tests/test_route_comfort.py` counts the fetch.
- **AC-3 — Honest gap.** When the corridor is unavailable the response has
  `comfort_profile: null` and the explanation says the profile needs OSM data —
  never fabricated segments, never a 500.
- **AC-4 — Visible and accessible.** The map draws the route in three bands
  derived from the route's **own** score terciles (absolute bands collapse when
  quiet/lit are corridor-level and only shade varies), shows a legend naming the
  bands and their score ranges, and exposes each segment's score without colour
  (a `title`/`aria-label` and a visible list). `frontend/e2e/search.spec.ts`
  asserts the legend and at least two distinct bands on the fixture route.
- **AC-5 — Deterministic tests.** `make test`, `make lint`, `make typecheck`
  and `npm --prefix frontend run check` are green; the profiling is pure and
  deterministic from fixture data (no clock, no network in tests).
- **AC-6 — Docs.** `changelog.md` records the change; `swarm/docs/*` is untouched
  (product docs live in `docs/`), and `.env.example` gains nothing.

## Evidence

`001` (corridor factors, comfort score), `004` (weather preference),
`006` (lit/traffic factors), `007` (the map is where a walk is read),
`docs/research/dark-factory-market-2026.md` (the product is the proof: a dark
factory that produces a number nobody can see is not a product).

## Success definition

A walker can look at the route and point at the sunny 200 m, and the number on
the page is the average of what the map shows — or the page says it does not
know, and why.

## Status (2026-11-15)

All six tasks are green and merged through the swarm (T1, T4, T5, T6 by the
queue; T2 and T3 by hand after typed stops — `no_progress` on a real design gap
and `delta_incomplete` on a context reference the coder could never write).
Verified evidence: `comfort_profile` covers the route contiguously and is scaled
to the provider distance; `comfort_score` is its distance-weighted mean; the
fixture route reports 7 shaded / 12 sunny segments; `contracts/route.json`
documents the field and 5 contract tests assert it; the map draws tercile bands
with a legend and a visible segment list; `make e2e` is **12 passed** (the new
scenario included), `make test` 214 with the live Postgres, svelte-check and lint
clean. `CACHE_VERSION` v6.
