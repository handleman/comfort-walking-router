# Self-healing e2e: what the market does, and what we should build

Date: 2026-11-15. Input for `specs/027-e2e-self-heal/`. Sources are linked at the
bottom; every claim below is from a published system or measurement, not memory.

## 1. The frame: dark factory

The market's vocabulary is useful because it separates three things we have been
conflating:

| Level | Human role | Who decides |
| --- | --- | --- |
| agentic coding | sets each task, redirects | the human |
| spec-driven | writes spec + acceptance | the human in the middle |
| **dark factory** | defines *what* and judges *output* | **the pipeline** |

BlueGrid's definition is the one we should borrow: "specifications go in,
software comes out; the pipeline determines how to satisfy the specification,
what approaches to take, **how to handle failures**, and how to iterate toward a
passing result." A run that stops on a failing end-to-end test and waits for a
human is not a dark factory — it is spec-driven with extra steps. That is exactly
the gap `027` closes.

Factory.ai frames the same loop as *signals → planned change → build/test/review →
ship → monitoring → new signals*, and notes the precondition: "Missions need a
repository that can be tested automatically. An agent cannot prove a migration
works if the test environment is missing." We have that precondition now
(`make e2e`, 026 AC-8) and we do not use it for anything but evidence.

StrongDM's Attractor (the "first dark factory", Feb 2026) is the closest
architecture to ours: NLSpecs in, a DOT-graph pipeline, and a **Digital Twin
Universe that runs thousands of tests and iterates until convergence**. Two
lessons: convergence is the product, and the tests are the oracle that makes a
human-free loop defensible.

BrainGu names the failure mode of naive dark factories the **Verification Gap**:
"the model that writes the implementation must not be the model that writes the
verification. If the model misunderstands an API, it will write code that calls
the API incorrectly and tests that validate that incorrect usage. Everything
passes." Pensar's Level 5 answer is the same idea enforced architecturally:
adversarial verification by agents isolated from the authors.

## 2. The narrow question: who repairs a failing e2e test?

Published systems converge on a small set of rules, and they are stricter than
"let the agent regenerate the test":

1. **Classify before touching anything.** Donobu's heal agent fixes *test-side*
   breakage only (renamed button, restructured form, stale selector); it
   "does not change your tests to hide genuine application bugs" and changes
   nothing for environment problems. RoostGPT publishes the decision table:
   selector drift → regenerate; flaky → no change; test-side code bug → patch;
   workflow changed → notify a human.
2. **The fixer never grades its own work.** Donobu: "The agent never grades its
   own work: only a test that passes the re-run counts as fixed." Exactly our
   015 rule (QA's recorded evidence) extended to the new phase.
3. **Weakening must be visible and refused.** Donobu's PR "flags any change that
   weakens a test, such as a skipped test or a removed check". Uber's AutoCover
   Fixer enforces "do no harm": patches that degrade passing tests are reverted,
   and chronic non-improvers are frozen. This is the single most important guard
   for an autonomous loop, because a model that can rewrite the oracle can make
   anything green.
4. **The healer preserves the quality of what it repairs.** The Playwright
   agent trio (planner / generator / **healer**) was measured on a real app: the
   healer repaired six deliberately stale locators in 1m55s, correctly — and
   "healed code preserves the quality level of the code that broke": it restored
   `#id` selectors rather than the semantic locators a reviewer would ask for,
   and even copied a button name with a leading space. Verdict of that
   measurement: "treat the healer as a colleague who proposes fixes in a PR, not
   as a silent auto-repair step."
5. **Bounded rounds, deterministic acceptance.** Donobu: ≤3 rounds; a test counts
   as healed only when its last re-run passed. Testuary repairs suites with
   "deterministic repair and acceptance checks" *before* any agentic phase.
   AutoCover runs generate → validate → fix with reversible edits.

## 3. What we adopt, and what we refuse

Adopt:

- the classification gate (test-side vs product vs environment), because it is
  what keeps an autonomous loop from "fixing" a real bug by editing the test;
- an inner roster written in our own SDD format (`spec → plan → tasks`) per
  failure, so a repair is a *planned change* with an AC and a file scope, not a
  free-form edit;
- the anti-weakening guard as **deterministic code**, not a prompt rule: no test
  removed, no `skip`/`fixme`/`only`, assertion count non-decreasing, and the
  originally failing titles must be present *and passing* in the final recorded
  run;
- the separation of roles: triage cannot write implementation, the spec-writer
  cannot decide green, QA still owns the gates, the verifier still reads the
  scenario.

Refuse:

- Testuary's "remove the failing tests and re-run" as an acceptance strategy: for
  us that is oracle weakening, suitable for generated candidates, not for a
  scenario that encodes an AC;
- silent auto-heal (Rainforest/RoostGPT style updates): our repairs are a normal
  run delta, visible in the commit, the roster and `run.json`, and revertible;
- regenerating the whole suite: too expensive (43m for 7 tests in the measured
  Playwright experiment) and it discards reviewed intent.

## 4. Why this is self-healing rather than reward hacking

Three independent things must agree before an inner repair counts:

1. **a recorded suite run** at the final delta hash passes (`shell_log.jsonl`,
   026 AC-8) — the harness, not the model;
2. **the original failing titles are still there and pass** — compared against
   the pre-repair `playwright test --list`, so deleting or skipping is visible;
3. **the scenario verifier** (019) still sees the AC implemented in the code, not
   just the test.

A repair that only satisfies (1) fails (2)/(3) and ends the run as
`e2e_weakened` with the evidence attached. That is the "verification gap" closed
by architecture, which is what BrainGu and Pensar both argue for.

## 5. Risks we are accepting, and the measurement that watches them

- **Oracle drift**: a drifted spec is repaired to what the app does today, so a
  regression can be blessed. Mitigation: the verifier reads the brief/ACs, and the
  escape rate (`make swarm-report`) counts reverts of auto-merged repairs.
- **Cost**: triage + roster + repair is 2–4 extra crews on a red e2e. Budget:
  `SWARM_MAX_INNER_TASKS=3`, `SWARM_MAX_INNER_ROUNDS=2`, and the existing
  per-task wall/cost caps; `run.json.e2e_self_heal` records what it spent.
- **Flakiness mistaken for drift**: a retry-passing test must classify as `flaky`
  (no edit), which is why classification runs on the *recorded* run and the
  reporter's retry field, not on a single failure line.

## Sources

- BlueGrid, *AI Dark Factory Pattern — Part 1* (2026-04): levels, pipeline decides.
- Factory, *Factory 2.0: From coding agents to software factories* (2026-06): the
  signal loop; "needs a repository that can be tested automatically".
- BrainGu, *Enter the Dark Software Factory* (2026-05): Verification Gap, build
  integrity, execution isolation.
- Pensar, *Level 5 Coding Agents* (2026-03): scenario testing against a replica;
  adversarial verification isolated from authors.
- Sandgarden, *The Evolution of AI Factories*: StrongDM Attractor, DTU convergence.
- Donobu docs + changelog, *Self-Healing Tests / --auto-heal* (2026-10): test-side
  only, no self-grading, weakening flags, ≤3 rounds.
- Playwright official test agents + Gary Parker's measured write-up (2026-11):
  planner/generator/healer, 43m generation, healer preserves the quality of what
  broke.
- RoostGPT / RainforestQA self-healing docs: diagnosis table (drift/flaky/code bug/
  workflow change).
- Uber AutoCover, ICSE-SEIP 2026: Preparer→Generator→Executor→Validator→Fixer,
  "do no harm" rollback, freeze chronic non-improvers.
- Testuary (arXiv 2610.14808): parallel suites, deterministic repair/acceptance,
  set-cover reduction.
