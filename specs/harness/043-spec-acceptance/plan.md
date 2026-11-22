# 043 Spec Acceptance — Plan

## Shape

```
queue drains
   │
   ▼
swarm.acceptance
   ├─ discover product specs with a ticked task
   ├─ build frontend once, serve preview + fixture backend (own ports)
   ├─ node frontend/scripts/acceptance.mjs
   │    ├─ desktop + mobile screenshots
   │    ├─ global facts (console, tiles, duplicates, overflow)
   │    └─ per-AC probes from <spec>/acceptance.toml
   ├─ vision pass (free VL, JSON per AC, optional)
   ├─ verdict: FAIL if a probe failed or vision said fail
   ├─ write specs/product/<spec>/acceptance.md
   └─ append T<n> fix tasks for failing ACs
   │
   ▼
exit 0 (greenlight) | exit 1 (regressions, tasks queued)
```

## Steps

1. **Core + discovery** (`swarm/acceptance.py`): parse `AC-n` paragraphs;
   select `specs/product/*` with a ticked task; load optional `acceptance.toml`.
2. **Browser runner** (`frontend/scripts/acceptance.mjs`): one chromium
   context (geolocation granted, fixtures on), two viewports, screenshots,
   console/page errors, global facts, and the JSON check plan from Python.
3. **Probe kinds**: `exists`, `absent`, `count`, `min_count`, `text`,
   `value_set`, `route_request` (fills a field, waits for `/route`).
4. **Vision** (`litellm.completion`): free VL model, AC text + both PNGs,
   strict JSON; `SWARM_ACCEPT_VISION=0` / no key → skip.
5. **Verdict + report + queue**: merge, write `acceptance.md`, append one task
   per failed AC (next free `T<n>`, dedupe by AC + `acceptance` marker).
6. **Greenlight**: `make swarm-accept`; supervisor runs it on queue drain,
   re-enters the queue if fixes were queued, otherwise returns non-zero on FAIL.
7. **Config**: `VITE_BACKEND_URL` for the preview proxy; `SWARM_ACCEPT=0` off
   switch; `SWARM_ACCEPT_MODEL`, `SWARM_ACCEPT_VISION`, `SWARM_ACCEPT_QUEUE=0`.
8. **Tests + docs**: unit tests for parsing/merge/queue/supervisor hook;
   `docs/reference.md`, `GLOSSARY.md`, `changelog.md`.

## Risks

- **Cold build/serve time.** Build once, reuse healthy ports when present, tear
  down only what the pass started.
- **Vision noise.** Deterministic probes are the authority; vision `unclear`
  never fails an AC, and vision is skipped without a key.
- **Spec pollution.** Auto-queueing edits `tasks.md`; dedupe on `(AC, acceptance)`
  and never touch spec/plan prose.
- **Tasks without files.** A queued fix task names the evidence file when a
  probe knows it; otherwise the brief stays file-free (the delta guard fails
  open on an empty brief, and the planner names the file).
- **Port collisions.** Preview port is configurable; the backend defaults to
  8000 but `VITE_BACKEND_URL` lets the pass use its own fixtures server.
