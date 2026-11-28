# 043 Live Parity and Visual Honesty — Spec

Status: queued (2026-11-28, operator rejection of the 042 upload).

## What / Why

The 042 upload was called green while the deployed app did not match the design
and could not reliably plan a route:

- the no-route builder's **Build route** CTA renders as plain text — the builder
  markup landed without its pill styles;
- a map-pick route can hang on the public OSM corridor lookup and the Render
  gateway returns **502** (the same coordinates answered 200 once, then timed
  out; the browser shows "Route planning failed (502)");
- **Saved** is shown although the deployment has no `DATABASE_URL`; the API
  correctly returns 503, but the UI still offers the feature;
- the spinner overlay was not visible in the captured upload because the request
  failed before the overlay state was observable.

Green was not a lie about the gates: every gate and the 042 interaction e2e run
hermetically with `ROUTE_FIXTURES=1`, and the 041 design checks compare tokens
and region rects, not the rendered pixels. This spec closes those gaps for the
app; spec 062 closes the visual gate in the harness.

## Scenario

On the public mobile app I pick a building on the map. The builder shows the
destination, a styled preference summary and a **Build route** pill. I tap it:
the builder closes, a dimmed overlay with a centered spinner owns the screen,
the route is calculated from the real provider within a bounded time, the
overlay dissolves and the drawn route opens the compact summary. A failed
request reopens the builder with an honest error. When the deployment has no
database, **Saved** and **Saved walks** do not appear at all.

## Scope

- `app/main.py`, `app/comfort.py`, `app/providers/overpass.py` — a total
  corridor budget, a weather-only fallback, and a route response that cannot
  outlive the gateway.
- `frontend/src/lib/components/BottomDrawer.svelte` — the builder CTA,
  destination, error and spacing in the 041 visual language.
- `frontend/src/App.svelte`, `frontend/src/lib/savedRoutes.ts` — a capability
  probe that hides Saved/Saved walks when the database is not configured.
- `frontend/e2e/build-route.spec.ts` (042 T4), `acceptance.toml`, `live.toml` —
  the spinner/visual evidence and the live route check.
- `specs/product/042-map-destination-build-flow/*` — the restored e2e oracle and
  `covered_by` declarations.

## Non-goals

- Changing the 040 typed auto-plan or the 041 frame layout.
- Adding a database to the deployment; the feature is hidden, not faked.
- A new routing provider or a progress percentage.
- Replacing the Figma design checks; 062 adds the pixel-similarity gate.

## Acceptance Criteria

- [ ] AC-1: **No database, no Saved.** When `DATABASE_URL` is not configured,
  the app hides the mobile Saved button, the save-route control and the nav
  Saved-walks entry, and never opens the saved dialog. The API keeps returning
  503. A configured database restores the feature unchanged.
- [ ] AC-2: **Builder matches the 041 language.** The no-route builder renders a
  brand pill **Build route** (52 px, radius, white label, icon/spacing), the
  destination and error slots are legible, and the preference summary/Edit row
  opens the styled PreferencesSheet. A computed-style test and a mobile
  screenshot prove it; the 90% visual gate (062) passes.
- [ ] AC-3: **A route is bounded and honest.** A `/route` request with the 042
  coordinates answers within 15 s on the live stand, returns 200 with waypoints
  and a comfort score, and never waits on three 90 s Overpass endpoints. A slow
  or unavailable corridor yields a weather-only score, not a 5xx; a provider
  failure is a typed 504/502 with a readable message.
- [ ] AC-4: **Spinner and success.** With `/route` held, the builder closes and
  the full-screen `[data-testid="route-loading"]` overlay (dimmed, centered
  spinner, `role="status"`) is visible; on success it dissolves, the drawer
  stays closed and the route is drawn; on 500 it reopens the builder with the
  error. The e2e asserts all three states.
- [ ] AC-5: **Verification.** `make e2e`, the full gates, `make swarm-accept
  --strict` for 028/004/040/041/042 and `make accept-live` (route + deployment)
  are green; the live route report records the latency. No regression in 001–040.

## Verification

The 042 e2e is the primary oracle (`covered_by` in `acceptance.toml`). The live
lane posts the 042 coordinates and records the response time. The 041/042 design
visual checks run in the strict pass and must be at least 90% similar on the
configured regions.

## Open questions

- Should the builder show the shade toggles inline instead of Edit? The 041
  design and 042 spec keep the summary + Edit; a later spec can change it.
