# 042 Swarm Visual QA — Spec

Harness spec (control plane; the queue never runs it).

## Problem

The swarm verifies work with **tests and static checks** (`npm test`, `npm run
check`, `npm run lint`), and the 019 verifier checks that the code matches the
brief. None of them look at the **rendered UI**. So the 040 Google-Maps work
landed "green" while being visually broken:

- the Leaflet map loaded **0 tiles** (blank grey box) — no test counts tiles;
- the controls were **duplicated and not visually divided** — no test checks
  layout;
- the top-card **buttons did nothing** — no test clicks the real buttons.

The built-in browser visual check (done by hand) caught all three instantly.
The swarm needs that check as a first-class step.

## Goal

A **visual testing agent** in the swarm that, for any UI task, opens the built
app in a browser, screenshots it (desktop **and** mobile widths), and verifies
the rendering — reporting visual findings the way the verifier reports code
findings, so a visually broken UI can never be "green".

## Investigation

- **Playwright** is already in the repo (the `make e2e` suite, `frontend/`), and
  `playwright.config.ts` already boots a fixture backend + `vite preview`. It can
  screenshot desktop and mobile viewports and inspect the DOM (e.g.
  `.leaflet-tile` count, duplicate selectors).
- **Vision models** with image input are available and priced per 1M tokens
  (input is what matters — screenshots are token-heavy): **`opencode/nemotron-3.5-super-vl-free`**
  is **free** ($0/$0) and explicitly vision-language; `claude-haiku-5-5`/`gpt-6-luna`
  are $0.10/M in / $0.50/M out; the rest (`gemini-4-argon`, `grok-4.7`,
  `claude-sonnet-5-5`, …) are $2–8/M in. So the agent can *look* at the
  screenshot and describe/flag issues — the free VL model is the cost-effective
  pick, with `claude-haiku-5-5` as the fallback.
- **Mobile widths**: emulate with Playwright's viewport (or a temporary iframe) —
  the same technique the AGENTS.md visual-check rule prescribes.

## Proposal

1. **A `visual-qa` agent/role** in the swarm (a crew like the 019 verifier), that
   runs after a UI task's coder work and before green.
2. **A browser tool** for it: open the built app (via the existing
   `playwright.config.ts` / `vite preview`), screenshot at desktop + a mobile
   viewport, and read the DOM (`.leaflet-tile` count, duplicate form/control
   selectors, clickable elements' handlers).
3. **Visual checks** (deterministic, first): map tiles > 0; exactly one form; no
   leftover step labels; the controls are visually separated (distinct
   sections); the top-card buttons resolve to elements that respond.
4. **A vision pass** (second): feed the screenshots to a vision model ("does the
   map render? are the controls visually divided? do the buttons look wired?")
   and record the findings.
5. **Report + integrate**: `run.json.visual_qa` records screenshots + findings;
   a `BLOCKED` visual verdict runs through the same correction path as the
   verifier (or stops with `reason_code=visual_blocked`), so a visually broken
   task cannot be green.

## Non-goals

- Pixel-perfect/visual-regression baselines (this is "is it obviously broken",
  not a diff against golden images).
- Replacing `make e2e` (assertion-based) — this complements it.

## Acceptance criteria

- **AC-1 — A visual agent exists.** The swarm has a `visual-qa` role that, for a
  UI task, opens the built app and screenshots it at desktop and mobile widths.
- **AC-2 — Deterministic visual checks.** It checks map tiles loaded, no
  duplicated form/controls, and the controls are visually separated; these are
  recorded as pass/fail in `run.json.visual_qa`.
- **AC-3 — Vision interpretation.** The screenshots are given to
  **`opencode/nemotron-3.5-super-vl-free`** (free, vision-language; fallback
  `claude-haiku-5-5`) which flags obvious visual breakage (blank map, overlapping
  controls, dead buttons); its findings are recorded in `run.json.visual_qa`.
- **AC-4 — Blocks green.** A visually broken task is not green: it stops with a
  typed reason (`visual_blocked`) or runs the correction path, like the verifier.
- **AC-5 — Off switch.** `SWARM_VISUAL_QA=0` disables it (A/B).
- **AC-6 — No regression.** `make swarm-test` green; the e2e suite still runs.

## Success definition

A UI task that renders a blank map or duplicated controls can never be reported
green — the visual agent sees it and stops it, exactly as a human tester would.
