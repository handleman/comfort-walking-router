# Harness lessons (learned from runs)

Hard-won lessons from real runs — read before "fixing" the swarm. See [GLOSSARY.md](../../GLOSSARY.md) for terms and [README.md](../README.md) for the harness index.

- **Read the run before theorising.** `run.json` first (`status`, `reason_code`, `gates`, `usage.models`, `usage.by_role`, `cost`, `budget`), then `events.jsonl` (`at` deltas = per-call latency), then `shell_log.jsonl` (gate argv/exit/output). A pretty TUI error is only a rendering of one of those.
- **`reason_code` can lag the real stop.** 007-T5 ended `reviewer_no_verdict` while the actual cause was the per-task cost cap: QA was never called. Cross-check `cost` vs `budget.max_cost_per_task` and the log for `qa crew failed`. Budget stops now re-raise as `_BudgetExhausted` (terminal, reported as `budget_exhausted`), and the QA review is **not** budget-gated — it is local/free and decides work that is already paid for.
- **Fallbacks are per role with one configurable local target.** A coder transport blip must never move QA: 007-T4 lost 30 minutes because one global `activate_fallbacks()` put the reviewer on `qwen3.5:9b`, which looped over the report and never declared a verdict. Now `SWARM_LOCAL_FALLBACK_MODEL` (default `ollama/swarm-coder:latest`) is the fallback for every role, `SWARM_<ROLE>_FALLBACK_MODEL` overrides per role, and only a provider-wide quota wall switches all roles at once. A missing QA verdict is decided by the senior model (`SWARM_SENIOR_MODEL`), never a paid one.
- **Never conclude "the provider is slow" from one error string.** Measure: events carry `at`, and a 120.5 s failure is 2×60 s (one SDK retry), not a slow model. A *fix* generation is not a 1–7 s chat call — 60 s cut a real fix off twice in a row (007-T5), so the cloud timeout is 180 s with SDK retries off (the harness retries once and logs it).
- **Statuses name the loop, not the task.** `needs_human`/`crew_error` usually mean the harness stopped itself; read `fix_rounds`, `dev_attempts`, `senior_used`, `evidence_note`, and the gate tails before blaming the code.
- **A green task that "reopened" is usually a key mismatch.** 007-T5 was green on 2026-11-09 and re-ran the next morning because its trailer said `Swarm-Task: 007/T5` (the invocation prefix) while the queue looked up `007-live-position/T5`. Before assuming the spec changed, compare `git log --grep 'Swarm-Task:'` against `swarm/spec_loader.py` `spec_dir_name()`, and check `_open_task_ids()` in `swarm/flow.py`. **Check the ledger entry points at the artifact**: 007-T9's green commit (`1f4b3d9`) contains only Mapbox files — the integration test it claims was never written — so a hash match alone is not proof; `git show --stat <sha>` should show the files the brief names.
- **Green means the gates passed, not that the task was done.** Six 014 tasks were committed green; T2's `GET /geocode` was never mounted in `app/main.py`, T7's client targets a path and a response key that the pinned contract does not use, T8 wired no selection, and T6/T9 never landed — all green, because a *missing* piece produces no failing assertion. Before trusting a green commit, compare the files it touched with the files the brief names, and check the endpoint is actually mounted (`grep '"/geocode' app/main.py`). A scenario verifier (spec 019) is the systematic answer.
- **Watch which task a run actually is.** `meta.json` is authoritative: the queue advances past done-ledger entries, so `run.sh 007 T4` can execute T5. Checkpoints are plan-hashed (`restarting … plan changed`).
- **A conflicted `git stash pop` is not a merge conflict.** 2026-11-10: T8 (014) popped its stash onto the base it had just merged and conflicted on `App.svelte`; the harness printed `STASH RESTORE FAILED`, kept the stash, and left three `UU` stages in the tree — the next three runs gated around conflict markers. Preflight now blocks on `git diff --diff-filter=U`, and the stash is always archived as `refs/swarm/archive/<stamp>-<sha>` with `stash_conflict`/`stash_conflict_ref` in `run.json`. A conflicted restore is **resolved**, not parked: a `Stash Conflict Resolver` crew (read + edit only) re-applies the parked side on the newer tree, accepted only when no marker remains, only conflicted files were edited, and every gate is green; otherwise it falls back to `--ours` and records `stash_conflict_resolution` (`crew`/`ours`/`kept`) + `stash_conflict_note`. Orphaned `swarm-*` stashes are swept at kickoff (archived as refs, indexed in `swarm/runs/orphan_stashes.json`, then dropped; `SWARM_ARCHIVE_STASHES=0` disables). No human step, and no user stash is ever touched — inspect with `git show <ref>:<path>`, never `git stash pop`.
- **A stuck task is usually a missing report, not a hard problem.** 007-T9 (2026-11-10) burned five fix rounds on a broken test file: the report was rendered in gate order and cut at 9000 chars, so the vitest failure never reached the coder. The report now puts failing gates first with extracted `file:line: message` key lines (14k budget), and a fix round that changes nothing ends the round (`no_progress`). Read the report the coder actually receives (`run.json.qa_report` → `report_text`) before blaming the model.
- **Deterministic style failures are not coder work.** The harness repairs them itself: when the only red gate is a lint/format gate and its output names nothing but formatting, the flow runs `SWARM_STYLE_FIX_COMMAND` (`npm --prefix frontend run lint:fix`) and re-checks it (`run.json.style_autofix`). A red type check or red test is never treated as style — that is coder work.
- **A type error is not a QA round-trip.** 007-T9 (2026-11-11) spent three QA rounds and two coder rounds on `Property 'tick' does not exist on type 'PositionProvider'`: the checker named the file, the line and the cause, and the fix rounds still did not land it (one round changed no file at all → `no_progress`). The harness now runs the static checks itself right after the micro-steps and gives the coder the same `file:line: message` report QA would have given him, before QA is invoked (`run.json.self_check`). When a run is "stuck on a linter bug", look for the self-check record first: if it is absent, the run predates 017 or the phase is off.
- **The coder may not own the module the test exercises.** The same 007-T9 run wrote its own `frontend/src/lib/navigation/walkMode.ts` because the real store (`frontend/src/lib/walkMode.ts`, green in T6–T8) was not in the plan — a duplicate implementation that would have been committed as part of a *test* task. Before writing a module, check the spec's plan and `git log --grep 'Swarm-Task:'` for an existing owner of that path; the queue order (T6→T9) is not a guarantee that the earlier task landed.
- **A truncated read is a loop, not a hint.** 014-T1 (2026-11-12) spent 50 minutes and 229 calls on one wrong string. The read tool caps observations at 3000 chars and said "re-read with start_line/line_count" — so the coder asked for lines 1–500 of a 178-line file **seven times** and got the same first 85 lines every time, never seeing `search()` at line 169; it re-read, changed nothing, and the run ended `no_progress`. The truncation note now names the exact line to continue from (`CONTINUE with start_line=<n>`). When a run ends `no_progress`, check the read log for a repeated read of the same range before blaming the coder.
- **A `needs_human` run needs a reason you can copy.** The dashboard's `h` screen is not pasteable. Every run now writes `<run_dir>/human_log.txt` (stop reason, reason code, failing gates, verdict, changed files); `make swarm-log` prints it. Read that file first — it is the whole story in one screen.
- **Do not show a budget cap that cannot fire.** The panel read "tokens 1.7M / 2.0M 84.0%" for a run whose token/dollar caps are *not enforced* (`free_local_run: true`), which reads as "the budget stopped this". A free-local run now shows "no cap: free local run".
- **A red run needs a verdict most of all.** The reviewer got 9 iterations for 6 gates + `git status` + the verdict, so it re-ran `pytest` and never concluded: `review_verdict: "unknown"` left the fix rounds with no grounded reason. The budget is 12 and the verdict repair now runs on red runs too (it used to run only when the gates were green).
- **Measure with the replay set, not with memory.** `make swarm-bench` (020) renders the real prompts and reports from 12 frozen green runs with no model call. It is the only way to tell whether a change removed work or moved it; run it before and after, and use `SWARM_CONTEXT_COMPACT=0` / `SWARM_GATE_SELECT=0` / `SWARM_PROMPT_CACHE=0` to restore the old behaviour for an honest A/B. A token win that lowers the green rate is not a win; `make swarm-bench-live CASE=<id>` is the check that the loop still reaches green.
- **A red suite is four problems, not one.** 2026-11-15/16: one walk-mode task produced a stale test datum, two product defects and a harness argv that made every test fail for the wrong reason. A single fix loop solves them in the wrong place (edit the test, or edit the product to agree with a bug). 027 triages first and refuses any repair that deletes, skips or weakens a check — the marketplace lesson is the same: the model that writes the code must not grade the verification. If a run ends `e2e_weakened`, that is the guard working, not the model failing. **The first canary was repaired by the coder, not the phase** (2026-11-15: one broken `button.walk-start` selector, `e2e_self_heal: {}`, green) — the spec is in the coder's scope, so a same-task drift rarely reaches the phase. The guard therefore runs on *any* delta touching `frontend/e2e/`, not only inside the phase.
- **A resume can skip the very phase the guard checks.** 2026-11-15: `run.sh 007 T10`
  printed `resuming T10 after step 5/5`, then stopped `no_delta` in 2 s — it had
  reused a checkpoint from an attempt whose delta was reverted, so the coding phase
  never ran and the run could not possibly produce a delta. A checkpoint is only
  valid if the run can still vouch for it: `load_checkpoint` now refuses
  `completed == len(steps)` (nothing left to run → empty delta by construction) and
  an empty recorded `delta_hashes` (`hash_paths([]) == {}` compares equal, so a
  snapshot written after a revert looked fine). Both print
  `restarting <T>: <reason>`; check `run.json.recovery`/`recovery_note` before
  blaming a coder for "doing nothing".
- **An empty delta is a stop, not a verdict problem.** Two 014-T10 runs spent 21 and 28
  minutes, produced `changed: []`, and then paid the verifier to name the missing files.
  026's delta guard now stops `no_delta`/`delta_incomplete` before any judge. If a docs
  task has an empty delta, check `run.json.delta_guard` and `scope_extra` before
  blaming the model.
- **A spent wall budget must not become an unbounded call.** 007-T10 ran 2.7 h against
  an 1800 s bound and ignored SIGTERM: `remaining = budget - elapsed` went negative and
  `run_bounded` read `timeout <= 0` as "no bound". Only `None` is unbounded now, and the
  flow stops before a crew when the budget is spent. **And the process must leave when the
  record is written**: `main()` arms a 5 s daemon timer (`_exit_soon`), because a CrewAI
  worker stuck in an HTTP call held the run lock ~40 s after a 2026-11-15 wall-budget stop
  (SIGKILL was needed) and the same shape likely explains a 40-minute replay that had no
  run directory at all.
- **A docs task could never write its deliverable.** `DEFAULT_SCOPE` has no `docs/`, `README.md` or `changelog.md`, and the scope was task-blind, so two 014-T10 runs produced an empty delta and the verifier (correctly) blocked on files the brief named. `task_scope` now extends the base scope with the brief's own paths, per task. When a docs task ends with `changed: []`, check `run.json.scope_extra` and the write-tool refusals before blaming the coder.
- **Three shapes for one field means no shape is right.** 014-T1 was not a typo: `plan.md`, the green `contracts/geocode.json` and the coder's module each defined `Suggestion` differently (and the token variable a third way). Before blaming a coder for a contract mismatch, diff the three sources — `plan.md`, the committed contract, and the code — and pin one.
- **An unparseable verdict is not a pass.** 014-T10 attempt 1 committed green with three missing deliverables because the verifier ended on a tool call and `unknown` fell through as `PASS`. Every judge (verifier, QA, senior) now goes through `guards.resolve_verdict`: parse → one repair call → terminal stop with the raw tail in `run.json.judges`. If a green run's brief is not implemented, look for `judges.<kind>.terminal` or `review_note` before blaming the gates.
- **A correction can break the build after the self-check passed.** 014-T11's senior correction appended a duplicate style block to `App.svelte` (stray `air;`, orphan `</style>`) and the run parked a broken tree, because nothing re-checked the static gates after a correction step. `correction_reverted` reverts only that step's paths (archived in `<run>/reverted/`), ends the *correction* loop and **continues to QA** — the verifier's block stands, so the run ends `verifier_blocked` with gate evidence instead of a stop nobody can read (2026-11-15: three cases stopped `correction_reverted` with no QA verdict).
- **A cap that cannot fire is worse than no cap.** A paid planner + paid coder made `estimate_run_cost` return `None`, which silently disabled `SWARM_MAX_COST_PER_TASK`, and the dashboard showed `unknown` with no reason. Cost is priced per model now, and `usage.cost_unknown` + `unpriced_models` + the budget note name the model whose price is missing.
- **A walled provider is not a fallback.** 014-T10 burned 54 `429 free-models-per-day` errors and 20 minutes because the chain still offered providers with no key and every role retried the wall. Quota is now counted per provider with a terminal breaker, `llms._callable` filters the chain, and `make swarm-preflight` makes one 1-token call per role.
- **A green task can be an e2e claim nobody ran.** 010-T4 was green having touched only `frontend/e2e/helpers.ts`; the suite had four setup bugs and NYC-only fixtures. A brief naming `frontend/e2e/*` now needs a recorded Playwright execution (`reason_code=e2e_missing`, `make e2e`), and preflight checks the binary exists.
- **Name every file by its FULL path in a brief.** A brief that mentions a file
  bare (`App.svelte`) *and* by full path (`frontend/src/App.svelte`) makes
  `brief_paths` extract both, and the delta guard marks the bare one `missing` →
  `delta_incomplete`, even though the coder changed the file. (036-T1's
  `Button.svelte`, 040-T10's `App.svelte`.) Use `frontend/src/App.svelte`
  everywhere; never a bare filename.
- **A new component must be imported and rendered where it is used.** The coder
  created `BottomDrawer.svelte`/`ControlsContent.svelte` but never imported them
  in `App.svelte`, so they were orphaned and the verifier blocked (040-T3). Say
  "import and render in `<file>`" explicitly in the brief — the coder's job is
  create **and** wire, not just create.
- **Removing the only trigger of a behaviour leaves the app unable to do it.**
  040-T9 removed the old `Find route` form + `submitRoute()` (the only
  `fetch('/route')`) and no task replaced the trigger, so the app could not plan
  a route at all — found by manual QA. A task that removes a control must name
  its replacement in the same brief, or a follow-up task must own the new
  trigger.
- **A component rendered in two places is a duplicate, not a feature.**
  `WalkControls` was rendered by `ControlsContent` *and* by a leftover
  `<section class="walk">` in `App.svelte`, so the sidebar showed Start/Stop
  twice. When wiring a component into a container, delete the old inline
  rendering of the same component.
- **A wiring brief must name only the files that must change.** 040-T11's brief
  named the two components being imported *and* `frontend/src/App.svelte`; the
  delta guard then required all three to change, and a wiring task only changes
  `App.svelte` → `delta_incomplete`. Name other files by component name, never
  by path, unless the task must edit them.
- **The coder imports but does not render.** 040-T11 passed the verifier with an
  import and no template tag twice; the script-side import is easy, the markup
  render + deleting the inline block is where it stops. A wiring brief must name
  the exact template block to replace/remove ("render the tags in `<main>` and
  delete `<section class="bottom-drawer">`"), not just "import and render".
- **A verify-only task can never satisfy the delta guard.** 040-T12's deliverable
  is running the gates, so its delta is empty by construction → `no_delta`. Do
  not queue verify-only tasks: fold verification into the implementation task,
  give it a real file deliverable, or run it by hand. Keep verify/regression
  tasks **last** in `tasks.md` — a queue stops on them before the work.
- **0 ms gate failures are infrastructure, not code.** All 12 e2e tests failed in
  0–2 ms after an `npm ci` bumped Playwright: `chromium_headless_shell-1255` was
  missing. `e2e.browsers()` used `any(exists)` across the install locations, so
  a present full chromium hid the missing shell; every location must exist now
  (`swarm/e2e.py`, test in `test_preflight.py`). Read the first failure's error
  text before touching tests.
- **A crash inside the linter is not a coder failure.** `@typescript-eslint/
  no-unused-vars` threw `TypeError: Cannot read properties of undefined
  (reading 'type')` on a `.svelte` file; the run ended `no_progress` although the
  verifier had passed. A gate that prints a stack trace plus "Occurred while
  linting" is tooling: fix the config (the rule is off for `.svelte`; the base
  rule covers it), don't send the coder another round.
- **A provider wall must be classified as quota, not retried.** OpenCode Go's
  "usage limit reached (weekly)" was not in `QUOTA_HINTS`, so the pilot retried
  until `crew_error` instead of stopping `quota_exhausted`. `retry.py` now
  matches `usage limit reached` / `GoUsageLimitError` (test added); add a new
  provider's exact wall text when onboarding it.
- **`svelte-check` warnings are evidence of an unfinished removal.** 31 "Unused
  CSS selector" warnings after 040-T11 pointed at the styles of the inline
  controls that were supposed to be gone — cheap proof a removal task is not
  done. Read the warnings, not just the error count.
- **Orphaned-but-committed components still exist.** `BottomDrawer.svelte` and
  `ControlsContent.svelte` were committed by an earlier run but never imported;
  they are not scratch files. Check `git ls-files <path>` before deleting
  anything that looks abandoned.
- **Manual QA needs the backend, and `vite preview` is not the source.** With
  the backend down, `/route` 500s and unproxied paths (`/suggestions`) return the
  SPA HTML; and `vite preview` serves the prebuilt `dist/`, so an old build looks
  like a fresh bug. Run `make dev` (or start uvicorn) and compare `dist/` vs
  `src/` mtimes before believing a QA finding.
## 043 Spec Acceptance (final greenlight)

- New: `swarm/acceptance.py` — end-of-batch spec acceptance pass for product specs with built work.
  - picks specs that have ticked tasks (skips harness), builds frontend once, drives it via
    `frontend/scripts/acceptance.mjs`, checks each AC (exists/absent/count/text/value_set/route_request),
    global browser facts (tiles, leaflet, duplicate buttons, zero-size inputs, overflow,
    console errors), and vision verdict (free VL model advisory).
  - writes `<spec>/acceptance.md`, appends one unchecked `T<n>` fix task per failing AC
    (dedupe open `acceptance`-tasks), exits non-zero on FAIL.
  - wired into supervisor as AC-7: when queue drains (`outcome.action == "continue"`), runs
    `make swarm-accept` (or `python -m swarm.acceptance [--no-vision] --no-queue ...`).
  - env overrides: `SWARM_ACCEPT=0` disables hook, `SWARM_ACCEPT_VISION=0` skips vision call,
    `SWARM_ACCEPT_QUEUE=0` only reports.
- New: `frontend/scripts/acceptance.mjs` — Node Playwright runner reusing fixture backend
  (`ROUTE_FIXTURES=1`), two viewports, screenshots, deterministic checks, JSON output.
- New: `swarm/tests/test_acceptance.py` — 26 unit tests covering parsing, discovery,
  merge, report, queue, vision.
- Changelog: 758 swarm tests pass; 732 + 26 = 758 total.

## 2026-11-25 — e2e migration, a dead map, and a reviewer that blocked without evidence

The swarm failed T6 (e2e spec migration) three times, the e2e suite exposed a dead
map, T23 (map) went green only after two tunings, and T6 needed a brief fix. Lessons:

- **A reviewer block must be grounded in recorded evidence, not prose.** T23 ended
  `review_verdict=blocked` with cause `test` while every recorded gate was green,
  the verifier passed, and **no `pytest` run existed** in `shell_log.jsonl`. The
  fix round then chased that non-existent failure, changed nothing, and the run
  died `no_progress`. `block_is_grounded` matched nothing concrete yet a fix round
  still ran. *Improve:* check the block against the recorded gates — all green +
  verifier pass + a block with no failing gate/AC/file:line is
  `reviewer_blocked_ungrounded`; stop, do not start a fix round.
- **Judgement roles need reasoning, not the cheapest tier.** The reviewer was
  `mimo-v2.6-flash` and blocked spuriously; `qwen3.8-flash` (the verifier's model)
  let the same work pass. 047's profile put the cheap flash on judgement roles —
  invert it: cheap on mechanical, reasoning on judging.
- **"Use X from `path`" is a reference, not a required change.** T6 named
  `frontend/e2e/helpers.ts` (the already-implemented `planRoute`); the delta guard
  read the backtick path as required, saw it untouched, and stopped
  `delta_incomplete` — after the coder had migrated all five specs. The 030
  read-verb rule covers "Read X"; extend it to "use/from/see X".
- **Off-scope e2e edits impose e2e on non-e2e tasks.** T23's coder edited
  `frontend/e2e/helpers.ts` and `app/saved_routes.py`; the helper edit flipped
  `e2e_required` on a map task, which then could never record a green suite.
  *Improve:* a per-task write allowlist from the brief, reverting other writes
  (global scope is too coarse); `e2e_required` should key off the task's target.
- **A launch failure is `env`, not `unclassified`.** `playwright.config.ts` had
  `webServer.cwd: 'frontend'` → `frontend/frontend` → `spawn /bin/sh ENOENT`. The
  self-heal saw no parseable failures, stopped `e2e_unclassified`, and hid the
  cause for three runs. A spawn/launch error is class `env` with the error text;
  "no failures parsed" must say whether the suite ran at all.
- **The e2e roster cap silently refuses big migrations.** `SWARM_MAX_INNER_TASKS`
  defaults to 3; >3 failures → `e2e_roster_overflow`, no repair round. An
  11-failure stale suite was unwinnable. Default higher, or batch the roster.
- **Stale test config is silent paralysis.** The suite could not launch, and
  nothing noticed until an explicit `make e2e`. A `make swarm-health` (or
  preflight) smoke of the suites would fail fast instead of on the one task that
  owns e2e.
- **A dead map passed "gates".** `npm check/test` and the verifier were green
  while `.leaflet-container` was absent (0 tiles, 0 markers). Only the e2e suite
  and the acceptance global facts (`leaflet`, `tiles`) caught it — keep those
  facts running after every green task.
## 2026-11-26 — a sleeping laptop looks exactly like a hung model

T6's first verified migration run lost 55 minutes to a wall of silence, then
recovered in seconds. Two lessons, both about signals the harness was missing.

- **Host sleep is a silent stall, and the harness blamed the model.** The
  verifier (`opencode-go/qwen3.8-flash`) was mid-call from 23:45:01; the next
  event of any kind was `llm_timeout` at 00:40:40 — 55 minutes with zero LLM,
  tool or shell events. `SWARM_LLM_TIMEOUT_SECONDS` is 180 s and the crew cap is
  300 s, so neither could explain it: the process was suspended with the Mac.
  On wake CrewAI surfaced `Failed to connect to OpenAI API: Request timed out`,
  which reads exactly like a provider hang. The first diagnosis ("the Go API is
  slow") was wrong; the run's own `mono` timestamps proved a gap, not latency.
  *Improve:* (a) keep the host awake for the life of a flow —
  `swarm/power.py` spawns `caffeinate -ims -w <pid>` on macOS
  (`SWARM_KEEP_AWAKE=0` off, no-op elsewhere); (b) when consecutive events show
  a `mono` gap above a threshold with no tool activity, record
  `host_suspended` in `run.json` instead of a model error, so the operator sees
  the machine slept rather than a provider failing.

- **A deterministic guard is an invariant the brief must state.** T6's migration
  was correct — all five specs converted, every gate 0, review `pass` — and was
  reverted by the e2e weakening guard for dropping one assertion in `search`
  (10→9) and `preferences` (7→6) while removing the old `.result` checks. The
  guard was right to be loud (a spec that deletes checks is how a suite gets
  weakened), but the brief never said the count was part of the contract, so the
  coder had no way to know. *Improve:* any brief that edits `frontend/e2e/*`
  states the invariants the guards enforce — "keep or raise each spec's
  `expect(...)` count", "no test removed or skipped", "only the files this task
  owns". A guard that can revert a green run must be legible in the task text,
  or it converts a correct run into a round trip.

- **Confirmed good:** 053's new machinery behaved as designed in its first live
  run — the allowlist kept the coder from wandering (no `helpers.ts` edit), the
  reference-vs-required rule let the five-spec delta go green, and the weakened
  verdict was recorded loudly (`e2e_weakened` with the exact per-file counts)
  instead of an opaque `e2e_unclassified`. The remaining cost was knowledge, not
  code.
