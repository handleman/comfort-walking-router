> **The Figma cache is local and gitignored (updated 2026-11-28).** The
> `designs/<key>/` IR, renders, brief and lock are rebuilt by `hq design sync`
> and must not be committed. The design.toml/swarm.yaml pin the frames.

# 041 design contract (Figma → code)

This is the operator's transcription of the three Figma frames into exact,
textual rules. The coder cannot see the PNGs, so this file is the visual source
of truth for the tasks. The cached references are
`designs/jFwR8VpN5Nls2RjN2Ifh4y/6-61.png` (desktop), `6-53.png` (mobile
results) and `6-57.png` (mobile preferences); the brief is
`designs/jFwR8VpN5Nls2RjN2Ifh4y/design-brief.md`.

## Product decisions

- Brand stays **Comfort Walking Router**. The design's `mellow.walk` wordmark
  is **not** used. Keep the tagline **"A nicer way to get there."**
- Honest controls only: the design's **Extra walking time** slider and the
  second route option ("20 min · Fastest", "2 routes", the fastest row) are
  **out of scope** because the API returns one route with no detour budget.
  The map layer pills ("Comfort route / Shade / Noise") are also omitted: there
  is no layer data. Do not render disabled/fake controls.
- The 040 layout is superseded by this shell: desktop gets a 72 px top nav and
  a 380 px left panel; mobile keeps the floating endpoint card and bottom
  sheets. Keep the 040 sidebar edge handle and the 040 test ids/hooks.

## Viewport mapping

The frames include a mocked browser chrome (40 px desktop, 48 px mobile). **Do
not render browser chrome.** Treat it as absent:

- Desktop: nav at `y=0..72`; the planning panel `y=72..bottom`; the map is
  full-bleed behind both.
- Mobile: endpoint card top `16`; weather chip below it; sheets are anchored to
  the viewport bottom. Ignore the frame's `y - 48` browser offset for the top
  overlay and keep the sheet heights below.

## Tokens

Add these CSS custom properties in `frontend/src/app.css` (inside `@theme` or
`:root`). Names are part of the contract (`design.toml` checks them).

| Token | Value | Use |
| --- | --- | --- |
| `--cwr-page` | `#f7faf5` | page/background |
| `--cwr-surface` | `#ffffff` | nav, panel, cards, sheets |
| `--cwr-ink` | `#223c32` | headings, primary text |
| `--cwr-ink-2` | `#35443e` | map badge text |
| `--cwr-muted` | `#63756a` | secondary text |
| `--cwr-muted-2` | `#849087` | tertiary text |
| `--cwr-brand` | `#17765c` | primary green (buttons, active) |
| `--cwr-brand-soft` | `#d8f3e7` | active pill, badge background |
| `--cwr-brand-tint` | `#f0f6f2` | summary row, selected card |
| `--cwr-sun-bg` | `#fff9e9` | weather chip |
| `--cwr-sun-ink` | `#806435` | weather text |
| `--cwr-sun-sub` | `#947d51` | weather subtext |
| `--cwr-blue` | `#4085ef` | origin / my-location |
| `--cwr-line` | `#e6ebe7` | hairline borders |
| `--cwr-line-strong` | `#d5dbd7` | card outline, sheet handle |
| `--cwr-control-bg` | `#f0f3ef` | segmented control track |
| `--cwr-selected-bg` | `#f7f9f6` | selected route card |
| `--cwr-radius-card` | `18px` | cards/sheets |
| `--cwr-radius-panel` | `12px` | small cards, map controls |
| `--cwr-shadow-card` | `0 3px 14px rgb(20 41 31 / 0.12)` | floating cards/sheets |
| `--cwr-shadow-pill` | `0 2px 6px rgb(0 0 0 / 0.12)` | active segment |

Typography: self-hosted **Inter Variable** (`@fontsource-variable/inter`,
already in `package.json`). `font-family: Inter Variable, Inter, system-ui,
-apple-system, sans-serif`. Weights: 400, 500, 600. No other font.

| Role | Size / weight / line-height | Colour |
| --- | --- | --- |
| Route duration (desktop card) | 26 / 600 / 31.5 | `--cwr-brand` |
| Route duration (mobile card) | 25 / 600 / 30 | `--cwr-brand` |
| Sheet title (preferences) | 23 / 600 / 28 | `--cwr-ink` |
| Sheet title (mobile results) | 20 / 600 / 24 | `--cwr-ink` |
| Section heading | 16 / 600 / 19.5 | `--cwr-ink` |
| Body strong | 14 / 600 / 17 | `--cwr-ink` |
| Body | 14 / 500 / 17 | `--cwr-ink` |
| Body muted | 13 / 400 / 16 | `#738078` |
| Small | 12 / 500 / 14.5 | `--cwr-muted` |
| Small muted | 11 / 400 / 13.5 | `--cwr-muted-2` |
| Micro label | 11 / 500 / 13 | `--cwr-muted` |

## Desktop frame (`6:61`, implement at 1280×800+)

### Top nav — `[data-testid="top-nav"]`

- Fixed, `height: 72px`, full width, `--cwr-surface`, bottom hairline
  `1px solid var(--cwr-line)`, z-index above the map and panel.
- Left (24 px): 40×40 rounded-8 brand tile in `--cwr-brand` with a white
  `directions_walk` icon (24 px); 1×28 divider at x≈96 in `--cwr-line`; tagline
  "A nicer way to get there." 13/400 `#7b887f`.
- Centre: "Plan a walk" 14/600 `--cwr-brand`; "Saved walks" 14/500 `#728077`;
  gap ~28 px. Both are real buttons.
- Right (24 px padding): weather chip (hidden until a route exists) with a sun
  icon, 12/500 `--cwr-sun-ink` on `--cwr-sun-bg`, pill, 32 px tall; then "How
  it works" 13/500 `--cwr-muted` + 16 px chevron. Both buttons.
- Brand name (visually hidden or beside the mark): **Comfort Walking Router**
  inside `[data-testid="brand-name"]`.

### Planning panel — `[data-testid="sidebar"]`

- Fixed left, `top: 72px`, `width: 380px`, full remaining height, white,
  `padding: 20px`, column flex, content scrolls, CTA pinned bottom.
- Keep `data-testid="sidebar"`, the edge handle
  `[data-testid="sidebar-handle"]` (040) and the collapsed behaviour.
- Remove the old `<h1>` from the panel; the nav carries the brand.

Order and geometry (x = 20, width = 340):

1. **Endpoint card** `[data-testid="top-card"]`: `340×108`, radius 12, white,
   `1px solid var(--cwr-line)`, shadow none. Two 33 px rows: blue 9 px dot +
   title 14/500 ink + address 11/400 `--cwr-muted-2`; destination green/dark
   pin + title/address; 20 px `swap_vert` at the right. It is the existing
   `TopSearchCard` (same inputs, placeholders, pick/swap behaviour, test ids).
2. **Your comfort** heading: 18 px `tune` icon + "Your comfort" 16/600 ink +
   "Reset" 12/400 `#728077` button on the right.
3. **Weather advice** (only when `route.weather` exists): 340×52, radius 12,
   `--cwr-sun-bg`; sun 25 px; title 12/600 `--cwr-sun-ink`; sub 11/400
   `--cwr-sun-sub` (copy below).
4. **Sun & shade**: label 12/500 `#65776b`; segmented control 340×40, radius
   11.4, track `--cwr-control-bg`, padding 3; three 110×34 options with 16 px
   icons + 11 px labels:
   - More shade (sun/shade icon) → `hot`, active `#17765c` on white with
     `--cwr-shadow-pill`
   - Balanced (cloud icon) → `balanced`
   - More sun (sun icon) → `cloudy`
5. **Quieter streets** row: title 14/500 ink, sub 11/400 `--cwr-muted-2`
   "Stay farther from busy roads"; brand toggle 40×22 bound to
   `avoid_traffic`.
6. **Choose your walk** heading 16/600 + honest count "1 route" 11/400.
7. **Route card**: 340×76, radius 14, `1px solid var(--cwr-line-strong)`;
   selected state `border-color: var(--cwr-brand)`, background
   `--cwr-selected-bg`. Duration 26/600 brand + "1.8 km" 12/400 `#738078`;
   "Best fit" pill 12/500 `#326647` on `--cwr-brand-soft`; meta row 11/500
   `#42705b` with a sun icon "NN% shaded" and a quiet icon "Quieter" (only
   when `avoid_traffic`). Use the route's real distance/duration and the
   profile-derived shaded percentage.
8. **CTA row** pinned bottom: "Start walk" button 288×52, radius 12,
   `--cwr-brand`, white 14/600 with `directions_walk`; save-route icon button
   44×44 radius 12, `1px solid var(--cwr-line-strong)`, `bookmark_border`
   (toggles to `bookmark` when saved). Keep `button.walk-start`,
   `data-testid="start-walk"` and the Stop/Auto-center controls (a compact
   row that appears only while walk mode is active).

Keep the e2e hooks: `section.route-summary`, `.chip`, `.comfort-segments`,
`ul.factors`, `.comfort-legend`, `.attribution`, `button.walk-start`,
`button.walk-stop`.

### Map overlays

- Map is full-bleed (`#map`, `data-testid="map"`), under the nav/panel.
- Right controls, 24 px from the right: locate 44×44 white radius 12 at
  `bottom: 106px`; zoom group 44×89 white radius 12 at `bottom: 24px` with
  `add`/`remove` 44 px halves, separated by a hairline. Both are real buttons.
- Legend bottom-left at `left: 404px` (24 px from the panel), `bottom: 21px`:
  257×37 white radius 10, two rows: green "Your comfort route", grey "Fastest
  route" — only the first is real here; render the second as a disabled/absent
  key? Do **not** invent a fastest route: render only the comfort key.
- Attribution stays bottom-right (`© OpenStreetMap contributors`) and keeps
  `.attribution`.
- Route badge: a Leaflet marker at the route midpoint with a green
  (`--cwr-brand`) rounded-12 card: duration 21/600 white and the preference
  summary 15/500 `--cwr-brand-soft` ("Quieter · more shade"). No second badge.
- Destination callout: a white rounded-12 card near the destination pin with
  the place name 21/600 ink and the label "Park entrance"/address 15/500
  `--cwr-muted`; use a Leaflet permanent tooltip/popup; do not block the map.

## Mobile results frame (`6:53`)

- 390 px wide; map full-bleed; no top nav.
- Endpoint card at `top:16px`, `left:16px`, `358×76`, radius 18, white, shadow:
  back arrow (16 px), two rows 14/600 + 9 px dot, swap at right; existing
  search inputs/placeholders.
- Weather pill at `top:121px`, `left:16px`, 104×32, radius 99, `--cwr-sun-bg`,
  sun 16 px + 12/500 `#6d5527` ("Sunny · 26°"), hidden without weather.
- Results sheet `[data-testid="mobile-sheet"]`: bottom-anchored, `height:360px`,
  width 100%, radius 18 18 0 0, white, `--cwr-shadow-card`; handle 32×4
  `--cwr-line-strong` at 20 px.
  - Title "Your kind of walk" 20/600 + "Walking" pill 12/500 muted with a walk
    icon.
  - Preferences summary row: `--cwr-brand-tint`, radius 12, 12/500 brand
    "More shade · Quieter streets" + "Edit" 12/600; tapping Edit opens the
    preferences sheet.
  - Best route card as desktop (radius 14), duration 25/600, km 12/400,
    Best fit pill, meta 12/500.
  - **No fastest row, no second card.**
  - CTA row 358 px wide: Start walk 15/600 + 44 px save button.
- Drawer handle/test ids stay: `[data-testid="drawer"]`,
  `[data-testid="drawer-handle"]`; auto-open when a route exists, collapsed
  before (still toggleable).
- Locate button 44×44 white radius 22 at `right:16px`, just above the sheet.

## Mobile preferences sheet (`6:57`)

- Full-width bottom sheet `[data-testid="prefs-sheet"]`, `height:604px`
  (max 604, `max-height: 92vh`), radius 18 18 0 0, white, shadow; scrim
  `rgb(23 43 36 / 0.35)` above the map, closes on scrim/×/Escape.
- Handle 32×4; title "Walk your way" 23/600 ink; subtitle "Find the route that
  feels good." 13/400 `#738078`; close 34×34 with `close` icon.
- Weather card 350×60, radius 12, `--cwr-sun-bg`: sun 28; "Sunny, 26°C" 14/600
  `#6e5428`; "A shady route can feel cooler." 12/400 `#8d774d`; hidden without
  weather.
- **Sun & shade** 14/600 + "Your preference" 11/400 right; segmented 350×64
  (112×56 options, 20 px icons, 11 px labels) with the same hot/balanced/cloudy
  mapping; helper "Prefer tree cover and shaded streets." 12/400.
- **Quieter streets** 14/600 + "Stay farther from noisy, busy roads." 12/400 +
  switch.
- **No Extra walking time.**
- "Apply preferences" 350×52, radius 12, brand, white 14/600, check icon;
  saves the prefs, closes the sheet and re-plans when both endpoints are set.

## Copy and data

- Weather advice (when `temperature >= 25` and `cloudCover < 70`):
  "A little shade goes a long way" / "Sunny, {t}°C · shade recommended".
  Overcast (`cloudCover >= 70`): "A brighter route feels better" /
  "Overcast, {t}°C · sun recommended". Otherwise: "A balanced route" /
  "{t}°C · balanced conditions".
- Mobile weather pill: "Sunny · {t}°" / "Cloudy · {t}°" / "{t}°".
- Nav weather chip: "{area} · Sunny, {t}°C" only when a route/place is known;
  otherwise hide. Do not invent a city.
- Shaded percent: sum of `(to_m - from_m)` over profile segments whose
  `factor === "shade"`, divided by the profile's total covered distance,
  rounded. Hide the metric when there is no profile.
- "Quieter" appears only when `avoid_traffic` is on. "More shade" active for
  `hot`, "Balanced" for `balanced`, "More sun" for `cloudy`.
- Sidebar "Reset": `default_preference = "balanced"`, `avoid_traffic = false`,
  `prefer_lit = false`; save and re-plan if a route exists.
- Titles: `<title>Comfort Walking Router</title>` (unchanged).

## Icons (Material Symbols, 24×24, `fill="currentColor"`)

Existing: `directions_walk`, `my_location`, `place`, `swap_vert`, `tune`,
`close`, `drag_handle`, `expand_more`, `more_horiz`, `share`.

Add to `frontend/src/lib/map/material.ts`: `wb_sunny`, `cloud`, `bookmark`,
`bookmark_border`, `chevron_right`, `add`, `remove`, `near_me`, `check`, `edit`,
`layers` (only if used), `search`. Use inline `<svg viewBox="0 0 24 24"
fill="currentColor" aria-hidden="true">` and keep the button's accessible name.
No emoji, no icon font.

## Accessibility

- Every icon-only button has `aria-label`; every control is keyboard reachable
  with a visible `:focus-visible` ring (2 px `--cwr-brand`, 2 px offset).
- The segmented control is a `role="group"` of `button aria-pressed`; the
  switch is a real checkbox or `role="switch"` with `aria-checked`.
- The sheets are `role="dialog" aria-modal="true"` with a labelled title; focus
  moves in and returns to the opener; Escape closes.
- Colour contrast: ink on surface ≥ 7:1, brand white text ≥ 4.5:1, muted small
  text ≥ 4.5:1.
- Respect `prefers-reduced-motion` (no slide when set).
- Mobile: no horizontal overflow at 390; no zero-size controls; the sheet must
  not cover the whole map (keep the top 240 px visible).

## Deviations (explicit)

| Frame | Deviation | Why |
| --- | --- | --- |
| Extra walking time slider | omitted | no detour budget in the API |
| Second route / "2 routes" / fastest row | omitted | API returns one route |
| Comfort route / Shade / Noise pills | omitted | no map layer data |
| `mellow.walk` wordmark | replaced by Comfort Walking Router | brand decision |
| Sidebar edge handle | kept | 040 contract |
| Browser chrome | not rendered | real browser owns it |
| Inter | self-hosted variable font | design font, offline-safe |

Follow-ups (not this spec): route alternatives (multiple Mapbox routes) and an
extra-walking-time budget; a shade/noise map layer.
