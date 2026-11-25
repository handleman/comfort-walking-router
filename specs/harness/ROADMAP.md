# Harness implementation order

**Revised 2026-11-25** after the T23/T6 session. Follow top to bottom; update the
status box as work lands.

Status: `[ ]` not started · `[~]` in progress · `[x]` done · `[-]` dropped.

## Done

- `[x]` **051** acceptance artifacts commit — `0855cbc`.
- `[x]` **Bookkeeping** — `2e6aeb3` (ticked 042 T1/T2, 043 T1–T6/T8, 044, 045).
- `[x]` **052** layout geometry + control presence — `3d63342` (live
  `layout_failures: NONE`).
- `[x]` **040 T23** the map never initialised (`onDestroy` inside `onMount`) —
  swarm-authored `c7b559c`.
- `[x]` cost bug: `usage._rate` missed the `opencode-go/` prefix, so the dollar
  cap could not fire — fixed.
- `[x]` reviewer model `mimo-v2.6-flash` → `qwen3.8-flash` (it blocked without
  evidence). Lesson: judgement roles need reasoning, not the cheapest tier.

## Phase A — make the harness trustworthy (now)

1. `[~]` **053 swarm hardening (2026-11-25).** Grounded reviewer blocks (a
   green-gates block with no evidence must not start a fix round); reference-vs-
   required paths in the delta guard; per-task write allowlist; e2e launch
   failure = `env`; roster cap + `make swarm-health`. *Design: `specs/harness/
   053-swarm-hardening-2026-11-25/`.*
2. `[ ]` **Re-run T6 (e2e specs) + T24 (acceptance fix)** with 053 in place —
   both are verification-shaped, which is what 053 hardens. The coder's partial
   migration was reverted (a repeated lint/verifier block).
3. `[ ]` **`make swarm-health`** — one command that runs `pytest` + the e2e
   suite so a broken test stand fails fast.

## Phase B — close cheap leftovers

4. `[ ]` **047 leftovers** — timeouts into `Profile`, fallback-id validation,
   `flow._role_provider`, docs. (Cost prefix + reviewer model already done.)
5. `[ ]` **050 leftovers** — vcrpy cassette (or fixture-backed parse test) + the
   four-state Playwright geolocation contract.

## Phase C — productization (the original goal, last)

6. `[ ]` **048 Phase 2–3** — `src/swarm/` layout, `hq` CLI (`[project.scripts]`),
   `swarm.yaml` contract, driver relocation.
7. `[ ]` **048 Phase 7** — create `handleman/handleman-hq`, push the filtered
   228-commit history, tag `v0.2.0`, app pins `git+…@v0.2.0`.
8. `[ ]` **038** — any ejectable-contract bits not folded into 048.

## Open 053 follow-ups (from the session)

- `[ ]` **042 T3/T4** visual phase integration — `_visual_phase` is a stub.
- `[ ]` **043 T7** acceptance re-queue — the supervisor does not re-enter the
  queue after queuing fixes.
- `[ ]` **049 T8** real-run verify.
- `[ ]` **`done.json` cache key** uses the invocation prefix (`040/T23`) while
  trailers are canonical; `is_done` is right via trailers, but tooling lies.

## Known issues

- Go-API timeouts make runs slow (a T6 run reached 50 min); if they persist,
  raise the LLM/crew timeouts or move a role to a faster model.
- `tasks.md` checkboxes are intentionally stale; the commit-trailer ledger is the
  source of truth (`make swarm-report`, not the checkboxes).

## Dependencies

```
053 ─→ T6 + T24 ─→ swarm-health
047 ─────────────────────────→ 048 (Phase 2-3) ─→ 048 (Phase 7)
050 (parallel, independent)
```
