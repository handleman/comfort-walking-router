# 042 Map Destination Build Flow — Plan

## Approach

1. **Map pick is a deliberate build.** Keep the 040 auto-plan for typed
   endpoints. When the active pick is `end`, set `awaitingBuild`, open the
   controlled drawer, and suppress the coordinate-triggered auto-plan until the
   walker taps Build route. Typing a destination suggestion clears the flag and
   restores auto-plan.
2. **The drawer is controlled by App.** `BottomDrawer` exports `open` (bound),
   `suppressAutoOpen`, `error` and `canBuild`. It still auto-opens on a typed
   route; the build flow sets `suppressAutoOpen` so the route does not reopen
   the sheet after the overlay.
3. **Builder content.** With no route the drawer renders the preference summary
   (with Edit → the 041 preferences sheet), an error slot and a pill **Build
   route** CTA. With a route it renders the compact 041 route card and the
   start/save CTA.
4. **Build request + overlay.** `buildRoute` closes the drawer, sets
   `building = true`, awaits the existing `planRoute`, and clears the flag in a
   `finally`. A fixed, dimmed, centered overlay with a CSS spinner and
   `role="status"` renders while `building`; a Svelte fade removes it. On error
   the drawer reopens with the message and no route is drawn.
5. **Reverse label.** `/geocode/reverse` returns `{suggestions}`; `reverseLabel`
   reads it (with `{results}` as a fallback) so the endpoint shows a place name
   instead of coordinates.
6. **Overlap fix.** Map controls sit below the sheet scrim (z-index 50 vs 60),
   so the locate button cannot float over the preferences sheet.
7. **e2e.** A mobile spec intercepts the reverse geocode for a stable label,
   arms the destination pick, clicks the map, asserts the drawer and no route
   request, chooses a preference, delays `/route` to observe the spinner, then
   asserts the closed drawer, the drawn path and the compact summary. A second
   test fulfils `/route` with a 500 and asserts the reopened error.

## Risks

- The map click + reverse geocode is asynchronous; the e2e routes it to a
  fixture so the destination label and coordinates are deterministic.
- A very fast local route can hide the spinner; the e2e delays the request only
  to observe the state (the production spinner is tied to the real request).
- The `prefers-reduced-motion` rule must not hide the overlay, only the spin
  animation; the overlay uses opacity/fade, which the global rule disables for
  reduced motion (the element still mounts).

## Verification

`make e2e` (new mobile spec), the full gate set, and the strict acceptance pass
for 028/004/040/041/042. The acceptance interaction steps are declared N/A with
the e2e as the oracle because the browser oracle cannot address a map
coordinate; the app-wide console check still runs.
