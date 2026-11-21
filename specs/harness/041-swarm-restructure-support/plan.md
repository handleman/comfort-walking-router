# 041 Swarm Restructure Support — Plan

1. In `swarm/prompts.py`, append two hard rules to `STEP_RULES`:
   - a step that replaces/restructures code must remove the old code it
     supersedes (no duplicates);
   - every step must leave an in-scope file change.
2. Append to `PLAN_RULES`: a restructure/refactor splits into atomic steps that
   each land a concrete file change, naming the exact file and action.
3. Tests in `swarm/tests/test_prompts.py`: the rules contain the new
   instructions; `make swarm-test` green.

Risks: over-prescribing could make steps verbose; keep the additions short and
actionable, and keep the existing "read the real module / never invent API"
rules intact.
