# 041 Swarm Restructure Support — Tasks

- [x] T1 (AC-1, AC-2): Add the "remove the old code you replace (no duplicates)" and "every step must leave an in-scope file change" hard rules to `STEP_RULES` in `swarm/prompts.py`.
- [x] T2 (AC-3): Add the "restructure/refactor → atomic steps that each land a file change, naming the exact file and action" rule to `PLAN_RULES` in `swarm/prompts.py`.
- [x] T3 (AC-4): Tests in `swarm/tests/test_prompts.py` asserting the new rules; `make swarm-test` green.
