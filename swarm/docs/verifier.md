# Scenario verification (019)

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

### Scenario verification (019)

The gates test **the code that exists**, so a missing piece passes them: 014-T2
shipped `app/cache.py` and a contract but never mounted `GET /geocode` in
`app/main.py`, and every gate exited 0. Six 014 tasks were committed green that
way, three of them not doing what their brief said and two never landing at all.

A read-only **Scenario Verifier** now runs between the 017 self-check and QA,
and again after a QA fix round that changed the delta:

- **What it sees:** the task brief, the `AC-n:` paragraphs it references, the
  `plan.md` lines that mention its files, the **full content** of every file in
  the run delta (up to `SWARM_VERIFY_READ_CHARS`, default 60000 — not the
  coder's 3000-char read) and a best-effort static import/imported-by view that
  makes a duplicate implementation visible (`frontend/src/lib/navigation/walkMode.ts`
  next to the real `frontend/src/lib/walkMode.ts`). Files that do not fit are
  listed by name and size, never silently dropped.
- **What it answers:** `VERDICT: PASS|BLOCKED`, with one `FINDING: <file/line> —
  <problem>` line per problem. It checks that every element the brief names
  exists, that the pieces connect (endpoint mounted, real module imported, the
  contract and the code agree) and that the referenced ACs are addressed.
- **What happens on BLOCKED:** it emits correction steps in the planner's own
  `STEP n: <file> — <action>` format; the flow runs them with the existing step
  coder crews (role `coder:verify<n>`) and verifies again, bounded by
  `MAX_VERIFY_ROUNDS` (2). A verifier that does not converge ends the run as
  `needs_human` / `reason_code=verifier_blocked`, never an unbounded loop. A
  block with no `FINDING` is treated as a pass; a block with findings but no
  plan of steps stops the round instead of looping.
- **What it cannot do:** write a file (no `Repo Edit`/`Repo Create`), run a
  gate (`allow_gates=False`), commit, or decide green. It runs under its own
  agent role (`verifier`), so its shell records are never QA evidence; QA's
  gates remain the only evidence of green. Its output is text, exactly like the
  planner's `STEP n:` lines and QA's `VERDICT:` line.
- **Where it is recorded:** `run.json.verifier` holds the verdict, the rounds,
  the findings, the correction plan, the files it read (and the ones it could
  not), the model and a per-round history; `human_log.txt` and the dashboard
  show its verdict next to QA's (`h`). `SWARM_VERIFY=0` disables the phase.

Like the self-check, the verifier is not a gate: it is cheap relative to a wrong
green (one bounded crew per round) and it never certifies work.

Two verdict rules matter when reading `run.json.verifier`:

- **No verdict is not a pass.** If the model spends its turn on tool calls and
  never states `VERDICT:`, the flow re-asks **once** (`verifier:<n>b`); if that
  also fails the run stops as `needs_human` (`verifier_blocked`). Before this,
  `unknown` fell through as a pass and 014-T10 committed green with three
  missing deliverables.
- **Re-litigation is judged on the finding, not the file.** A block after a
  landed correction is `unstable` (a warning, QA decides) only when it repeats
  the **same** finding (file + normalised sentence, line numbers ignored). A new
  defect in the same file stops the run — the earlier file-overlap heuristic
  waived a real missing crosshair rule.
