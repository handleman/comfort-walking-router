# 037 Swarm npm install — Spec

Harness spec (control plane; the queue never runs it).

## Problem

The coder's `Guarded Shell` blocks `npm install` on purpose (see
`swarm/tools_guarded.py::_valid_npm`: "`install` stays blocked"), so adding a
library is a two-hop human step — the coder writes `package.json`, then the
operator runs `make swarm-preflight` (whose `self_heal` installs new deps). That
breaks full autonomy, and it is exactly what the 036 UI-overhaul foundation
needs (Svelte 4→5, Tailwind, shadcn-svelte): the swarm must be able to install
its own dependencies.

## Goal

The coder can install frontend dependencies itself — `npm --prefix frontend
install [pkg…]`, `npm ci`, `npm add` — within the existing argv-only,
prefix-locked shell. The gate scripts stay QA-only, arbitrary `npx`/`exec` stays
blocked, and there is an off switch.

## Scope

- `_valid_npm` accepts `install`/`ci`/`add`/`i` under `--prefix frontend`,
  rejecting `--prefix` (redirect elsewhere), `--global`/`-g`, and anything
  `_no_meta` already blocks.
- `SWARM_NPM_INSTALL=0` restores the block (off switch, default on).

## Non-goals

- `npx` (arbitrary package execution) and `npm exec` stay blocked.
- Changing which scripts are gates (`check`/`lint`/`test`/`test:e2e` stay QA-only).

## Acceptance criteria

- **AC-1 — install allowed.** `npm --prefix frontend install tailwindcss` and
  `npm --prefix frontend ci` pass `_valid_npm` for a coder (not a gate).
- **AC-2 — still guarded.** `npm --prefix frontend exec …`, `npx …`,
  `npm --prefix frontend install --global …`, and a second `--prefix` are
  rejected; the gate scripts remain QA-only.
- **AC-3 — off switch.** With `SWARM_NPM_INSTALL=0`, `install` is blocked again.
- **AC-4 — documented.** `_valid_npm` and the ShellTool description note the
  supply-chain tradeoff (package install scripts run under the coder's session),
  and the off switch is recorded in the changelog.

## Security note (recorded, not argued away)

`npm install` runs a package's install/postinstall scripts. The coder already
writes code that executes in the gates, so this widens the trust boundary from
"the operator installs deps" to "the coder installs deps" — accepted for the
dark factory, reversible with `SWARM_NPM_INSTALL=0`.
