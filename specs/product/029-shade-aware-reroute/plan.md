# 029 Shade-Aware Reroute — Plan

## Shape

```
drift detected (007 T7)
  └─ POST /route from current position → candidate (has comfort_profile, 028)
       └─ compareReroutes(current, candidate)         pure, frontend
            replace (Δ ≥ +5)  → adopt, brief banner "route improved"
            ask     (−5<Δ<+5) → banner with Δ and both choices
            keep    (Δ ≤ −5)  → keep route, banner explains the loss
```

## Modules

`frontend/src/lib/navigation/rerouteChoice.ts`

```ts
export interface RouteForChoice {
  profile: ProfileSegment[]   // 028: {from_m,to_m,score,factor,label}
  distance_m: number
  from_m: number              // how far the walker already is along THIS route
}

export type RerouteVerdict = 'replace' | 'ask' | 'keep'

export interface RerouteChoice {
  delta: number          // candidate − current, one decimal, remaining-distance weighted
  remainingKm: number    // candidate's remaining distance, one decimal
  verdict: RerouteVerdict
  summary: string        // "+9 comfort · 1.2 km left" / "−6 comfort · 1.5 km left"
}

export function compareReroutes(current: RouteForChoice, candidate: RouteForChoice): RerouteChoice
```

Rules (pure, deterministic, no clock):

- each route's remaining score = distance-weighted mean of the profile segments
  whose `to_m > from_m`, weighting the overlap only from `from_m`;
- `remainingKm = max(0, (candidate.distance_m − candidate.from_m)) / 1000`, one decimal;
- `delta = candidateScore − currentScore`, one decimal;
- `remainingKm === 0` → `delta = 0`, `verdict = 'ask'`;
- thresholds: `delta >= +5` → `replace`, `delta <= -5` → `keep`, else `ask`;
- `summary` names the delta with a sign and the remaining distance; for `keep`
  it says the current route is shadier.

`frontend/src/lib/walkMode.ts`

- `rerouteWarning` gains `{ delta, remainingKm, verdict }` (all optional, so 007's
  banner keeps working before a comparison exists);
- `reroute(pos, destination)` computes the candidate, calls `compareReroutes`
  with the current route (profile + distance + `from_m` from the nearest profile
  segment to `pos`), and:
  - `replace` → adopt the candidate route, clear the warning;
  - `ask` → keep the current route, set the warning with the numbers;
  - `keep` → keep the current route, set the warning and `rerouteError` with the
    reason (no accept button is offered by the banner for `keep`).

`frontend/src/lib/WalkRerouteWarning.svelte`

- props gain `delta`, `remainingKm`, `verdict`;
- copy: `Off route — reroute? +9 comfort · 1.2 km left` / `... −6 comfort ...`;
- `verdict === 'keep'` renders a single `Stay on this route` button (dismiss) and
  no accept; `ask`/`replace` keep the two buttons.

## Tests

- `rerouteChoice.test.ts`: weighting by remaining distance (a long already-walked
  bad stretch must not dominate), the three verdicts at the exact thresholds,
  `from_m` mid-segment overlap, past-the-end → `remainingKm 0` / `delta 0` / `ask`.
- `walkMode` store tests: `replace` adopts, `ask` keeps + numbers, `keep` keeps +
  no accept.
- `frontend/e2e/walk-mode.spec.ts`: drift on the fixture route → the banner shows
  a delta and the remaining distance (the fixture returns the same corridor, so
  the verdict is `ask`), and the route is not replaced until the walker accepts.

## Risks

- **Numbers from two profiles measured differently** — both come from the same
  028 code path and the same corridor, so the delta is comparable by construction.
- **`from_m` drift** — the walker's position is projected onto the profile by
  nearest segment; a coarse profile (200 m) makes that ±100 m, which is why the
  delta is rounded to one decimal and the thresholds are ±5 points, not ±1.
- **Banner complexity** — the copy is one line; the three verdicts change which
  buttons exist, not the layout.
