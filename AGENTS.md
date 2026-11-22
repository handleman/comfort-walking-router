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
  visually broken spec as green. After every green feature task the supervisor's
  acceptance hook automatically runs the per-feature acceptance pass
  (`swarm/acceptance.py`), queuing fix tasks for failing ACs and recording the
  verdict in run.json — the feature still goes green but regressions are flagged
  for the operator.
- Update tasks/ACs in the same change as the implementation; record completed
  work and blockers explicitly. Prefer editing existing files; keep changes
  minimal. Do not invent commands or config — verify via manifests/scripts.
- **Grill before spec, spec before code (no exceptions).** On any **non‑trivial**
  request — a new harness capability (e.g. the Swarm Agent Skills folder/injection
  from 044), a product behaviour, or a refactor — ask questions until the picture
  is unambiguous: goal, scope, priorities, edge cases, interpretive choices. Write
  the spec (`spec.md` → `plan.md` → `tasks.md`) before implementing, even when the
  harness itself is being changed directly (the swarm is not queued). Small,
  isolated one‑line fixes still bypass this flow.
- **Model profiles are configuration, not capability** (the dark factory is
  provider-agnostic). The same harness runs on **paid cloud, free cloud, local
  Ollama, or a mix**; only `.env` changes. Three profiles are documented and
  supported: `opencode-go` (paid subscription, current default), free OpenRouter
  tiers, and all-local Ollama (`make swarm-local`). Rules:
  - **One source of truth:** `swarm/llms.py` picks every model; a role var
    (`SWARM_<ROLE>_MODEL`) plus `SWARM_<ROLE>_FALLBACK_MODEL` is the whole API.
    Routing is by prefix — `ollama/*` local, `zen/*` Zen, `opencode-go/*` Go,
    everything else OpenRouter.
  - **Never assume a provider.** A fallback must be a model the machine can
    actually serve: `preflight` checks Ollama tags, the OpenRouter list and the
    Go `/models` catalogue before the first call. A dead fallback id is a bug
    (2026‑11‑22: `opencode-go/qwen3.8-flash` sat in `SWARM_LOCAL_FALLBACK_MODEL`
    as if it were an OpenRouter id).
  - **Timeouts follow the profile, one knob each:** `SWARM_CREW_TIMEOUT_SECONDS`
    (cloud, default 300 s) and `SWARM_LOCAL_CREW_TIMEOUT_SECONDS` (local,
    default 900 s) via `llms.crew_timeout_seconds()`. They are independent, so a
    local step is never truncated by a cloud-sized cap and a hung cloud call
    cannot eat the task (046 AC‑3).
  - **Cost is honest in every profile:** local and `:free` models are $0 in
    `swarm/usage.py`; a paid model with no price makes cost `None` and names
    itself (`unpriced_models`) instead of faking a number.
  - **Paid is one switch:** `SWARM_ALLOW_PAID=1` in `.env` — the operator's
    decision, in the same place the model ids live. `local` and `:free`/`-free`
    ids never need it, so switching to a local profile requires no code change.
    (The old rule also demanded `allow_paid=True` at each call site; that
    duplicated one decision across every builder and died at run time when a
    role was constructed with the wrong flag.)

- **Swarm Agent Skills** (044): operators add agent behaviour via YAML‑frontmatter
  skill files under `swarm/agents/skills/<role>.md`; the swarm auto‑discovers them
  and appends to `agent.skills` (additive). Missing files fall back to built‑in
  default templates. Off switches: `SWARM_SKILLS=0`, configurable dir
  `SWARM_SKILLS_DIR`.

  **Shared internal builders (045):** `swarm/crew.py` exposes `_senior_agent(task, kind)` and
  `_conflict_resolver_agent(kind)`. Both are byte-equivalent to the old inline
  `Agent(...)` blocks for `build_senior_step_crew`/`build_senior_crew` and
  `build_conflict_crew`/`build_stash_crew`; they only differ by prompt text and
  `max_iter`. No public builder names or signatures changed.

  **Clarifying questions (044):**
  - Which core agent roles should ship with a skill file? (coder, qa, verifier,
    planner, senior, senior_step, test_author, conflict_resolver, stash_resolver?)
  - Should each skill file be additive (append to existing backstory) or replace
    the backstory wholesale?
  - What should the built‑in default template say for roles with no operator file?
  - Should injection be disabled per role, or only globally?
  - Should the skills folder be versioned/published (038‑style pip package), or stay
    repo‑local for now?

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
