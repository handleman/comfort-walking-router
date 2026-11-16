# 024 Earned Autonomy — Tasks

Control-plane spec (`HARNESS_SPECS`): the queue never runs these.

- [x] T1 (AC-1): add `swarm/risk.py` — the 0/1/2/3 path ladder, sensitive-brief override, and unknown/empty → 3.
  Evidence: `swarm/risk.py`, `swarm/tests/test_autonomy.py`.
- [x] T2 (AC-2): `risk.decision` — auto-merge only when autonomy is on, class ≤ max, gates green, reviewer pass and verifier not blocked; a named reason for every refusal.
  Evidence: `swarm/risk.py`, `swarm/tests/test_autonomy.py`.
- [x] T3 (AC-3): wire the decision into `save_run` — record `payload["autonomy"]` and skip the `awaiting_approval` hold only for `auto_merge`; the green commit path is unchanged.
  Evidence: `swarm/flow.py`, `swarm/tests/test_autonomy.py`.
- [x] T4 (AC-4): telemetry — `run.json.autonomy`, the human-log line and `make swarm-report` class counts + auto-merged total.
  Evidence: `swarm/humanlog.py`, `swarm/report.py`, `swarm/tests/test_autonomy.py`.
- [x] T5 (AC-5, AC-6): knobs and docs — `SWARM_AUTONOMY`, `SWARM_AUTONOMY_MAX_CLASS`, `.env.example`, `swarm/README.md`, `AGENTS.md`, `docs/roadmap.md`, `changelog.md`, and `024-earned-autonomy` in `HARNESS_SPECS`.
  Evidence: `.env.example`, `swarm/README.md`, `swarm/flow.py::HARNESS_SPECS`.
- [x] T6 (AC-7): record the measurement honestly — no live auto-merge is claimed until a green baseline exists; expansion/withdrawal on agreement/escape rates is the next decision.
  Evidence: `docs/roadmap.md`, `changelog.md`.

## Decisions (2026-11-14)

- **Earned, not blanket.** Only class 0/1 auto-merge, and only with autonomy
  explicitly enabled; class 2/3 stays human. The market's risk-class ladder, not
  "green means merge".
- **The verifier stays in the loop.** A class-1 test change still needs the 019
  verifier; a test that encodes the wrong behaviour is the 014-T7 class.
- **The decision is recorded before it is trusted.** Escape-rate measurement
  (post-merge reverts) is the input for expanding to class 2; it is not
  automated here.
- **Default off.** `SWARM_AUTONOMY=0`, so the phase is inert until an operator
  opts in; `--require-approval` still holds explicitly.

## Phase 024 evidence

The 020–023 work has no green live baseline yet, so auto-merge is shipped as a
tested, off-by-default policy with a per-run decision record. It cannot make a
red run green, and class 2/3 cannot auto-merge by construction.
