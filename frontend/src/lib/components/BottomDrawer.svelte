<script lang="ts">
  // Mobile results sheet ("Your kind of walk", spec 041 T4 / AC-3): the fixed
  // 360px bottom sheet holding the mobile walk result. Collapsed on first
  // load; it auto-opens as soon as a route exists and stays toggleable through
  // the 32x4 handle. It owns the sheet chrome — the 20/600 title, the Walking
  // pill, the brand-tint preferences summary and the shared <RouteCard /> —
  // and never renders the desktop-only <ControlsContent />.
  import { createEventDispatcher } from 'svelte'
  import RouteCard from './RouteCard.svelte'
  import { stop, walkMode } from '../walkMode'
  import type { ComfortProfileSegment } from '../map/comfortBands'

  // Structural subset of App.svelte's Route: everything the shared RouteCard
  // renders. App's full Route satisfies it.
  interface SheetRoute {
    name: string
    duration_s: number
    distance_m: number
    applied_preference: string
    preference_source: 'auto' | 'manual'
    weather: { temperature: number }
    comfort_profile: ComfortProfileSegment[] | null
    attribution?: string
    explanation: string[]
  }

  export let route: SheetRoute | null = null
  /** Comfort profile segments; empty until a route with profile data exists. */
  export let segments: ComfortProfileSegment[] = []
  /** `Quieter` meta only shows when the walk avoids busy roads. */
  export let avoidTraffic = false
  export let suggestionAttribution = ''
  /** Brand-tint summary of the preferences this walk was planned with. */
  export let preferenceSummary = 'More shade · Quieter streets'
  /** Controlled expansion: App owns it so a map pick can open the builder. */
  export let open = false
  /**
   * Set by App while a map-picked destination is still building its route:
   * auto-open is parked so the builder state (not a stale route) is shown.
   */
  export let suppressAutoOpen = false
  /** Inline error slot of the no-route builder. */
  export let error = ''
  /** False while the picked destination has no buildable coordinates. */
  export let canBuild = true
  /** Map-picked destination shown in the no-route builder. */
  export let destinationLabel = ''
  /** True while App is building the route for the picked destination. */
  export let building = false

  const dispatch = createEventDispatcher<{
    edit: null
    start: null
    save: null
    saved: null
    build: null
  }>()

  // Auto-open once a walk result exists, unless App parked it for a build;
  // the handle still collapses it.
  $: if (route && !suppressAutoOpen) open = true

  function toggle() {
    open = !open
  }

  // Material Design glyphs kept inline: the sheet only needs these two.
  // Material 'arrow_upward': the design's Start walk glyph (not the walker).
  const ARROW_PATH = 'M4 12l1.41 1.41L11 7.83V20h2V7.83l5.58 5.59L20 12l-8-8-8 8z'
  const WALK_PATH =
    'M13.5 5.5c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zM9.8 8.9L7 23h2.1l1.8-8 2.1 2v6h2v-7.5l-2.1-2 .6-3C14.8 12 16.8 13 19 13v-2c-1.9 0-3.5-1-4.3-2.4l-1-1.6c-.4-.6-1-1-1.7-1-.3 0-.5.1-.8.1L6 8.3V13h2V9.6l1.8-.7z'
  const SAVE_PATH =
    'M17 3H7c-1.1 0-1.99.9-1.99 2L5 21l7-3 7 3V5c0-1.1-.9-2-2-2zm0 15l-5-2.18L7 18V5h10v13z'
</script>

<div class="bottom-drawer" class:open data-open={open} data-testid="drawer">
  <button
    type="button"
    class="grab-handle"
    data-testid="drawer-handle"
    aria-expanded={open}
    aria-controls="bottom-drawer-body"
    aria-label={open ? 'Collapse walk results' : 'Expand walk results'}
    on:click={toggle}
  >
    <span class="handle-bar" aria-hidden="true"></span>
  </button>

  <div class="drawer-body" id="bottom-drawer-body" role="region" aria-label="Your kind of walk">
    <div class="sheet-head">
      <h2 class="sheet-title">Your kind of walk</h2>
      <span class="walk-pill">
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d={WALK_PATH} />
        </svg>
        Walking
      </span>
      <button
        type="button"
        class="sheet-saved"
        data-testid="saved-walks-mobile"
        on:click={() => dispatch('saved')}
      >
        Saved
      </button>
    </div>

    <div class="prefs-row">
      <span class="prefs-text">{preferenceSummary}</span>
      <button
        type="button"
        class="prefs-edit"
        data-testid="prefs-edit"
        on:click={() => dispatch('edit')}>Edit</button
      >
    </div>

    <RouteCard {route} profile={segments} {avoidTraffic} {suggestionAttribution} compact />

    {#if route}
      <div class="sheet-cta">
        {#if $walkMode.active || $walkMode.arrived}
          <button
            type="button"
            class="walk-stop"
            data-testid="stop-walk"
            aria-label="Stop walk mode"
            on:click={() => stop()}
          >
            <span>Stop walk</span>
          </button>
        {:else}
          <button
            type="button"
            class="walk-start"
            data-testid="start-walk"
            aria-label="Start walk mode"
            on:click={() => dispatch('start')}
          >
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d={ARROW_PATH} />
            </svg>
            <span>Start walk</span>
          </button>
        {/if}
        <button
          type="button"
          class="save-route"
          aria-label="Save route"
          on:click={() => dispatch('save')}
        >
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d={SAVE_PATH} />
          </svg>
        </button>
      </div>
    {:else}
      <!-- No-route builder (042 T1): a map-picked destination has no walk yet,
           so the sheet shows where you are going, the preferences the walk
           will use and the one action that builds it. -->
      <div class="builder" data-testid="route-builder">
        {#if destinationLabel}
          <p class="builder-destination">{destinationLabel}</p>
        {/if}
        <button
          type="button"
          class="build-route"
          data-testid="build-route"
          disabled={!canBuild || building}
          on:click={() => dispatch('build')}
        >
          {building ? 'Finding your walk…' : 'Build route'}
        </button>
        {#if error}
          <p class="builder-error" role="alert" data-testid="build-error">{error}</p>
        {/if}
      </div>
    {/if}

    <slot />
  </div>
</div>

<style>
  /* Fixed 360px sheet pinned to the bottom of the viewport. The collapsed
     state is a downward translation so only the handle band stays visible
     while the sheet keeps its 360px geometry. */
  .bottom-drawer {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 40;
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 360px;
    background: var(--cwr-surface, #fff);
    border-radius: 18px 18px 0 0;
    box-shadow: var(--cwr-shadow-card);
    transform: translateY(calc(100% - 24px));
    transition: transform 0.25s ease;
  }

  .bottom-drawer.open {
    transform: translateY(0);
  }

  .grab-handle {
    display: flex;
    flex: none;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 24px;
    padding: 0;
    background: transparent;
    border: none;
    cursor: pointer;
  }

  .grab-handle:focus-visible {
    outline: 2px solid var(--cwr-brand);
    outline-offset: -2px;
  }

  /* Visible affordance: the 32x4 grab bar. */
  .handle-bar {
    display: block;
    width: 32px;
    height: 4px;
    border-radius: 2px;
    background: var(--cwr-line-strong, #d5dbd7);
  }

  .drawer-body {
    display: flex;
    flex: 1;
    min-height: 0;
    flex-direction: column;
    overflow-y: auto;
    padding: 0 16px 4px;
  }
  /* The shared RouteCard renders its duration at 25/600 inside the sheet.
     :global() because the card is a child component. */
  :global(.route-card .duration) {
    font-size: 25px;
    font-weight: 600;
  }

  .sheet-saved {
    border: none;
    background: transparent;
    color: var(--cwr-brand, #17765c);
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
  }

  .sheet-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 2px 0 10px;
  }

  .sheet-title {
    margin: 0;
    color: var(--cwr-ink, #12211b);
    font-size: 20px;
    font-weight: 600;
    line-height: 1.25;
  }

  .walk-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    border-radius: 999px;
    background: var(--cwr-surface-muted, #eef2ec);
    color: var(--cwr-ink-muted, #4a5568);
    font-size: 12px;
    font-weight: 500;
    line-height: 1;
    white-space: nowrap;
  }

  .walk-pill svg {
    width: 14px;
    height: 14px;
  }

  .prefs-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin: 0 0 12px;
    padding: 10px 12px;
    border-radius: 12px;
    background: var(--cwr-brand-tint, #e7f2ec);
  }

  .prefs-text {
    color: var(--cwr-brand, #17765c);
    font-size: 12px;
    font-weight: 500;
  }

  .prefs-edit {
    padding: 0;
    border: none;
    background: none;
    color: var(--cwr-brand, #17765c);
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
  }

  .sheet-cta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: auto;
    padding-top: 12px;
  }

  .walk-start,
  .walk-stop {
    display: inline-flex;
    flex: 1;
    align-items: center;
    justify-content: center;
    gap: 8px;
    min-width: 0;
    height: 48px;
    padding: 0 20px;
    border: none;
    border-radius: 999px;
    background: var(--cwr-brand, #17765c);
    color: #fff;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
  }

  .walk-start svg,
  .walk-stop svg {
    width: 20px;
    height: 20px;
  }

  .save-route {
    display: inline-flex;
    flex: none;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    padding: 0;
    border: 1px solid var(--cwr-line-strong, #d5dbd7);
    border-radius: 24px;
    background: #fff;
    color: var(--cwr-brand, #17765c);
    cursor: pointer;
  }

  .save-route svg {
    width: 20px;
    height: 20px;
  }
</style>
