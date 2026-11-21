# 042 Swarm Visual QA — Plan

## Shape

```
coder (UI task) → self-check → verifier → [ NEW: visual-qa ] → QA (gates) → green
                                   ↑
                          Playwright: open built app,
                          screenshot desktop + mobile,
                          DOM checks (tiles/forms/buttons),
                          vision model reads the screenshots
                                   ↓
                          run.json.visual_qa = {screenshots, findings}
                          BLOCKED → correction / visual_blocked
```

## Steps

1. **A browser runner** (`swarm/visual.py`): given a built app (reuse
   `frontend/playwright.config.ts` / `vite preview` + the fixture backend),
   screenshot at desktop (e.g. 1280×800) and a mobile viewport (e.g. 390×844),
   and collect deterministic DOM facts: `.leaflet-tile` count, number of
   Start/End forms, presence of leftover `PLAN`/`REVIEW`/`WALK` labels, and
   whether the top-card buttons resolve to real elements.
2. **A `visual-qa` crew** (like the 019 verifier): a read-only agent that runs
   the browser runner and then sends the screenshots + facts to a vision model
   ("is the map rendered? are the controls visually divided? do the buttons look
   active?") for a verdict + findings.
3. **Flow integration**: run it after the verifier (and after a UI fix round),
   gate it with `SWARM_VISUAL_QA`; record `run.json.visual_qa`; a `BLOCKED`
   verdict feeds the correction path (same as the verifier) or stops
   `visual_blocked`.
4. **Vision model routing**: use a vision-capable model for the visual agent
   (e.g. `opencode/nemotron-3.5-super-vl-free` or `gemini-4-argon`), routed via
   the existing `llms` layer with its own env (`SWARM_VISUAL_MODEL`).
5. **Tests + off switch**: unit-test the DOM facts (mocked Playwright output);
   `SWARM_VISUAL_QA=0` disables; `make swarm-test` green.

## Risks

- **Browser cost/latency**: Playwright + screenshots add time per UI task; keep
  it to one desktop + one mobile shot and cache the build.
- **Vision model noise**: a vision pass can over-report; keep the deterministic
  DOM checks as the authority and the vision pass as advisory findings.
- **Headless vs real**: Playwright headless is fine for rendering; it won't test
  real geolocation (that stays a human gate).
