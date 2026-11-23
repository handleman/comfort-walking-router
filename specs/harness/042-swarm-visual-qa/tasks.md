# 042 Swarm Visual QA — Tasks

- [x] T1 (AC-1, AC-2): Add `swarm/visual.py` — a Playwright runner that opens the built app (reusing `frontend/playwright.config.ts` / `vite preview`), screenshots at desktop and a mobile viewport, and collects deterministic DOM facts (map tile count, number of Start/End forms, leftover step labels, top-card button presence).
- [x] T2 (AC-3): Add a `visual-qa` crew/role that runs the runner and sends the screenshots + facts to a vision-capable model (`SWARM_VISUAL_MODEL`) for a verdict + findings.
- [ ] T3 (AC-4): Integrate into the flow after the verifier: run on UI tasks, record `run.json.visual_qa`, and on BLOCKED run the correction path or stop `visual_blocked` (like the verifier).
- [ ] T4 (AC-5, AC-6): Add the `SWARM_VISUAL_QA` off switch; unit-test the DOM facts (mocked Playwright output); `make swarm-test` green.
