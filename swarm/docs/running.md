# Running a pilot

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

## Dashboard (Textual)
`make swarm-dash` / `make swarm-up` open the parallel dashboard:

- **Queue** (left): tasks in order, newest outcome per task from run history
  (`✓` green, `✗` needs_human, `⏸` approval, `⛔` quota/budget, `▶` current).
- **The model list is live, per role.** It shows the model each role *actually
  calls*: live mode reads `llms.role_models()`, `--tail` reads `progress.json`
  (in flight) then `run.json usage.by_role` (finished). A role on a fallback is
  marked `fallback` and an Ollama model is marked `local`, so a paid → local
  switch is visible instead of hiding behind the static env list.
- **Models**: planner/coder/reviewer/senior, `local` for Ollama, `fallback ON`
  once a quota/429 switched the run; in tail mode it shows the models the run used.
- **Budget**: tokens / cost / wall-clock against `SWARM_MAX_*` with percentages.
- **Gates**: exit code per gate (`✓ 0` / `✗ 1`), scope included.
- **Recent runs**: last tasks for this spec with status, tokens, and cost.
- **Panes**: planner/coder/reviewer logs; status line has elapsed, tokens, cost,
  calls, attempts, plan=cached, senior, and approval state.
- **Human log** (`h`): scrollable "why did it stop?" view — status, notes,
  reviewer output, gate transcript (including `npm run check`), changed files,
  and the last events. `H` replays this run's event history into the panes.

Tail mode (`--tail swarm/runs/<id>`) follows `run.json` + `events.jsonl` of another
process and jumps to the newest run automatically. It opens **fresh**: events logged
before you attached are skipped, panes start empty, and each new task clears the
previous task's log.

Keys: `a`=approve (run dir + ledger), `r`=retry (live mode), `h`=human log
(why the run stopped: reviewer output, gate transcript, notes, events), `H`=history
for the current run, `p`/`n`=older/newer run, `t`=back to the newest run, `q`=quit.
History is opt-in, so long runs never flood a newly opened dashboard.

**The human log is take-away (018).** Every run writes the same report to
`<run_dir>/human_log.txt` — plain text, naming the stop reason, the reason code,
the failing gates, the reviewer's verdict and the changed files. A terminal screen
is not copy-pasteable, so the file is the artifact you attach to an issue:

```bash
make swarm-log              # newest run
make swarm-log RUN=<run dir>  # a specific run
cat swarm/runs/<id>/human_log.txt | pbcopy
```

In the dashboard, `c` on the human-log screen copies the report to the clipboard.
The screen and the file are the same renderer (`swarm/humanlog.py`), so they cannot
drift apart.

The dashboard is a read-only view; `run.json`/`events.jsonl` stay the contract
(ADR-011). For per-call spans when debugging, an optional OpenInference/OTel export
to a local Phoenix is the recommended add-on — the TUI is not a tracer.

## Resume from checkpoint
`make swarm-up` / `./swarm/run.sh` with no args resumes where the sequence last stopped:
latest run green → next task (or next spec); red, killed mid-run (`meta.json` only), or
held (`awaiting_approval`) → same task again; everything green → exits with
`all specs complete`. Explicit `SPEC TASK` args always override. Resolution lives in
`_resume_point` (`--resume` flag). To release an approval hold, use
`make swarm-approve SPEC=… TASK=…` (or `./swarm/run.sh SPEC TASK --approve`), then resume.

A *phase* checkpoint (`progress.json`, and the journal's completed prefix) only skips
micro-steps the next run can still vouch for, because run-delta attribution compares
against the baseline it took at start:

- **completion** — `SWARM_RESUME_MAX_AGE_SECONDS`, plan hash and step list must all match;
- **delta** — the recorded `delta_hashes` must be non-empty and still present in the
  worktree. An empty delta is evidence of nothing (`hash_paths([]) == {}` compares
  equal), so a checkpoint written after a revert is not a resume;
- **not all steps done** — `completed == len(steps)` is refused: nothing is left to
  run, so this run's delta would be empty by construction and the delta guard would
  stop it. The coding phase is redone so the run owns what it commits.

Both refusals print `restarting <T>: <reason>` and land in `run.json.recovery_note`
(`reason_code=no_delta` otherwise, which is how 007-T10 "resumed after step 5/5" into
an empty delta on 2026-11-15).

## Escalation (dev ×3 → senior → QA)
Each task gets up to `DEV_ATTEMPTS` (3) dev phases (micro-steps + review + 2 fix rounds
each, cached plan reused). A single micro-step failing `STEP_ATTEMPTS` (3) times is
rescued by the senior inline, then the phase continues. Still red after all dev phases →
up to `SENIOR_ATTEMPTS` (2) senior passes: `SWARM_SENIOR_MODEL`
(OpenRouter `:free`, must differ from planner; Zen free tier is locked to OpenCode
clients) fixes everything in one go via `build_senior_crew`, then QA re-verifies and
gates re-run. Still red → `needs_human`. Attempts + `senior_used` recorded in `run.json`.

Quota: a daily `free-models-per-day` / 429 error is provider-wide, so it switches every
role to its fallback (`SWARM_<ROLE>_FALLBACK_MODEL`; coder → `ollama/swarm-coder`,
planner/coder/reviewer → `SWARM_LOCAL_FALLBACK_MODEL` (default `ollama/swarm-coder:latest`), senior → `zen/glm-5.3-flash` when paid is allowed;
the reviewer keeps `swarm-qa` by design) and retries. If the fallback is also out,
the pilot stops with `quota_exhausted`, a `quota_note` in `run.json`, and a
`QUOTA EXHAUSTED` line in `up.log`. Transient 429/timeout/5xx errors get exponential
backoff (1s→8s, 3 attempts) before giving up.

## Event listener & dashboard (012 T15)
Each flow unregisters its CrewAI event handlers on `save_run` (`SwarmListener.teardown`),
so long autonomous loops do not leak handlers or keep writing to old run dirs.
Tail mode reads `events.jsonl` from a byte offset with a partial-line buffer instead
of re-reading the whole file every tick.
