# 041 Figma Redesign — Spec (draft)

> **Status: draft — do not queue.** The Figma file is still in preparation. Fill
> the link/frames below and run `hq design sync` (factory spec 057) before
> writing `plan.md`/`tasks.md`. The queue must not implement this from prose
> alone.

## What / Why

Replace the current visual layer of the comfort-walking-router with the
forthcoming Figma design while keeping every behavior and acceptance criterion
intact. The design is the source of truth for layout, color, type, spacing and
component states; the existing specs remain the source of truth for behavior.

## Inputs (to fill)

- **Figma file:** `<paste https://www.figma.com/design/<KEY>/... here>`
- **Frames:**
  - Plan / route (desktop + mobile): `<node>`
  - Walk mode (desktop + mobile): `<node>`
  - Saved routes / preferences (desktop + mobile): `<node>`
  - Empty/error/loading states: `<node>`
- **Design tokens:** colors, typography, spacing, radii, shadows (exported via
  `get_variable_defs` / the 057 cache).
- **Assets:** icons/illustrations (SVG preferred), licensed fonts.
- **Breakpoints:** desktop ≥1280, mobile 390 (the accepted stand sizes).

## Scope

- Frontend only (`frontend/src/**`): components, styles, tokens, assets.
- Keep the 040 layout regions (floating top card, map, sidebar, mobile drawer)
  or update `layout.toml` in the same change.
- Update the 042/043 design checks (`design.toml`) with the frame's tokens,
  regions and reference screenshots.
- No backend, routing, scoring, saved-routes or walk-logic changes.

## Non-goals

- New product behavior not present in the design.
- A second breakpoint or dark mode unless the design includes it.
- Replacing the map provider or the Leaflet stack.
- Pixel parity on devices/fonts the design does not specify.

## Acceptance Criteria

- [ ] AC-1: **Tokens.** The design's colors/type/spacing are CSS custom
  properties / Tailwind `@theme` tokens; `design.toml` token checks are green.
- [ ] AC-2: **Frames.** Each in-scope frame is implemented at its desktop and
  mobile size; region bounds match the reference within the declared tolerance.
- [ ] AC-3: **Responsive.** No overflow, no zero-size controls, the mobile drawer
  and desktop sidebar behave as in the design; layout facts have no overlaps.
- [ ] AC-4: **Accessible.** Every control keeps an accessible name; focus states
  are visible; contrast meets WCAG AA for text and controls.
- [ ] AC-5: **Behavior preserved.** 001–040 ACs and the e2e suite stay green;
  route → summary → walk → saved routes all work as before.
- [ ] AC-6: **Design checks.** The screenshot diff is within threshold (or the
  deviation is reported and accepted explicitly); `--strict` passes with the
  design checks covered.
- [ ] AC-7: **No regressions in the stand.** `make test`, `make swarm-health`
  and `make swarm-accept --strict` are green; mobile + desktop screenshots are
  attached to the acceptance report.

## Before queuing

1. Paste the file key + frame node IDs above.
2. Add the `design:` block to `swarm.yaml` (see `docs/figma.md`).
3. Run `hq design sync`; commit `designs/<key>/` (IR, brief, renders, lock).
4. Write `plan.md` (one phase per frame) and `tasks.md` (one task per AC/frame).
5. Add `design.toml` with the frame's tokens/regions/screenshot.
6. Only then let the queue pick the tasks up.

## Open questions

- Which seat/plan is available? (remote MCP works on all plans; a Full/Dev seat
  avoids limits)
- Are there Code Connect mappings or a component library to reuse?
- Which fonts are licensed and how should they load (self-host vs system)?
- Is dark mode or a tablet breakpoint in scope?
- Are the illustrations/icons final, and where do the source assets live?
