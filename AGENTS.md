# AGENTS.md

Learning repo for spec-driven development + swarming agents (autonomous CrewAI
loops). The **swarm** (in `swarm/`) builds the **comfort route guide** (in
`app/`, `frontend/`) — a walking app that scores routes by comfort from real OSM
data, with a live GPS walk mode. Live: https://comfort-walking-router.onrender.com/

## State (essentials)

- Specs are the source of truth: `spec.md` → `plan.md` → `tasks.md` under
  `specs/product/` (the queue runs them) or `specs/harness/` (the swarm's own
  machinery — never queued). Templates in `.specify/templates/`.
- The swarm is autonomous: a green run merges by itself. Docs start at
  [`swarm/README.md`](swarm/README.md).
- Separate venvs: `app/`+`tests/` → `.venv`, `swarm/` → `swarm/.venv`,
  `frontend/` → npm. Don't mix them.

## Spec-driven workflow (the rules)

- **Route requests by target.** A request about the *built app* (`app/`,
  `frontend/`, product behaviour) goes to the **swarm**: write a
  `spec.md` + `plan.md` + `tasks.md` under `specs/product/…` and let the queue
  implement it. A request to *adjust the swarm itself* (`swarm/`, the harness,
  its constraints) is done **directly** by the coding agent. Only small, isolated
  direct edits (a one-line fix, a tiny tweak) bypass the spec+plan step;
  everything non-trivial gets a spec first.
- **Clarify by grilling first.** Before implementing, iteratively question the
  user (via the `question` tool) until you have a complete, unambiguous picture —
  probe the goal, scope, priorities, edge cases and anything interpretable two
  ways. Keep asking in rounds until clear; do not guess or implement on ambiguity.
- **Spec before code.** Define requirements, acceptance criteria and scope in
  `specs/` first. Keep specs small and verifiable; one task maps to one AC.
- **Visual-check UI in the built-in browser.** For UI work, verify visually in
  the built-in browser (`tools.browser.*`), not just via tests — a map can render
  no tiles and tests still pass. Check mobile sizes via canvas resize or a
  temporary iframe. Screenshot and look at it.
- **Final greenlight.** When a queue drains, `make swarm-accept` runs the spec
  acceptance pass (043): every built product spec is checked in a real browser
  (desktop + mobile) against its ACs, failures append `T<n>` fix tasks back to
  `tasks.md`, and anything broken exits non-zero — the harness never lands a
  visually broken spec as green.
- Update tasks/ACs in the same change as the implementation; record completed
  work and blockers explicitly. Prefer editing existing files; keep changes
  minimal. Do not invent commands or config — verify via manifests/scripts.

## Where to find more (load on demand)

- **Terms:** [GLOSSARY.md](GLOSSARY.md) — the product + harness vocabulary.
- **Skills:** use the `skill` tool (`domain-modeling`, `grilling`, `browser`, …)
  — load only the one that matches the task.
- **Harness lessons:** [swarm/docs/lessons.md](swarm/docs/lessons.md) — read
  before "fixing" the swarm.
- **Commands & boundaries:** [docs/reference.md](docs/reference.md).
- **Harness index:** [swarm/README.md](swarm/README.md) → `swarm/docs/*.md`.
- **Runbooks:** [docs/runbooks/](docs/runbooks/) — local-postgres, e2e-suite,
  verification, deploy, overnight-runs.
