# 041 Figma Redesign — Plan

## Approach

The design is implemented as a set of small, green-at-each-step changes. The
existing behaviour (routes, comfort, walk mode, saved routes, geolocation) is
not rewritten; the UI is re-shelled around it and the existing hooks are kept as
long as possible. Visual details come from [`design-spec.md`](design-spec.md),
which is the textual transcription of the three frames.

1. **Foundation (T1)** — tokens, Inter, the top nav, the desktop shell and the
   mobile map layering. The old controls content stays inside the new panel so
   every gate keeps passing.
2. **Comfort panel (T2)** — move the endpoint card into the desktop panel and
   add the weather advice, the shade segment, Quieter streets and Reset, wired
   to the existing preferences API. Add the API's `balanced` value (scoring
   already supports it) and update the preferences e2e.
3. **Desktop routes (T3)** — the "Choose your walk" card, the honest single
   route, the filled CTA, the comfort legend and the compact "Why this route?"
   factors. Preserve `section.route-summary`, `.chip`, `.comfort-segments`,
   `ul.factors`, `.comfort-legend` and the walk buttons.
4. **Mobile results (T4)** — the bottom sheet "Your kind of walk": handle,
   title, preference summary, route card, CTA, auto-open on a route, collapsed
   before it. Update the mobile e2e.
5. **Mobile preferences (T5)** — the 604 px "Walk your way" sheet with the
   weather card, shade segment, quieter switch, Apply, scrim and focus trap.
6. **Map + nav actions (T6)** — locate/zoom, attribution, route badge,
   destination callout, Saved walks and How it works dialogs, focus styles and
   reduced motion.
7. **Verification (T7)** — a full gate + e2e pass, the design checks, and the
   acceptance report; fix only what the checks expose.

## Ordering and green-at-each-step

Each task must leave `pytest`, `ruff`, `mypy`, `npm run check`, `npm run lint`,
`npm test` and `npm ci --dry-run` green. UI tests are updated in the same task
that changes the control they exercise; the 040 layout selectors are kept (the
top card is the endpoint card in both surfaces). The per-feature acceptance hook
is disabled for the run (`SWARM_ACCEPT=0`) because a half-redesigned app cannot
satisfy all ACs after T1–T5; the final `make swarm-accept --strict` is the gate.

## Caching and the design lane

`hq design sync` has written `designs/jFwR8VpN5Nls2RjN2Ifh4y/` (lock, IR,
renders, brief). The queue reads only that cache; it never calls Figma. The
design brief is injected into the planner/coder prompts; `design-spec.md` adds
the exact values the brief does not carry (colours, sizes, copy, states).

## Risks and mitigations

- **Cheap coder + visual work.** The brief is precise and split by surface; the
  senior role can escalate, and T7 + the operator's final acceptance catch
  drift.
- **040 contract drift.** The top card moves into the sidebar on desktop, so the
  operator updates 040's `layout.toml`/`acceptance.toml` to the new regions
  (same test ids); the 040 prose is left alone to avoid reopening its done
  ledger.
- **Preferences need Postgres.** Acceptance runs without a DB; the checks assert
  the controls exist and are accessible, and the e2e preferences test keeps its
  existing DB skip.
- **No route alternatives.** The design's second card/fastest row are omitted
  and recorded as deviations; no fake numbers.
- **Fonts.** Inter is self-hosted via `@fontsource-variable/inter`; the fallback
  stack keeps the app usable if the font fails to load.

## Verification

- `pytest -q`, `ruff check .`, `mypy app tests`, `npm --prefix frontend run
  check`, `lint`, `test -- --run`, `npm ci --dry-run`.
- `make e2e` (fixture backend) with the updated selectors.
- `make swarm-accept --strict` and `hq design check` with the cached frames.
- Visual: desktop 1280×800 and mobile 390×844 screenshots compared with
  `designs/jFwR8VpN5Nls2RjN2Ifh4y/6-61.png`, `6-53.png`, `6-57.png`.
