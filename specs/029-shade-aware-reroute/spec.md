# 029 Shade-Aware Reroute — Spec

Product spec (the swarm queue runs it). Builds on `007` (drift → reroute) and
`028` (per-segment comfort profile).

## Problem

Walk mode's reroute is comfort-blind. When the walker drifts, `007 T7` requeries
`POST /route` from the current position to the same destination and **replaces**
the displayed route with whatever comes back — even when the new route walks the
walker straight into the sun on a busy road the old route avoided. The profile
(028) made comfort visible along the route, and the reroute ignores it: the one
moment a walker is most willing to accept a detour is the moment the harness
throws the comfort information away.

Two concrete failures:

1. A shaded route that drifts by 40 m is replaced by a shorter, unshaded one with
   no warning; the walker cannot see what they lost until they are in it.
2. The "Off route — reroute?" banner says nothing about the trade the tap makes,
   so declining is guesswork.

## Goal

Make the reroute a **comparison**, not a replacement: compute the new route's
comfort over the distance still to walk, compare it with the remaining part of
the current route, and either replace silently (materially better), refuse and
say why (worse), or ask with the delta shown (close). The number the walker sees
is the profile they already understand from 028.

## Scope

- `frontend/src/lib/navigation/rerouteChoice.ts`: a pure function
  `compareReroutes(current, candidate) -> {delta, remainingKm, verdict, summary}`
  where each argument is `{profile, distance_m, from_m}`; `remainingKm` is the
  distance from the walker's position to the destination on each route (the
  current route's already-walked part is discounted via `from_m`), and `delta` is
  the distance-weighted score difference on the *remaining* distance.
- `frontend/src/lib/walkMode.ts`: `reroute()` gains the comparison. `verdict`
  decides what happens: `replace` (delta ≥ +5), `keep` (delta ≤ −5), `ask`
  otherwise; `rerouteWarning` records `delta`, `remainingKm` and `verdict` so the
  banner can explain it, and `keep` leaves the current route untouched.
- `frontend/src/lib/WalkRerouteWarning.svelte`: the banner states the trade —
  "Off route — reroute? +9 comfort · 1.2 km left" / "the current route is
  shadier (−6)" — with buttons that match the verdict (the "keep" case offers
  "Stay on this route" only).
- Tests: `rerouteChoice.test.ts` (remaining-distance weighting, thresholds, a
  walker already past the destination end), `walkMode` store tests for the three
  verdicts, and one `frontend/e2e/walk-mode.spec.ts` scenario where drift makes
  the reroute worse, so the banner shows a negative delta and the route is not
  replaced until the walker accepts.
- Documentation: `changelog.md` entry; no API or contract change (the profile is
  already in the route response), so `CACHE_VERSION` stays `v6`.

## Non-goals

- Generating multiple candidate routes or asking the provider for alternatives:
  the comparison is between the route the walker has and the one the provider
  returns for the reroute.
- Changing `007`'s drift rule or `028`'s profile.
- Persisting a preference for shade across sessions (004/005 prefs own that).

## Acceptance criteria

- **AC-1 — The comparison is about the remaining walk.** `compareReroutes`
  computes each route's score over the **remaining** distance only (the current
  route's profile is sliced at `from_m`; the candidate starts at 0), weights by
  distance, and returns `delta = candidate − current` (points, one decimal),
  `remainingKm` (candidate's remaining distance, rounded 0.1) and a `verdict` of
  `replace` (delta ≥ +5), `ask` (−5 < delta < +5) or `keep` (delta ≤ −5). The
  function is pure and deterministic; a walker at or past the end yields
  `remainingKm == 0` and `delta == 0`.
- **AC-2 — The store obeys the verdict.** `reroute()` replaces the route only on
  `replace` or on an explicit accept; `keep` leaves `route` unchanged and sets
  `rerouteWarning` with the negative delta; `ask` shows the banner with both
  choices. The banner copy names the number (`+9 comfort`, `−6 comfort`) and the
  remaining distance, and never claims a comfort gain that the comparison does
  not show.
- **AC-3 — Tests pin the three branches.** Unit tests for `compareReroutes`
  (weighting, thresholds, past-the-end) and store tests for
  `replace`/`ask`/`keep`. The e2e scenario covers `ask`: the fixture corridor is
  the same for both routes, so the banner must show the signed delta and the
  remaining distance and the route must not change until the walker accepts.
  (`keep` is a store-level branch; a fixture pair with two different corridors
  would be needed to make it visual.)
- **AC-4 — No new requests, no contract change.** The comparison uses the
  profile already present in both responses; the reroute path keeps its single
  `POST /route`; `contracts/route.json` and `app/` are untouched.
- **AC-5 — Green gates.** `npm --prefix frontend run check`, `npm run lint`,
  `npm --prefix frontend test -- --run` and `make e2e` pass; `changelog.md`
  records the change.

## Evidence

`007` T7 (drift → reroute, the banner), `028` (profile, `weighted_score`, the
`Profile:` explanation), `docs/research/self-healing-e2e-2026.md` (why a
scenario, not a unit, is the acceptance).

## Success definition

A walker who drifts sees what the reroute costs or gains in comfort before it
replaces the route, and can decline without losing the route they chose.
