# The task queue

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

## How the swarm builds its todo list

The queue comes from `specs/*/tasks.md`, sorted by directory name (`001-…`, `004-…`, …):

- `swarm/spec_loader.py` parses **only unchecked tasks** with this shape:
  `- [ ] T1 (AC-1, AC-2): brief text`
  (regex: `^- \[ \] (T\d+)\s*(\([^)]*\))?\s*:\s*(.+)$`). `- [x]` tasks are invisible to the
  parser, and ids must be `T1`, `T2`, … — `T1a` is not recognized.
- Task order in the file is the execution order (`T1` → `T2` → …). After the last task, the
  loop moves to the next spec directory with tasks.
- Skipped automatically: `009-swarm-harness`, `012-dark-factory-harness`, `013-dark-factory-phase-2`, directories without
  `tasks.md`, and specs whose tasks are all `[x]`/have no parseable tasks.
- The planner reads `specs/<dir>/{spec,plan,tasks}.md` plus the constitution. The `brief` it
  receives is the text after the colon on the task line; indented notes below the line are fine
  but do not replace the brief.
- Progress between invocations comes from `swarm/runs/` history (`_resume_point`): latest green
  → next task/spec, red or killed → retry the same task. A checkpoint task that is already `[x]`
  (or was renamed) advances to the next open task; if the rest of the queue is done, resume wraps
  to the earliest open spec so newly added earlier-spec tasks are not stranded.
- `--spec` accepts a unique prefix (`001` → `001-example-app`). If two directories share a prefix,
  pass the full directory name.

## Adding a spec to the swarm todo list

1. Create `specs/NNN-name/` (`NNN` controls queue position) with:
   - `spec.md` — what/why, scope, acceptance criteria using stable ids (`AC-1`, `AC-2`, …).
   - `plan.md` — approach, ordered steps, risks; name the files you expect to change.
   - `tasks.md` — the queue (see format below).
2. Write one unchecked task per line, in order, e.g.:

   ```markdown
   # 012 My Feature — Tasks

   - [ ] T1 (AC-1): Add `POST /thing` in `app/main.py` plus a test in `tests/test_thing.py`.
   - [ ] T2 (AC-2): Render the result in `frontend/src/App.svelte` and keep `npm run check` green.
   - [ ] T3 (AC-3): Show the comfort score in `frontend/src/App.svelte`.
   ```

   Keep `T<n>` and the `(AC-…)` refs on the same line as the brief. The brief must be
   self-contained: one behavior change, exact paths, and what "done" means.
3. Make each task coder-sized: one file/behavior, ~4–8 planner micro-steps, verifiable by the
   project gates in `SWARM_GATE_COMMANDS` (this repo: `pytest -q`, `ruff check .`,
   `mypy app tests`, `npm --prefix frontend run check`, `npm --prefix frontend run lint`, `npm --prefix frontend test -- --run`).
   Split larger work into more tasks.
4. Respect the coder scope. Default: `app/`, `frontend/`, `tests/`, `contracts/`,
   `requirements*.txt`, `pyproject.toml`, `.gitignore`. Anything else needs an explicit override,
   e.g. adding a `scripts/` prefix:

   ```bash
   SWARM_SCOPE=app/,frontend/,tests/,scripts/ make swarm-up
   ```

   `swarm/`, `specs/`, `docs/`, and `.env*` are off-limits to the coder by design. The override
   **replaces** the defaults, so list every prefix the task needs (e.g. `app/,frontend/,tests/`,
   plus `pyproject.toml` if the task changes it).
5. Start it explicitly the first time (or when the new spec sorts before the current checkpoint):

   ```bash
   make swarm-run SPEC=012 TASK=T1      # foreground, then continues through the queue
   ./swarm/run.sh 012 T1 --single       # only this task
   ./swarm/run.sh 012 T1 --no-commit    # do not autocommit/push
   ```

   With no arguments, `make swarm-up` / `./swarm/run.sh` resumes from run history.
6. The swarm **does not edit spec files**. After a green run is reviewed, change `- [ ]` to
   `- [x]` yourself — that removes it from the queue. Do not check a task before it is green:
   the parser will skip it and an explicit start on that id fails with
   `No task … (have: …)`.
7. If you edit `spec.md`/`plan.md`/`tasks.md` after a plan was cached in
   `swarm/runs/plans/<spec>-<task>.md`, force a fresh plan with `--replan`:

   ```bash
   ./swarm/run.sh 012 T1 --replan
   ```

   Without it the cached `STEP` list is reused even if the spec changed.

Each run still has to pass the flow's own gates and scope check (`pytest`, `ruff`, `mypy`,
`npm --prefix frontend run check` / `run lint` when the frontend is installed, plus an optional frontend test).
`npm test` when the frontend test script exists); green runs autocommit in-scope changes and push
(`swarm: <spec>-<task> green …`) before continuing.

Each run writes:
- `swarm/runs/<ts>-<pid>-<rand>/run.json` — spec, task, status (`green`/`needs_human`/`crew_error`/…), gate exit codes, usage (tokens/cost/timestamps).
- `swarm/runs/<ts>/events.jsonl` — streamed agent events; `usage.json` when available.
Tail mode follows the loop: when a newer run becomes `latest`, the dashboard jumps to it
(task list + plan note re-sync). Plan validation: planner output without `STEP` lines fails
the run instead of executing garbage. A run with no new in-scope changes recovers the same
task's interrupted paths whenever they are still dirty (unrelated dirty files are left
alone); otherwise it records an empty green commit (`Swarm-Vacancy: 1`) and advances. Only unrelated dirty in-scope work still
stops as `needs_human`.
