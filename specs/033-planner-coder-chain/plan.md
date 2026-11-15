# 033 Planner-Coder Chain — Plan

## Shape

```
plan.md (human approach)  ──►  planner  ──►  STEP n: <intent — files optional>
AC paragraphs              ──►  (decompose,  └─ never invent API names
                                not re-derive)
                                    │
                                    ▼
step_prompt: "logical step i/n: <intent>"   (coder reads real modules)
```

## The two prompt changes, exactly

`plan_prompt(task, spec_dir)` — include the task's plan lines next to the ACs:

```python
def plan_prompt(task, spec_dir):
    parts = [stable_prefix(task, spec_dir, "plan")]
    if plan_use_md() and plan_md:
        parts.append("PLAN (the approach, already decided — decompose, do not re-derive):")
        parts.extend(f"- {line}" for line in plan_lines(plan_md, task, brief_paths(task.brief))[:MAX_PLAN_LINES])
    return "\n\n".join(parts) + "\n\nResult: the STEP lines only."
```

`PLAN_RULES` — the fidelity rule:

```
Decompose the plan into logical steps, one acceptance criterion each. For each
step: what the step achieves, and at most which files it may touch. NEVER invent
a function, import path or field name — the coder reads the real module and
decides how. Output (exact, one per line): `STEP n: <intent> — <files, optional>`.
4–8 steps. No other text.
```

The old sentences ("name the module under test, the import path and the
functions it calls", "never plan a call to a function you have not seen") are
removed: they are the coder's rule, and they already live in `STEP_RULES`.

`step_prompt` — the step is an intent:

```
Execute logical step {idx}/{total} (no other work):\n{step_text[:2000]}\n
```

with `STEP_RULES` unchanged except the lead ("the step names intent; you choose
the implementation and read the real modules").

## The `plan_src` record

`_kickoff`/`run_crew` sets it:

| Value | When |
| --- | --- |
| `cached` | the STEP list came from `read_cached_plan` |
| `plan.md` | the planner prompt included the plan (`SWARM_PLAN_USE_MD=1` and a plan exists) |
| `derived` | the planner derived from ACs alone (off, no plan, or `--replan`) |

`plan_steps` = `len(steps)`. Both land in `run.json` next to `plan_reused` (which
stays, meaning "cache hit").

## Measurement (AC-5)

The replay suite and `make swarm-bench` are the acceptance. Run both sides:

1. `SWARM_PLAN_USE_MD=0` → today's numbers (the A side is already in
   `replay_baseline.json` for the frozen cases);
2. `SWARM_PLAN_USE_MD=1` → the new numbers.

Record `green`, `prompt tokens`, `task_prompt_chars` and `plan_steps` per side in
`changelog.md`. Success is **green rate not lower**; the prompt-char delta is
reported but is not the pass condition (020).

## Risks

- `plan.md` naming a file outside the task's scope: `plan_lines` already filters
  by the brief's paths; a step that overreaches is caught by the scope guard and
  the verifier as today.
- A plan with no STEP-decomposable content (e.g. a one-line plan): the planner
  falls back to the ACs; `plan_src` says `plan.md` only when lines were actually
  included.
