<script lang="ts">
  // Shared controls content for the desktop sidebar and the mobile bottom
  // drawer (spec 040, T3 / AC-4): route summary row, Preferences, Saved
  // routes, and the walk action buttons. Walking only — no transport-mode
  // selector. All state and handlers live in App.svelte and are passed in.
  import WalkControls from '../WalkControls.svelte'
  import type { Prefs, SavedRoute } from '../savedRoutes'
  import {
    COMFORT_BANDS,
    COMFORT_UNAVAILABLE_TEXT,
    formatRun,
    mergeBandRuns,
  } from '../map/comfortBands'
  import type { ComfortProfileSegment } from '../map/comfortBands'
  import Attribution from './Attribution.svelte'

  // Structural subset of App.svelte's Route: everything this component
  // renders. App's full Route satisfies it.
  interface RouteSummary {
    name: string
    duration_s: number
    distance_m: number
    comfort_score: number
    applied_preference: string
    preference_source: 'auto' | 'manual'
    weather: { temperature: number }
    comfort_profile: ComfortProfileSegment[] | null
    attribution?: string
    explanation: string[]
  }

  export let route: RouteSummary | null = null
  /** WalkControls route as `[lat, lng]` pairs; empty until a route exists. */
  export let walkRoute: [number, number][] = []
  export let profile: ComfortProfileSegment[] = []
  export let prefs: Prefs | null = null
  export let showPrefs = false
  export let savedRoutes: SavedRoute[] = []
  export let savedError = ''
  export let prefsError = ''
  export let error = ''
  export let suggestionAttribution = ''

  // Handlers owned by App.svelte (sync/async state lives there).
  export let onTogglePrefs: () => void = () => {}
  export let onPrefsSave: () => void = () => {}
  export let onSaveRoute: () => void = () => {}
  export let onRecall: (id: string) => void = () => {}
  export let onDelete: (id: string) => void = () => {}

  function formatArrivalTime(durationS: number): string {
    const arrival = new Date(Date.now() + durationS * 1000)
    return arrival.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  // Terrain: dominant comfort-profile factor by covered distance, falling
  // back to the applied preference when no profile data is available.
  function terrainLabel(r: RouteSummary): string {
    if (r.comfort_profile && r.comfort_profile.length > 0) {
      const covered = new Map<string, number>()
      for (const seg of r.comfort_profile) {
        covered.set(seg.factor, (covered.get(seg.factor) ?? 0) + (seg.to_m - seg.from_m))
      }
      let best = 'unknown'
      let bestLen = -1
      covered.forEach((len, factor) => {
        if (len > bestLen) {
          bestLen = len
          best = factor
        }
      })
      return best
    }
    return r.applied_preference
  }

  $: comfortRuns = route && route.comfort_profile ? mergeBandRuns(route.comfort_profile) : []
</script>

<section class="route-summary" aria-labelledby="route-summary-title">
  <h2 id="route-summary-title">Route summary</h2>
  {#if route}
    <div class="chip">
      {route.preference_source === 'manual'
        ? `Manual: ${route.applied_preference}`
        : `Auto: ${route.applied_preference} ${route.weather.temperature}°C`}
    </div>
    <button type="button" on:click={onSaveRoute}>Save route</button>
    <h2>{route.name}</h2>
    <p class="stats">
      {Math.round(route.duration_s / 60)} min ·
      {(route.distance_m / 1000).toFixed(2)} km · arrival {formatArrivalTime(route.duration_s)} · terrain
      {terrainLabel(route)}
    </p>
    <p class="score">comfort {route.comfort_score}/100</p>
    {#if route.comfort_profile}
      <ul class="comfort-legend">
        {#each COMFORT_BANDS as b (b.band)}
          <li class="comfort-band comfort-band--{b.band}">
            <span class="comfort-swatch" style="background:{b.colour}"></span>
            {b.band} · {b.range}/100
          </li>
        {/each}
      </ul>
      <ul class="comfort-segments">
        {#each comfortRuns as run, index (index)}
          <li class="comfort-segment comfort-band--{run.band}">{formatRun(run)}</li>
        {/each}
      </ul>
    {:else}
      <p class="comfort-unavailable">{COMFORT_UNAVAILABLE_TEXT}</p>
    {/if}
    <Attribution text={route.attribution ?? suggestionAttribution} />
    <h3>Comfort factors</h3>
    <ul class="factors">
      {#each route.explanation as line, index (index)}
        <li>{line}</li>
      {/each}
    </ul>
  {:else}
    <p class="empty">No route planned yet.</p>
  {/if}
</section>

<hr class="section-divider" />

<section class="prefs" aria-labelledby="prefs-title">
  <h2 id="prefs-title">Preferences</h2>
  <button type="button" on:click={onTogglePrefs}>
    {showPrefs ? 'Hide preferences' : 'Edit preferences'}
  </button>
  {#if showPrefs && prefs}
    <label>
      Default preference
      <select bind:value={prefs.default_preference}>
        <option value="hot">Hot — prefer shade</option>
        <option value="cloudy">Cloudy — prefer sun</option>
      </select>
    </label>
    <label><input type="checkbox" bind:checked={prefs.prefer_lit} /> Prefer lit streets</label>
    <label><input type="checkbox" bind:checked={prefs.avoid_traffic} /> Avoid busy roads</label>
    <button type="button" on:click={onPrefsSave}>Save preferences</button>
  {/if}
  {#if prefsError}
    <p class="error">{prefsError}</p>
  {/if}
</section>

<hr class="section-divider" />

<section class="saved-routes" aria-labelledby="saved-routes-title">
  <h2 id="saved-routes-title">Saved routes</h2>
  {#if savedError}
    <p class="error">{savedError}</p>
  {/if}
  {#if savedRoutes.length === 0}
    <p class="empty">No saved routes yet.</p>
  {:else}
    <ul class="saved-list">
      {#each savedRoutes as saved (saved.id)}
        <li>
          <span class="saved-name">{saved.name}</span>
          <span class="saved-actions">
            <button type="button" on:click={() => onRecall(saved.id)}>Recall</button>
            <button type="button" on:click={() => onDelete(saved.id)}>Delete</button>
          </span>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<hr class="section-divider" />

<section class="walk" aria-labelledby="walk-title">
  <h2 id="walk-title">Walk</h2>
  <WalkControls route={walkRoute} {profile} />
  {#if !route}
    <p class="empty">Plan a route first, then start the walk.</p>
  {/if}
  {#if error}
    <p class="error">{error}</p>
  {/if}
</section>

<style>
  .route-summary,
  .prefs,
  .saved-routes,
  .walk {
    margin-bottom: 0.75rem;
  }

  h2 {
    font-size: 1rem;
    margin: 0.25rem 0;
  }

  .chip {
    display: inline-block;
    background: #edf2f7;
    border-radius: 999px;
    padding: 0.15rem 0.6rem;
    font-size: 0.8rem;
    margin-bottom: 0.4rem;
  }

  .stats {
    font-size: 0.9rem;
    margin: 0.25rem 0;
  }

  .score {
    font-size: 0.9rem;
    margin: 0.25rem 0;
  }

  .comfort-legend,
  .comfort-segments,
  .factors,
  .saved-list {
    list-style: none;
    padding: 0;
    margin: 0.25rem 0;
  }

  .comfort-swatch {
    display: inline-block;
    width: 0.75rem;
    height: 0.75rem;
    border-radius: 2px;
    margin-right: 0.3rem;
    vertical-align: middle;
  }

  .saved-list li {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0;
  }

  .saved-actions {
    display: flex;
    gap: 0.35rem;
  }

  .empty {
    color: #718096;
    font-size: 0.85rem;
  }

  .error {
    color: #c53030;
    font-size: 0.85rem;
  }

  .section-divider {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 0.75rem 0;
  }

  label {
    display: block;
    font-size: 0.85rem;
    margin: 0.35rem 0;
  }
</style>
