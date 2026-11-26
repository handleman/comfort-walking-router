# Model usage recommendations

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).
> The concrete ids and prices for the current profile live in
> [`setup.md`](setup.md); this page is about **which kind of model each role
> needs and why**.

## The one rule

**Mechanical work gets a fast, cheap model. Judgement gets a reasoning-capable
model.**

The harness optimises **cost per green task**, not cost per token. A cheap model
that writes code in 90 seconds is a bargain; a cheap model that blocks a correct
run, or passes a wrong one, costs a fix round, a wall-clock hour, and sometimes a
whole night. Those are not the same kind of purchase.

| Role | Class | What it actually does | Model requirement |
| --- | --- | --- | --- |
| Planner | mechanical | turns one brief into ordered steps | fast, tool-capable, instruction-following |
| Coder | mechanical (high volume) | writes/edits code for one step | fast, strong at code, tool-calling; the bulk-token role |
| Conflict / stash resolver | mechanical | reconciles two known diffs | fast, code-aware |
| Style/format fixes | mechanical | runs the linter and applies it | irrelevant (harness-driven) |
| **Reviewer / QA** | **judgement** | decides green vs blocked from gate evidence | **reasoning**; must not invent failures or excuse them |
| **Verifier** | **judgement** | reads the whole scenario, finds what gates miss | **reasoning**, long-context reading |
| **Senior (escalation)** | **judgement** | fixes what two rounds could not | strongest available; rare, so cost is amortised |
| Acceptance vision | advisory | looks at screenshots | vision-capable; never the sole gate |
| Conflict *judgement* (senior path) | judgement | same as senior | reasoning |

## Why review needs reasoning (the record)

These are measured failures, not a preference:

- **2026-11-15, planner/coder escalation:** six paid fix rounds were spent
  because the reviewer's prose said "the verdict should be BLOCKED" while its own
  recorded evidence was green. The parser believed the prose. → `block_is_grounded`
  now requires a checkable citation, but the *cause* was a model reasoning about
  its own answer instead of the evidence.
- **2026-11-25, T23:** the reviewer was the cheapest tier (`mimo-v2.6-flash`). It
  returned `blocked` with cause `test` while **every recorded gate was 0**, the
  verifier passed, and **no `pytest` run existed** in `shell_log.jsonl`. The fix
  round chased a non-existent failure, changed nothing, and the run parked
  `no_progress`. Switching the reviewer to `qwen3.8-flash` (the verifier's model)
  let the same work go green with no code change.
- **2026-11-26, T25:** the same reviewer, now on a reasoning model, **correctly**
  blocked a coder fix that would never pass ("clearing the query makes the bound
  input empty and the assertion unachievable"). A cheap reviewer had previously
  passed guesses like this.
- **Cost inversion:** the reviewer sees large inputs (diff + gates + brief) and
  emits a short verdict. A reasoning model there costs cents per task; a wrong
  block costs a fix round (T6: 201,982 tokens ≈ 10–20× the review call) plus the
  wall clock. **A reviewer that can be wrong is not cheap at any price.**

## Anti-patterns

- **Cheapest tier on review or verifier.** This is the failure above. Do not.
- **The same model for coder and reviewer.** Prefer a different family: two
  copies of one model share its blind spots. The current profile pairs a GLM
  coder with a Qwen reviewer/verifier for exactly this reason.
- **A reviewer with no gate visibility.** If the prompt does not include the
  recorded gate exits and the diff, no model can review; fix the prompt first.
- **Unpriced models.** A paid model with no price row makes `cost` `None` and the
  per-task dollar cap silently inert. `usage.py` must know the id.
- **Dead fallbacks.** A fallback the machine cannot serve is a bug: `preflight`
  validates every id *and every fallback* against its provider's catalogue
  (Ollama tags / OpenRouter list / Go `/models`).
- **Judging with a vision model.** Vision is advisory; deterministic probes and
  gates decide.

## Choosing a model, in order

1. Pick the **mechanical workhorse** by measured green rate on this repo (time
   and cost per task), not by benchmark marketing.
2. Pick a **reasoning model for reviewer and verifier** from a different family
   than the coder. If only one strong model exists, give it to the reviewer
   first — the verifier second.
3. Keep the **flagship for escalation** only; it is rare and short.
4. Ensure every role has a **servable fallback** on the same provider (a blip
   moves sideways) or an explicitly supported local one.
5. Run **one real task** where the coder is subtly wrong. A good reviewer blocks
   it with a checkable reason; a cheap one either passes it or blocks with a vibe.
6. `python -m swarm.model_config` prints the resolved profile;
   `python -m swarm.preflight` proves every id and fallback exists.

## Profiles

- **Cloud (current):** `opencode-go/*` for every role; reviewer/verifier on
  `qwen3.8-flash`, flagship senior. Table in [`setup.md`](setup.md).
- **Free cloud:** the same *shape* — the strongest free reasoning model for
  review, flash models for code. Free tiers are quota-capped; expect fallbacks.
- **Local (Ollama):** if the best local model is the same one used for coding,
  treat review as **advisory**: gates and the verifier carry the green decision,
  and the operator reads `run.json`. Local is supported, but do not pretend a
  9B coder is a reasoning reviewer.

## Knobs

```bash
SWARM_REVIEWER_MODEL=…          SWARM_REVIEWER_FALLBACK_MODEL=…
SWARM_VERIFIER_MODEL=…          SWARM_VERIFIER_FALLBACK_MODEL=…
SWARM_SENIOR_MODEL=…            SWARM_SENIOR_FALLBACK_MODEL=…
SWARM_ALLOW_PAID=1              # required for any paid id
```

Timeouts follow the profile (`Profile.crew_timeout()`): cloud 300 s, local 900 s.
`SWARM_CREW_TIMEOUT_SECONDS` / `SWARM_LOCAL_CREW_TIMEOUT_SECONDS` override each
side independently.
