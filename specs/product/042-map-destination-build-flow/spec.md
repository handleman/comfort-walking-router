# 042 Map Destination Build Flow — Spec

Status: queued for the queue-owned implementation (operator version reverted 2026-11-28).

## What / Why

Today a map-picked destination starts the route request immediately, behind a
results sheet that is either collapsed or already open. The walker cannot set
the destination, adjust the walk's comfort, and then deliberately ask for the
route. They also get no clear "calculation is running" state: on a slow route
the map simply looks unchanged.

This spec adds the explicit mobile build flow: pick the destination on the map →
the drawer slides up with the destination and the current preferences → choose
the parameters → **Build route** → the drawer closes and a centered spinner on a
dimmed background shows the calculation → the overlay fades and the route is
drawn and ready to use. Typed endpoints keep the 040 auto-plan; the map-pick
path is deliberate because it is the moment the walker is choosing a place.

## Scenario

As a user I choose a destination by tapping a building or place on the map. The
results drawer opens smoothly. I choose the preferences I need and tap **Build
route**. The drawer closes and I see a spinner in the middle of a shadowed
screen while the route is calculated. When it finishes, the spinner and the
shadow dissolve and the route is drawn on the map, fully functional.

## Scope

- `frontend/src/App.svelte` — the map-pick state, the controlled drawer, the
  Build route request, the loading overlay and the success/failure transitions.
- `frontend/src/lib/components/BottomDrawer.svelte` — the controlled `open`
  prop, the no-route builder (destination + preferences + Build route) and the
  `build` event.
- `frontend/src/lib/map/picker.ts` — the reverse-geocode label reads the API's
  `{suggestions}` (with `{results}` as a compatibility fallback).
- `frontend/e2e/build-route.spec.ts` — the full mobile scenario, including the
  delayed-request spinner and the failure path.
- `specs/product/042-map-destination-build-flow/*` — this spec, plan, tasks and
  acceptance declarations.

## Non-goals

- Changing the typed-endpoint auto-plan (040 AC-8) or the desktop flow.
- A new routing provider, backend fields or a progress percentage.
- A second route or a detour budget.
- Replacing the map or the drawer's 041 visual language.

## Acceptance Criteria

- [ ] AC-1: **Map pick opens the builder, not a request.** With the destination
  pick armed, tapping the map fills the destination (street/building label or a
  fallback label), opens the drawer with its slide-up transition, and sends no
  `POST /route`. A typed destination still auto-plans.
- [ ] AC-2: **Parameters before build.** The open drawer shows the destination,
  the current preference summary, its Edit action (opening the 041 preferences
  sheet) and a **Build route** button. Applying preferences closes the
  preferences sheet and keeps the builder drawer open.
- [ ] AC-3: **Build route owns the request.** Tapping Build route closes the
  drawer and shows a full-screen dimmed overlay with a centered spinner
  (`role="status"`) while the route request is in flight.
- [ ] AC-4: **Success dissolves into the route.** When the request succeeds the
  overlay fades out, the drawer stays closed, the comfort route is drawn on the
  map and is interactive; opening the drawer shows the compact route summary.
- [ ] AC-5: **Failure is honest.** A failed request dismisses the overlay,
  reopens the builder drawer and shows the error; no route is drawn.
- [ ] AC-6: **No overlapping chrome.** With a sheet open, the map controls
  (locate/zoom) are covered by the scrim and never float over the sheet's text;
  the builder and results content fit without overlapping the handle or the
  endpoint card.
- [ ] AC-7: **Accessible and calm.** The overlay is announced as a status, the
  drawer and sheets keep their dialog semantics and keyboard/focus behaviour,
  and `prefers-reduced-motion` suppresses the spinner rotation and the
  transitions.
- [ ] AC-8: **No regressions.** The 040 typed auto-plan, 041 frames, 028 bands,
  004 weather chip and 005 saved routes remain green; `pytest`, `ruff`, `mypy`,
  the frontend gates, `make e2e` and the strict acceptance pass are green.

## Verification

`frontend/e2e/build-route.spec.ts` is the primary oracle: it drives the map
pick, the preferences sheet, a delayed `/route` (to observe the spinner), the
success dissolve and the failure reopen. `acceptance.toml` declares the
interaction steps N/A for the DOM oracle (a map coordinate is not a stable
selector) and points at that e2e; a console-error check still runs.

## Open questions

- Should the builder eventually offer the fastest alternative inline? That
  depends on the API returning alternative routes (follow-up spec).
