# 004 Weather-Sun — Plan

## Approach
Backend slice on the 001 API: Open-Meteo client + auto-rule + cached fetch, additive contract fields per ADR-005, source chip in the Svelte UI. No provider/interface changes (scorer consumes the resolved preference). Reference spec AC-1..AC-5.

## Steps
1. Open-Meteo client in `app/` (current temp + cloud cover at midpoint), fixture-recorded unit tests, no live calls in CI (AC-1, AC-5).
2. Auto-rule module (thresholds ≥25°C / ≥70% cloud as constants) + SQLite weather cache (~30 min TTL) + graceful fallback to caller preference on fetch failure (AC-2, AC-4).
3. Additive contract: `applied_preference`, `preference_source`, `weather` in `contracts/route.json` + both sides' types (AC-1, per ADR-005).
4. Frontend: source chip (`Auto: …` vs `Manual`); toggle sends explicit preference = manual override (AC-3).
5. Verify: gates green, rule matrix test (hot-sunny/overcast/edge/failure), one live-weather smoke off-CI (AC-5).

## Risks / Open Questions
- Threshold defaults (25°C / 70%) are starting points — revisit with field evidence, no ADR needed for tuning.
- Open-Meteo availability — fallback path (AC-4) is the mitigation; cache keeps call volume trivial.
- Depends on 001 (scorer, cache, contract); lands after 001, independent of 007/008.
