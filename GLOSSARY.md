# Comfort Walking Router

A walking-route app that scores routes by comfort (shade, quiet, lighting) from
real OSM data, with a live GPS walk mode. It is built by an autonomous swarm
(the harness), so the language splits into the **product** (the app) and the
**harness** (the swarm that builds it).

## Product language

**Route**:
A walking path between an origin and a destination, with geometry, distance, duration and a comfort score.
_Avoid_: path, track

**Origin**:
The starting point of a route. The walker's current position by default.
_Avoid_: start, source, from

**Destination**:
The end point of a route, chosen by search or map pick.
_Avoid_: end, target, to

**Comfort profile**:
The per-segment comfort along a route (≤200 m bands of a score, a dominant factor and a label), built from the OSM corridor.
_Avoid_: comfort segments, comfort breakdown

**Comfort score**:
The single 0–100 number for a route — the distance-weighted mean of its comfort profile.
_Avoid_: score, comfort rating

**Comfort bands**:
The three colour tiers of a comfort profile — `poor` (0–40), `mixed` (40–70), `good` (70–100) — drawn on the map and in the legend.
_Avoid_: terciles, colours

**Corridor**:
The strip of OSM data (highway ways + trees + green) around a route, queried from Overpass; the source of the comfort factors.
_Avent_: OSM box, buffer (corridor is the correct term)

**Shade factor / Quiet factor / Lit share**:
The three comfort factors from the corridor — tree/green cover per way, the share of quiet ways, and the share of lit ways.
_Avoid_: shade score, greenery, lighting

**Geocode**:
Turning an address or place name into coordinates. The reverse direction (coords → address) is **reverse geocode**.
_Avoid_: lookup, search

**Walk mode**:
The live walk that tracks the walker's GPS, shows the route and flags when they go off it.
_Avoid_: navigation, guidance

**Reroute**:
An alternative route offered when the walker leaves the current one; refused if it is materially worse for the remaining distance.
_Avoid_: recalculation, detour

**Arrival**:
The state reached when the walker nears the destination.
_Avoid_: reached, done

**Preference** (`hot` / `cloudy` / `quiet`):
The route bias — `hot` seeks shade, `cloudy` seeks sun, `quiet` seeks calm streets.
_Avoid_: mode, setting

**Saved routes**:
Routes persisted per bearer token in the database, with an optional **default preference**.
_Avoid_: favourites, bookmarks

## Harness language (the swarm)

**Spec**:
One unit of planned work: `spec.md` (what/why + acceptance criteria), `plan.md` (approach), `tasks.md` (the queue). Lives under `specs/<kind>/`.
_Avoid_: story, epic

**Acceptance criterion (AC)**:
A single verifiable requirement of a spec, referenced by tasks (`AC-1`, `AC-2`, …). One task maps to one AC.
_Avoid_: requirement, goal

**Task**:
A queue item — one `- [ ] T<n> (AC-…): brief` line in `tasks.md`.
_Avoid_: job, unit

**Queue**:
The ordered list of open (unchecked) tasks the swarm runs, in directory order.
_Avoid_: backlog, list

**Coder / Reviewer / QA / Verifier / Senior**:
The swarm's agent roles. The coder writes code; QA runs the gates; the reviewer declares PASS/BLOCKED; the verifier (019) checks the code matches the brief; the senior does deep fixes.
_Avoid_: worker, judge

**Shared agent builder** (`_senior_agent` / `_conflict_resolver_agent`):
The internal `swarm/crew.py` factories that build the senior (`step`/`fix`) and conflict-resolver (`merge`/`stash`) agents from the shared constructor — they differ only by prompt text and `max_iter`. No public builder names or signatures changed.
_Avoid_: duplicate constructor

**Gate**:
A verification command (`pytest`, `ruff`, `mypy`, `npm …`) run by QA; its exit code is the only source of "green".
_Avoid_: check, test (gates include non-test checks)

**Delta**:
The set of files a run changed (in scope), attributed to that run only.
_Avoid_: diff, changes

**Green**:
A task that passed every gate, got a PASS review, and was committed — recorded in the done ledger.
_Avoid_: done, complete

**Done ledger**:
The record of green tasks, stored as commit trailers (`Swarm-Task`, `Task-Hash`, `Spec-Hash`), not in `tasks.md`.
_Avoid_: history, log

**Risk class**:
The 0–3 telemetry label on a run (docs / tests / logic / control). Telemetry only — never a gate.
_Avoid_: priority, severity

**Dark factory**:
The autonomous loop: plan → code → verify → QA → commit, with no human in the middle.
_Avoid_: automation, pipeline

**Spec kind** (`product` / `harness`):
Whether a spec builds the app (queued) or improves the swarm itself (never queued). Lives in the spec's folder.
_Avoid_: type, category

**Pilot** (a **run**):
One execution of one task, from kickoff to commit or a typed stop. Writes `swarm/runs/<ts>/`.
_Avoid_: session, job

**Fix round** (a **correction**):
The QA→coder→QA loop that repairs a red gate or a verifier block, bounded by `MAX_FIX_ROUNDS`.
_Avoid_: retry, iteration

**Scenario verifier** (019):
A read-only agent that answers "does the code do what the brief says?" and blocks when it does not.
_Avoid_: reviewer (that's the gate verdict; this checks the scenario)

**Visual QA** (042):
A planned agent that screenshots the built UI (desktop + mobile) and judges the rendering, so a visually broken app is never green.
_Avoid_: visual regression (this is "is it obviously broken", not a pixel diff)

**Agent skill** (044):
A YAML‑frontmatter markdown file under `swarm/agents/skills/<role>.md` that the swarm auto‑discovers and appends to that agent's CrewAI `skills` list (additive to the backstory). Filename = role key; missing files fall back to a built‑in default template.
_Avoid_: prompt, backstory (a skill is a separate, operator‑editable capability layer)

**Spec acceptance pass** (043):
The final greenlight: `make swarm-accept` runs every built product spec through a real browser (desktop + mobile), deterministic probes + a free vision model, appends fix tasks for failing ACs and exits non-zero on FAIL. It is the end-of-batch check, not a per-task one. After every green feature task the supervisor's acceptance hook automatically runs the per-feature acceptance pass (swarm/acceptance.py), queuing fix tasks for failing ACs and recording the verdict in run.json — the feature still goes green but regressions are flagged for the operator.
_Avoid_: visual QA (042 is per-task; this is per-spec/per-feature after the queue drains or after each green task), e2e suite (that is gate evidence for one task)
