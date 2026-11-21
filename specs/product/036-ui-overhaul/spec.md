# 036 UI Overhaul — Spec

Product spec (the comfort route guide): a guided, mobile-first interface so the
walk is planned, reviewed and started in clear steps instead of one overflowing
sidebar.

## Problem

The whole app is one `aside` column: Preferences, a geolocation notice, the
Start/End form, Saved routes, and — once a route exists — the entire result
(chip, save, stats, score, comfort legend, per-segment list, walk controls,
comfort factors, arrival card) are all visible at the same time. The result is
what the operator called it: **bleak** (no visual hierarchy, default browser
chrome) and **overflowed with controls** (nothing is gated behind a step or a
collapse). Two specific complaints: the **"use my location" control sits below
the form instead of next to the Start field**, and the layout is a fixed
desktop two-column grid even though the walk happens on a **phone**.

## Goal

A step-based, mobile-first flow — **Plan → Review → Walk** — with secondary
controls collapsed behind headers, an inline "use my location" button on the
Start field, and a coherent visual layer (spacing, hierarchy, colour) so the app
no longer looks like an unstyled prototype. Every behaviour the gates cover
(route, comfort profile, walk mode, saved routes, geolocation) keeps working.

## Research (Svelte, 2026)

| Option | Model | Fit |
| --- | --- | --- |
| **shadcn-svelte** | copy-in components on Bits UI (accessible primitives) + Tailwind | Svelte-native, own the code, ships Accordion/Collapsible, Card, Button, Select — the best "polish + a11y" baseline. Requires adding Tailwind. |
| Skeleton | opinionated Tailwind design system (Zag.js) | cohesive, but heavier/opinionated for a small single-screen app. |
| DaisyUI | CSS-only Tailwind plugin | fast, but no interactive behaviour (we'd hand-roll the accordion/stepper anyway). |
| Bits UI / Melt UI | headless primitives only | the a11y layer; shadcn-svelte already wraps Bits UI. |

**Pattern:** progressive disclosure. A 3-step stepper (Plan / Review / Walk) is
the market-standard answer to "all controls at once"; accordion sections are the
standard answer for secondary panels (Preferences, Saved routes).

## Recommendation

1. **Pattern first, library second.** Reorganise into three steps (Plan, Review,
   Walk) with a visible step indicator, and collapse Preferences / Saved routes
   behind their headers. This is library-agnostic and is most of the fix.
2. **Tailwind CSS + hand-rolled primitives** (a `Button`, `Card`, `Collapsible`,
   and a small stepper) for the visual layer. **Svelte 5 + shadcn-svelte is
   rejected**: the Svelte 4→5 migration broke the app at runtime (`effect_orphan`
   — the form never rendered and 12/12 e2e failed), and the swarm failed the
   migration twice. Svelte 4 + Tailwind keeps every UI goal without that risk.
3. **Responsive, desktop-first:** the two-column layout (controls left, map
   right) is primary; below ~768 px the map is full-bleed and the controls become
   a bottom sheet/panel.

## Scope

- `frontend/src/App.svelte` — restructure into the step flow + collapsible
  sections; move "use my location" inline with the Start field.
- Responsive layout: map full-bleed on phone, controls as a panel/sheet.
- The stepper + collapsible + button/card primitives (hand-rolled with Tailwind).
- Visual tokens: spacing, type scale, colour (comfort-band colours stay).

## Non-goals

- Changing the backend, the API contract, or the walk/comfort logic.
- Adding a router or new pages (it stays a single-page app).
- Auth/accounts.

## Acceptance criteria

- **AC-1 — Steps.** The UI shows three steps — Plan (Start/End + preference),
  Review (route stats, comfort score, bands, factors), Walk (live position,
  off-route/reroute, arrival) — with a visible step indicator, and only the
  active step's controls are prominent.
- **AC-2 — Collapsed by default.** Preferences and Saved routes are collapsed
  behind their headers and expand in place; the primary flow never scrolls past
  them to reach the route form.
- **AC-3 — Inline location.** The "use my location" control is attached to the
  Start field (same row), not a separate notice below the form.
- **AC-4 — Responsive, desktop first-class.** The desktop two-column layout
  (controls panel left, map right) is retained as the primary experience; on a
  phone viewport (~768 px) the map becomes full-bleed and the controls a
  collapsible bottom sheet. Both layouts are supported, not one at the other's
  expense.
- **AC-5 — Not bleak.** Coherent spacing, type hierarchy and colour; controls
  read as a designed UI, not default browser elements.
- **AC-6 — No regression.** `make e2e` (12) and `npm run check`/`npm test` (93)
  stay green, and the route/comfort/walk/saved-routes behaviours are unchanged.

## Success definition

A new user on a phone can, without reading anything: locate themselves, pick an
origin and destination, review the route and its comfort in one clear step, and
start the walk — with secondary features tucked away and no wall of controls.
