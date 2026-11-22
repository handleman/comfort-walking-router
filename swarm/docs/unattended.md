# Unattended operation and tuning

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

### Cost routing (015 D2)
- Non-trivial steps (existing file, >1 file, frontend/type-checked path, logic/
  tests/API/DB wording, or any retry) use the paid coder.
- Trivial steps (one new small file, mechanical wording) use the local coder;
  a trivial step that fails is retried paid (`swarm/routing.py`).
- `SWARM_LOCAL_FIRST=0` or `SWARM_PAID_ALWAYS=1` forces paid everywhere.
- `usage.by_role` / `usage.by_step` record model, tokens, and cost per call;
  `SWARM_MAX_COST_PER_TASK` (0.15) and `SWARM_MAX_SECONDS_PER_TASK`
  (1800s) bound a single task without touching the run budget.
- **Budgets stop spending, never verification.** A tripped budget re-raises as
  `_BudgetExhausted` and is reported as `budget_exhausted` (007-T5 reported
  `reviewer_no_verdict` instead, because QA was skipped by the cap). The QA
  review is not budget-gated: it is local/free and decides work already paid for.
- `make swarm-report` prints cost per green task, tokens per role, fix-round
  rate, stop reasons, and p50/p90 duration.

### Running unattended (overnight)

```bash
make swarm-night      # caffeinate -is + swarm.supervise (auto-resume + retries)
```

A locked screen is harmless; **system sleep** is what kills a run. Keep the Mac on
AC power, leave the lid open, and start it inside `tmux`:

```bash
tmux new -s swarm 'make swarm-night'
```

Full procedure, verification, recovery states, and knobs:
`docs/runbooks/overnight-runs.md`.

### Tuning (015)

Thresholds are derived from the recorded runs, not guessed. Re-derive them any
time with `make swarm-report` (24 green tasks at tuning time: cost p50 $0.0097 /
p90 $0.0295, duration p50 237s / p75 454s, fix rounds 0:11, 1:5, 2:3).

| Knob | Value | Rationale |
| --- | --- | --- |
| `MAX_FIX_ROUNDS` | 3 | 19/24 green tasks converge in ≤2 QA rounds; 3 covers the tail without paying for a 4th. |
| `DEV_ATTEMPTS` | 2 | Retries resume finished steps, so a third full phase only re-reviews. |
| `STEP_ATTEMPTS` | 2 | Attempt 2 already switches a trivial step to the paid coder; provider retries live inside `_kickoff` (3 with backoff). |
| `SENIOR_ATTEMPTS` | 2 | Free model, but two passes are the empirical limit. |
| QA `max_iter` | 9 | 5 gates + `git status` + verdict + margin; the old 5 made QA skip a gate and triggered the harness fallback. |
| `SWARM_MAX_COST_PER_TASK` | 0.15 | 007-T5 spent $0.0624 on five paid steps, then the $0.06 cap blocked its QA review. A task with one fix round now fits. |
| `SWARM_MAX_SECONDS_PER_TASK` | 1800 | p75 is 454s; three QA rounds on a slow local model still fit. |
| `SWARM_MAX_COST_USD` | 3 | ~100 green tasks at the current median. |
| `SWARM_MAX_TOKENS` | 2,000,000 | 2.6× the p90 green task (768k). |
| `SWARM_MAX_RUNTIME_SECONDS` | 14400 | 4h wall clock on a slow machine. |
| QA report tails | 4k/gate, 9k prompt | Failure output is enough to investigate; the coder is paid per token. |
| Supervisor | 30s base, 600s cap, 3 attempts, 20 rounds | A 5-minute task retries at most ~10 minutes apart; parked tasks let the queue move on. |
| `SWARM_LOCAL_FALLBACK_MODEL` | `ollama/swarm-coder:latest` | One local model every role falls back to when the cloud is unreachable; per-role `SWARM_<ROLE>_FALLBACK_MODEL` still overrides. |
| `SWARM_OLLAMA_TIMEOUT_SECONDS` | 1800 | Local generation at 64k context legitimately ran past 300 s (two `litellm.Timeout` on 2026-11-10); 30 min bounds a hang without cutting a real answer. |
| `SWARM_STYLE_FIX_COMMAND` | `npm --prefix frontend run lint:fix` | The harness repairs a style-only gate failure (Prettier/ESLint) instead of spending a coder round on a wrap. |
| `SWARM_LLM_TIMEOUT_SECONDS` / `SWARM_LLM_MAX_RETRIES` | 180 / 0 | Small calls return in 1–7 s, but a fix generation on a big prompt legitimately runs past 60 s (007-T5 saw 6 failures at exactly 2×60 s). SDK retries off: the harness retries once, visibly, then falls back per role. |
| `SWARM_DELTA_GUARD` / `SWARM_JUDGE_FAIL_CLOSED` / `SWARM_CORRECTION_GUARD` | `1` | 026 off switches: empty-delta stop, fail-closed judges, correction regression revert. `0` restores the pre-026 behaviour (A/B only). |
| `SWARM_QUOTA_BREAKER` / `SWARM_QUOTA_LIMIT` | `1` / `3` | Quota errors per provider before the run stops `quota_exhausted`; `SWARM_QUOTA_BREAKER=0` restores the retry loop. |
| `SWARM_E2E_EVIDENCE` / `SWARM_PREFLIGHT_FACTORIES` | `1` | Require a recorded Playwright run for a `frontend/e2e/*` task; build the crews' real role factories in preflight. |
| `max_retry_limit` (agents) | `0` | CrewAI's inner retry loop would multiply one outage into ~20 calls; the harness owns retries. |

### Stash lifecycle: conflicts are resolved, not parked
A run parks unrelated dirty work in a `swarm-<run-id>` stash and restores it
afterwards. Stashes never survive a run as loose entries:

- **Orphans.** At kickoff the flow archives every `swarm-*` stash left by an
  earlier run (a crashed/killed run, or an old budget stop). Each becomes a
  permanent ref `refs/swarm/archive/<timestamp>-<sha>` and is appended to
  `swarm/runs/orphan_stashes.json`, then dropped. The ref is readable with
  `git show <ref>:<path>` (GC-safe), so no landmine is left for a LIFO
  `stash pop` to apply to the wrong base.
- **Conflicted restore is solved, not just recorded.** The parked work is
  wanted, so one `Stash Conflict Resolver` crew (read + edit only, no shell,
  same model as the merge resolver) gets the unmerged files and re-applies the
  parked side on top of the current worktree, without duplicating a change that
  is already there. The harness accepts it only if no conflict marker remains,
  the crew edited only those files, and every gate (`gate_commands()`) exits 0;
  then the conflict stages are cleared, the parked work stays an unstaged change
  (like a successful `stash pop`), and the stash is archived with
  `reason: "resolved"`.
- **Fallback.** If the resolver is unavailable, leaves markers, touches another
  file, or the gated tree is red, the attempt is reverted (including
  out-of-conflict edits), the tree keeps the current worktree (`--ours`), and
  the stash is archived with `reason: "conflict"`. `run.json` records
  `stash_conflict` (paths), `stash_conflict_ref`,
  `stash_conflict_resolution` (`crew` / `ours` / `kept`) and
  `stash_conflict_note`. Cleanup/signal paths never call a crew.
- Only `swarm-*` entries are touched — a user's `WIP` stash is never archived or
  dropped. `SWARM_ARCHIVE_STASHES=0` disables archiving;
  `SWARM_CONFLICT_CREW=0` disables both resolver crews.

### Unattended operation (015)
- `make swarm-supervise` drives `./swarm/run.sh --resume`: retryable outcomes
  (`interrupted`, transient `crew_error`, `quota_exhausted`, `budget_exhausted`,
  commit/push/merge failures) restart with exponential backoff; a task that
  exhausts `SWARM_SUPERVISE_ATTEMPTS` (default 3) is parked in
  `swarm/runs/retry_later.json` and the queue skips it. `config_error` (HTML
  body, 404/401/403, bad base URL, bad key) stops immediately.
- Hygiene: out-of-scope writes are reverted (`out_of_scope_reverted`), unrelated
  dirty in-scope files are stashed before the run and restored after
  (`SWARM_STASH_UNRELATED=0` disables), and preflight self-heals a missing venv,
  `frontend/node_modules`, or Ollama image — and runs `npm install` when a task
  added a devDependency the coder cannot install itself (`SWARM_SELF_HEAL=0`).
- Transport: cloud calls use one SDK retry with `SWARM_LLM_TIMEOUT_SECONDS` (60);
  a transport failure gets one same-model retry, and a second identical failure
  moves only that role to its fallback chain (006/007 runs showed five SDK
  retries × 120s before the flow saw it).
- **Fallbacks are per role.** A coder timeout must not degrade QA: 007-T4 lost
  30 minutes because one global switch moved the reviewer to `qwen3.5:9b`, which
  looped over the report and never declared a verdict (`reviewer_no_verdict`).
  The reviewer has no fallback chain — a missing verdict is decided by the
  senior model instead. Every other role falls back to
  `SWARM_LOCAL_FALLBACK_MODEL` (default `ollama/swarm-coder:latest`), with
  `SWARM_<ROLE>_FALLBACK_MODEL` as a per-role override; only a provider-wide
  quota wall switches every role at once.
- Verification honesty: DB-backed tests that skip are recorded in
  `run.json.skipped_ac` + `verification_note` (set `DATABASE_URL` to run them).
- Retries resume at the failing step; a drifted checkpoint redoes only its last
  step. Identical failures are not retried on the same model.

Green is deliberately strict (012 AC-4/AC-6):
1. every gate exits `0` (including the run-delta scope gate);
2. the Reviewer's final word is `PASS` (`BLOCKED` → `needs_human`; a missing verdict gets one free-model repair),
   and the scenario verifier (019) did not end blocked — a `verifier_blocked` run is `needs_human` even when every gate exits `0`;
3. a non-empty in-scope run delta, or the same task's recovered interrupted delta, or an
   empty green commit when the tree is already clean/satisfied (never a blind commit of
   unrelated dirty work);
4. approval is present only when the run was started with `--require-approval`;
5. commit + push succeed. `commit_failed`/`push_failed`/`merge_failed` are not green.
6. the 043 Spec Acceptance pass runs after a green task (unless `SWARM_ACCEPT=0`).
   Its verdict and any queued fix tasks are recorded in `run.json.acceptance`; the task is still
   recorded green in the done ledger, but the acceptance result flags regressions for the operator.

Plan cache: planner output is saved to `swarm/runs/plans/<spec>-<task>.md` with a
`<!-- plan-source: sha256 -->` header over `spec.md`+`plan.md`+`tasks.md`. A changed spec
invalidates the cache automatically; `--replan` still forces re-planning. Zero-step,
malformed, or over-`MAX_STEPS` plans fail through the normal replan/`crew_error` path —
they are never silently truncated.
