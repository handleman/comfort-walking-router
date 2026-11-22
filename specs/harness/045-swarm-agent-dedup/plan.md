# 045 Swarm Agent Dedup — Plan

## Shape

```
swarm/crew.py
  _senior_agent(task, kind)          # new internal builder
    ├─ build_senior_step_crew  → Agent(kind="senior_step", prompt=senior_step_prompt, max_iter=12)
    └─ build_senior_crew       → Agent(kind="senior",       prompt=senior_prompt,        max_iter=16)
  _conflict_resolver_agent(kind)     # new internal builder
    ├─ build_conflict_crew     → Agent(kind="merge", ...goal/backstory...)
    └─ build_stash_crew        → Agent(kind="stash", ...goal/backstory...)
```

## Steps

1. **Senior factory** — extract the common `Agent(...)` construction (role/goal/backstory via `agent_copy(task, kind)` + `stack_hint`, `senior_llm()`, `_tools`, skill injection) into one helper; `build_senior_step_crew` passes `senior_step` + `senior_step_prompt` + `max_iter=12`, `build_senior_crew` passes `senior` + `senior_prompt` + `max_iter=16`.
2. **Conflict resolver factory** — extract the common `Agent(...)` construction (`conflict_llm(allow_paid=True)`, read+edit tools, `max_iter=10`, SCOPE_RULE, skill injection) into one helper; `build_conflict_crew` passes a merge goal/backstory, `build_stash_crew` a stash goal/backstory.
3. **Tests** — run `make swarm-test`; fix only structural assertions that referenced the old literal `Agent(...)` blocks, keeping behaviour checks (role, max_iter, tools, skill injection) intact.

## Risks

- **Byte-equivalence.** The built agents must be indistinguishable from today's (role/goal/backstory/llm/tools/max_iter). A drift would change prompt prefixes and fail the 020/033 prefix-hashing assertions.
- **Test churn.** `test_autoloop.py`, `test_prompts.py`, `test_conflict.py`, `test_stashes.py` assert structure; the extraction must not change public names or signatures.
- **Conflict goal divergence.** Merge and stash backstories are genuinely different prose; the factory must parametrize them (not merge them), or the resolver becomes wrong for one case.