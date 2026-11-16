# 004 Weather-Sun — Spec

## What / Why
Replace the 001 manual hot/cloudy default with a weather-aware auto preference from Open-Meteo (keyless, backend-fetched + cached). Manual toggle always wins on override. Keeps sun/shade scoring honest without user effort.

## Scope
- In scope:
  - Backend fetches Open-Meteo current (temperature + cloud cover) at route midpoint; SQLite-cached, ~30 min TTL.
  - Auto rule (defaults, adjustable): temp ≥25°C and cloud <70% → shade preference; cloud ≥70% → sun preference; else keep caller's preference.
  - Manual toggle overrides auto; UI shows source chip (`Auto: sunny 27°C` vs `Manual`).
  - Additive contract change per ADR-005: response gains `applied_preference`, `preference_source` (`auto`|`manual`), and `weather` snapshot.
- Non-goals:
  - No forecast-ahead or hourly planning; current conditions only.
  - No new secrets (Open-Meteo keyless); no frontend weather calls (backend-only per ADR-003).

## Acceptance Criteria
- [ ] AC-1: Weather available → response carries `applied_preference` + `preference_source=auto` + `weather` snapshot.
- [ ] AC-2: Hot-sunny (≥25°C, cloud <70%) auto-prefers shade; overcast (cloud ≥70%) auto-prefers sun.
- [ ] AC-3: Manual toggle overrides auto; chip shows `Manual` with the chosen preference.
- [ ] AC-4: Cached weather reused within TTL; Open-Meteo failure degrades to caller preference (no 500).
- [ ] AC-5: `pytest` + `ruff check .` + `mypy .` + `npm run check` clean; auto-rule unit-tested with fixtures.
