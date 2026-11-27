<script lang="ts">
  /**
   * ComfortPanel (spec 041, T2 / AC-1, AC-4): the desktop "Your comfort"
   * panel rendered directly under the endpoint card in the planning sidebar.
   *
   * It owns three controls:
   *  - a weather-advice banner (hidden when there is no `route.weather`),
   *  - a 3-way Sun & shade segmented control mapping to the route preference
   *    values `hot` / `balanced` / `cloudy`,
   *  - a Quieter streets toggle bound to `avoid_traffic`.
   *
   * The component is intentionally presentational: App.svelte owns the saved
   * `Prefs` state and persistence. It can consume it either through the
   * two-way bindings (`bind:preference`, `bind:avoidTraffic`) or through the
   * dispatched `shade` / `quieter` events; both are emitted so the parent can
   * use whichever contract fits its save path. The component also updates its
   * own bound props, so it never depends on the parent re-rendering for
   * `aria-pressed`/`aria-checked` state.
   */
  import { createEventDispatcher } from 'svelte'
  import { materialPaths } from '../map/material'
  import { weatherAdvice } from '../routeMeta'

  // Svelte's instance `<script>` treats `export` as a prop declaration, so
  // these type helpers stay local to the component.
  type ShadePreference = 'hot' | 'cloudy' | 'balanced'

  /** The subset of `route.weather` this panel renders. */
  interface ComfortWeather {
    temperature: number
    cloudCover: number
  }

  /** Current shade preference; two-way bindable with the host page. */
  export let preference: ShadePreference = 'balanced'
  /** Current quieter-streets preference; two-way bindable with the host page. */
  export let avoidTraffic = false
  /** Route weather; the advice banner renders nothing without it. */
  export let weather: ComfortWeather | null = null

  const dispatch = createEventDispatcher<{
    shade: ShadePreference
    quieter: boolean
    reset: void
  }>()

  // Inlined Material Symbols (Outlined) paths. Kept local so this component
  // does not force an unrelated change to `map/material.ts` for the new
  // redesign icons; they follow the same 24×24 `fill="currentColor"` style.
  const wbSunnyPath =
    'M6.76 4.84l-1.8-1.79-1.41 1.41 1.79 1.79 1.42-1.41zM4 10.5H1v2h3v-2zm9-9.95h-2V3.5h2V.55zm7.45 3.91l-1.41-1.41-1.79 1.79 1.41 1.41 1.79-1.79zm-3.21 13.7l1.79 1.8 1.41-1.41-1.8-1.79-1.4 1.4zM20 10.5v2h3v-2h-3zm-8-5c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm-1 16.95h2V19.5h-2v2.95zm-7.45-3.91l1.41 1.41 1.79-1.8-1.41-1.41-1.79 1.8z'

  // Material 'park': tree cover for the shade option (the design uses a
  // tree, not a sun, for More shade).
  const parkPath = 'M17 12h2L12 2 5.05 12H7l-3.9 6h6.92v4h4v-4h6.9L17 12z'

  const cloudPath =
    'M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM19 18H6c-2.21 0-4-1.79-4-4s1.79-4 4-4h.71C7.37 7.69 9.48 6 12 6c3.04 0 5.5 2.46 5.5 5.5v.5H19c1.66 0 3 1.34 3 3s-1.34 3-3 3z'

  $: advice = weather ? weatherAdvice(weather) : null

  function setShade(value: ShadePreference): void {
    preference = value
    dispatch('shade', value)
  }

  function toggleQuieter(): void {
    avoidTraffic = !avoidTraffic
    dispatch('quieter', avoidTraffic)
  }

  function reset(): void {
    dispatch('reset')
  }
</script>

<div class="comfort-panel" data-testid="comfort-panel">
  <div class="comfort-heading">
    <span class="heading-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d={materialPaths.tune} /></svg>
    </span>
    <h2 class="heading-title">Your comfort</h2>
    <button type="button" class="reset-btn" on:click={reset}>Reset</button>
  </div>

  {#if advice}
    <div class="weather-banner" role="status" aria-label="Weather advice">
      <span class="weather-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d={wbSunnyPath} /></svg>
      </span>
      <div class="weather-copy">
        <p class="weather-title">{advice.title}</p>
        <p class="weather-sub">{advice.sub}</p>
      </div>
    </div>
  {/if}

  <div class="shade-group">
    <p class="shade-label">Sun &amp; shade</p>
    <div class="segmented" role="group" aria-label="Sun and shade preference">
      <button
        type="button"
        class="segment {preference === 'hot' ? 'active' : ''}"
        data-testid="shade-more"
        aria-pressed={preference === 'hot'}
        on:click={() => setShade('hot')}
      >
        <span class="segment-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d={parkPath} /></svg>
        </span>
        <span class="segment-label">More shade</span>
      </button>

      <button
        type="button"
        class="segment {preference === 'balanced' ? 'active' : ''}"
        data-testid="shade-balanced"
        aria-pressed={preference === 'balanced'}
        on:click={() => setShade('balanced')}
      >
        <span class="segment-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d={cloudPath} /></svg>
        </span>
        <span class="segment-label">Balanced</span>
      </button>

      <button
        type="button"
        class="segment {preference === 'cloudy' ? 'active' : ''}"
        data-testid="shade-more-sun"
        aria-pressed={preference === 'cloudy'}
        on:click={() => setShade('cloudy')}
      >
        <span class="segment-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d={wbSunnyPath} /></svg>
        </span>
        <span class="segment-label">More sun</span>
      </button>
    </div>
  </div>

  <div class="quieter-row">
    <div class="quieter-copy">
      <p class="quieter-title">Quieter streets</p>
      <p class="quieter-sub">Stay farther from busy roads</p>
    </div>
    <button
      type="button"
      class="switch {avoidTraffic ? 'on' : ''}"
      class:on={avoidTraffic}
      data-testid="quieter"
      role="switch"
      aria-checked={avoidTraffic}
      aria-label="Quieter streets"
      on:click={toggleQuieter}
    >
      <span class="knob"></span>
    </button>
  </div>
</div>

<style>
  .comfort-panel {
    display: flex;
    flex-direction: column;
    gap: 16px;
    width: 340px;
    color: var(--cwr-ink);
  }

  .comfort-heading {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .heading-icon {
    display: inline-flex;
    width: 18px;
    height: 18px;
    color: var(--cwr-ink);
  }

  .heading-icon svg {
    width: 18px;
    height: 18px;
  }

  .heading-title {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    line-height: 1.2;
    color: var(--cwr-ink);
  }

  .reset-btn {
    margin-left: auto;
    padding: 4px 6px;
    border: none;
    border-radius: 6px;
    background: transparent;
    font-size: 12px;
    font-weight: 400;
    color: #728077;
    cursor: pointer;
  }

  .reset-btn:hover {
    color: var(--cwr-brand);
  }

  .weather-banner {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 340px;
    height: 52px;
    box-sizing: border-box;
    padding: 0 12px;
    border-radius: 12px;
    background: var(--cwr-sun-bg);
  }

  .weather-icon {
    display: inline-flex;
    flex: 0 0 auto;
    width: 25px;
    height: 25px;
    color: var(--cwr-sun-ink);
  }

  .weather-icon svg {
    width: 25px;
    height: 25px;
  }

  .weather-copy {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .weather-title {
    margin: 0;
    font-size: 12px;
    font-weight: 600;
    line-height: 1.3;
    color: var(--cwr-sun-ink);
  }

  .weather-sub {
    margin: 0;
    font-size: 11px;
    font-weight: 400;
    line-height: 1.3;
    color: var(--cwr-sun-sub);
  }

  .shade-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .shade-label {
    margin: 0;
    font-size: 12px;
    font-weight: 500;
    color: #65776b;
  }

  .segmented {
    display: flex;
    align-items: center;
    width: 340px;
    height: 40px;
    box-sizing: border-box;
    padding: 3px;
    border-radius: 11.4px;
    background: var(--cwr-control-bg);
  }

  .segment {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    width: 110px;
    height: 34px;
    box-sizing: border-box;
    padding: 0 6px;
    border: none;
    border-radius: 8.4px;
    background: transparent;
    color: var(--cwr-muted);
    cursor: pointer;
  }

  .segment.active {
    background: #ffffff;
    color: var(--cwr-brand);
    box-shadow:
      inset 0 0 0 1.5px var(--cwr-brand),
      var(--cwr-shadow-pill);
  }

  .segment-icon {
    display: inline-flex;
    width: 16px;
    height: 16px;
  }

  .segment-icon svg {
    width: 16px;
    height: 16px;
  }

  .segment-label {
    font-size: 11px;
    font-weight: 500;
    white-space: nowrap;
  }

  .quieter-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    width: 340px;
  }

  .quieter-copy {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .quieter-title {
    margin: 0;
    font-size: 14px;
    font-weight: 500;
    line-height: 1.3;
    color: var(--cwr-ink);
  }

  .quieter-sub {
    margin: 0;
    font-size: 11px;
    font-weight: 400;
    line-height: 1.3;
    color: var(--cwr-muted-2);
  }

  .switch {
    position: relative;
    flex: 0 0 auto;
    width: 40px;
    height: 22px;
    padding: 0;
    border: none;
    border-radius: 999px;
    background: var(--cwr-control-bg);
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .switch.on {
    background: var(--cwr-brand);
  }

  .knob {
    position: absolute;
    top: 3px;
    left: 3px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #ffffff;
    box-shadow: var(--cwr-shadow-pill);
    transition: transform 0.15s ease;
  }

  .switch.on .knob {
    transform: translateX(18px);
  }
</style>
