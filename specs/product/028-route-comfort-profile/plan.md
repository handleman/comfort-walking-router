# 028 Route Comfort Profile — Plan

## Shape

```
POST /route
  ├─ corridor fetch (001, one Overpass call) → factors for the whole route
  ├─ comfort.profile(geometry, factors)      → segments with score + factor
  ├─ comfort_score = distance-weighted mean  → the two can never disagree
  └─ response.comfort_profile + explanation line

frontend
  └─ drawRoute(): per-segment polyline in three bands + legend + per-segment label
```

## Modules and exact shapes

`app/comfort.py`

```python
PROFILE_SEGMENT_M = 200.0
BANDS = ((0, 40, "poor"), (40, 70, "mixed"), (70, 100, "good"))  # label only

@dataclass(frozen=True)
class ProfileSegment:
    from_m: float
    to_m: float
    score: float          # 0..100
    factor: str           # shade|sun|quiet|traffic|lit|unknown
    label: str            # ≤ 40 chars, human ("shaded footpath", "busy road")

def profile(geometry: dict, factors: dict | None, *, segment_m: float = PROFILE_SEGMENT_M) -> list[ProfileSegment] | None
def weighted_score(segments: list[ProfileSegment]) -> float
```

Rules (pure, no clock, no network):

- walk the LineString accumulating haversine distance; cut a segment every
  `segment_m` (the last one takes the remainder, so `to_m` ends exactly at the
  route distance);
- each segment scores from the corridor factors: base 50, **+20 · shade_factor**
  for the shaded share, **+15 · quiet_factor**, **−15 · (1 − quiet_factor)** for
  busy ways, **+10** when `lit` and the request asked for `prefer_lit`; clamp 0–100;
- `factor` is the term that moved the score most (ties: `shade` before `quiet`
  before `lit`); with no data `factor="unknown"`, `score=50`, label "no OSM data";
- `label` is a short phrase chosen from the dominant factor and its strength
  ("shaded footpath", "open and sunny", "quiet side street", "busy road").

`app/main.py::_build_response`

- pass the geometry + `comfort_data` to `comfort.profile(...)`;
- when the profile exists: `comfort_score = comfort.weighted_score(profile)` (AC-1
  replaces the old single-number path so the two agree by construction), and add
  one explanation line: `Profile: {k} of {n} segments shaded, {m} sunny ({start}–{end} m).`
- when it does not: `comfort_profile = None` and the existing data-gap line plus
  `Profile: unavailable without OSM corridor data.`

`contracts/route.json` — add under the response `properties`:

```json
"comfort_profile": {
  "type": ["array", "null"],
  "items": {
    "type": "object",
    "required": ["from_m", "to_m", "score", "factor", "label"],
    "properties": {
      "from_m": {"type": "number", "minimum": 0},
      "to_m": {"type": "number", "minimum": 0},
      "score": {"type": "number", "minimum": 0, "maximum": 100},
      "factor": {"enum": ["shade", "sun", "quiet", "traffic", "lit", "unknown"]},
      "label": {"type": "string", "maxLength": 40}
    }
  }
}
```

Keep it optional (an old client must not break); `required` for the response
array itself only.

`frontend/src/App.svelte`

- `drawRoute()` builds one `L.polyline` per band run (consecutive segments in the
  same band merge) instead of `L.geoJSON`; band colours `#2f855a` (good),
  `#d69e2e` (mixed), `#c53030` (poor);
- a legend `<ul class="comfort-legend">` with the three bands and their ranges;
- each merged run gets `bindTooltip` (`"shaded footpath · 0–200 m · 78/100"`) and
  the segments are also listed in `.comfort-segments` (visible text, so colour is
  not the only signal);
- when `route.comfort_profile` is null: no bands, one line "Comfort profile
  unavailable (no OSM data)."

`app/cache.py` — `CACHE_VERSION` → `v5`.

## Tests

- `tests/test_comfort_profile.py`: distance cut points, weights, clamps, factor
  choice, `weighted_score`, determinism (same input twice → identical output),
  no-data → `None`.
- `tests/test_route_comfort.py`: response has the profile for a fixture corridor;
  `comfort_score == weighted_score(profile)` ±0.5; gap case → `null` + explanation;
  cache hit does not refetch.
- `tests/test_route_contract.py`: the field exists, is an array, entries validate
  against `contracts/route.json`.
- `frontend/e2e/search.spec.ts`: legend visible, ≥3 polylines, one tooltip text.

## Risks

- **Colour-only information** — mitigated by the legend, visible segment list and
  tooltip (AC-4).
- **Profile/score disagreement** — avoided by deriving the score from the profile
  (AC-1), not by computing both.
- **Cost per route** — zero extra network; the profile is arithmetic over data
  already in memory.
- **Cache staleness** — `CACHE_VERSION` bump is mandatory and part of T2's
  acceptance.
