# 043 Live Parity and Visual Honesty — Plan

1. **Capability probe.** Add `GET /capabilities` returning
   `{"saved_routes": bool(app_db.DATABASE_URL), "database": bool}`. It does not
   touch the database. The frontend fetches it on mount; `savedRoutesAvailable`
   gates the drawer's Saved button, the save-route control and the nav entry.
   Keep the 503 API behaviour and the 005 flow when a DB exists.
2. **Builder styles.** Add the missing `.builder`, `.builder-destination`,
   `.build-route`, `.builder-error` rules to `BottomDrawer.svelte` using the
   041 tokens: a 52 px brand pill, 14/600 label, 18 px radius, white text,
   focus ring and disabled state; spacing that fits the 360 px sheet. Verify
   the Edit row still opens the styled PreferencesSheet.
3. **Route budget.** Replace the sequential 3 × 90 s Overpass attempts with a
   bounded corridor lookup: a total budget (`OVERPASS_TOTAL_BUDGET_SECONDS`,
   default 8 s), parallel mirrors or one fast mirror, and a QL timeout under the
   budget. A miss returns a weather-only score (200), never a gateway timeout.
   Keep Mapbox at 10 s and surface its failure as a typed 504/502 with a
   readable detail; add a slow-Overpass test that the response is 200 and <10 s.
4. **Spinner proof.** With the route held by the e2e, assert the builder has
   closed and `route-loading` is visible and on top; on success it is removed
   and the path is drawn; on 500 the builder reopens with the error. Capture
   the mobile screenshot for the visual gate.
5. **Acceptance.** Restore 042 T4's `frontend/e2e/build-route.spec.ts`, declare
   AC-1..7 `covered_by` that test, add 042 `live.toml` (remote Render URL + the
   042 coordinates + latency), and add the 041/042 visual regions for the 062
   gate. Run `make e2e`, the strict pass and `make accept-live`.
6. **Deploy and verify.** Push, let Render deploy, run the live route twice
   (cold + warm), capture the mobile 390×844 screenshot, and compare the
   builder/summary region to the Figma mobile reference at >=90%.

## Risks

- The public Overpass mirrors are the slow dependency; a hard total budget is
  the only reliable fix. A weather-only score is honest and already part of the
  contract.
- Hiding Saved removes a visible feature on the current deployment; that is the
  requested behaviour until a real database is configured.
- The visual region must exclude live map tiles; compare the sheet chrome and
  the builder CTA, not the map.
- The e2e still uses fixtures for determinism; the live lane is the only proof
  of the real provider.
