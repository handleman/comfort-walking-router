<script lang="ts">
  /**
   * TopSearchCard (spec 040, task T2, AC-2):
   * Presentational two-row card floating over the map. Row 1 is the
   * origin (blue my-location dot + "My location" label), row 2 is the
   * destination (red pin marker). A drag-handle divider sits between
   * the rows, and the `↑↓` swap action lives on the right. Each row
   * hosts the existing SearchInput combobox; the row markers (blue
   * my-location dot / red destination pin) are the map-pick triggers
   * and the text inputs stay pure search fields.
   *
   * Two-way contract (Svelte 4 `export let` + `bind:` in markup):
   * - `startQuery` / `endQuery` mirror the SearchInput `query` values.
   * - `startSelected` / `endSelected` mirror the SearchInput `selected`
   *   values, so the host page owns the route endpoints.
   * - `baseUrl` is forwarded one-way to the SearchInput fetcher.
   * - `activePick` mirrors the page's active map-pick role ('start' |
   *   'end' | null) for the ⌖ buttons' aria-pressed state.
   * Events: `pick` (PickRole), `swap`. (T14: the `⋯` more-options button
   * and its `more` event were removed; Preferences lives in the panel.)
   */
  import { createEventDispatcher } from 'svelte'
  import SearchInput from './SearchInput.svelte'
  import type { Suggestion } from '../search/suggestions'
  import type { PickRole } from '../map/picker'
  import { materialPaths } from '../map/material'

  /** Origin query text; two-way bound with the host page. */
  export let startQuery = ''
  /** Destination query text; two-way bound with the host page. */
  export let endQuery = ''
  /** Selected origin suggestion; two-way bound with the host page. */
  export let startSelected: Suggestion | null = null
  /** Selected destination suggestion; two-way bound with the host page. */
  export let endSelected: Suggestion | null = null
  /** Currently active map-pick role ('start' | 'end' | null), two-way bound. */
  export let activePick: PickRole | null = null

  /** Base URL forwarded one-way to the SearchInput suggestion fetcher. */
  export let baseUrl = ''

  /** Extra classes forwarded to the host element (e.g. positioning). */
  export let extraClass: string = ''

  /** Dispatched when the user clicks a ⌖ pick button. */
  const dispatch = createEventDispatcher<{
    pick: PickRole
    swap: void
  }>()

  function beginPick(role: PickRole): void {
    dispatch('pick', role)
  }
</script>

<div class="top-search-card {extraClass}" role="group" aria-label="Route search">
  <div class="row row-origin">
    <button
      type="button"
      class="marker marker-origin"
      aria-label="Pick start on map"
      aria-pressed={activePick === 'start'}
      on:click={() => beginPick('start')}
    >
      <span class="marker-icon marker-icon--origin" aria-hidden="true"
        ><svg viewBox="0 0 24 24" fill="currentColor"><path d={materialPaths.my_location} /></svg
        ></span
      >
      <span class="marker-label" aria-hidden="true">My location</span>
    </button>
    <span class="pick-row">
      <SearchInput
        {baseUrl}
        placeholder="e.g. Marienplatz, Munich"
        required
        bind:query={startQuery}
        bind:selected={startSelected}
      />
    </span>
  </div>

  <div class="divider" role="separator" aria-label="Drag to reorder">
    <span class="drag-handle" aria-hidden="true">⠿</span>
    <span class="divider-line" aria-hidden="true"></span>
    <span class="divider-actions">
      <button
        type="button"
        class="action-btn"
        aria-label="Swap origin and destination"
        on:click={() => dispatch('swap', undefined)}
        ><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"
          ><path d={materialPaths.swap_vert} /></svg
        ></button
      >
    </span>
  </div>

  <div class="row row-destination">
    <button
      type="button"
      class="marker marker-destination"
      aria-label="Pick end on map"
      aria-pressed={activePick === 'end'}
      on:click={() => beginPick('end')}
    >
      <span class="marker-icon marker-icon--place" aria-hidden="true"
        ><svg viewBox="0 0 24 24" fill="currentColor"><path d={materialPaths.place} /></svg></span
      >
    </button>
    <span class="pick-row">
      <SearchInput
        {baseUrl}
        placeholder="e.g. Englischer Garten"
        required
        bind:query={endQuery}
        bind:selected={endSelected}
      />
    </span>
  </div>
</div>

<style>
  .top-search-card {
    position: absolute;
    top: 0.75rem;
    left: 0.75rem;
    right: 0.75rem;
    z-index: 1000;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    padding: 0.5rem;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25);
  }

  .row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .pick-row {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    flex: 1;
    min-width: 0;
  }

  .pick-row :global(.search-combobox) {
    flex: 1;
    min-width: 0;
  }

  .marker {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    flex-shrink: 0;
    border: none;
    background: transparent;
    cursor: pointer;
    padding: 0.25rem 0.4rem;
    border-radius: 6px;
    color: #555;
  }

  .marker:hover {
    background: #f1f3f4;
  }

  .marker[aria-pressed='true'] {
    background: #e8f0fe;
    color: #1a73e8;
  }

  .marker-icon {
    display: inline-flex;
    width: 18px;
    height: 18px;
    flex-shrink: 0;
  }

  .marker-icon :global(svg) {
    width: 100%;
    height: 100%;
  }

  .marker-icon--origin {
    color: #1a73e8;
  }

  .marker-label {
    font-size: 0.75rem;
    color: #444;
    white-space: nowrap;
  }

  .marker-icon--place {
    color: #d93025;
  }

  .divider {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0 0.25rem;
  }

  .drag-handle {
    color: #999;
    cursor: grab;
    font-size: 0.9rem;
    letter-spacing: 2px;
  }

  .divider-line {
    flex: 1;
    height: 1px;
    background: #e0e0e0;
  }

  .divider-actions {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    margin-left: auto;
  }

  .action-btn {
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
    padding: 0.25rem 0.4rem;
    border-radius: 6px;
    color: #555;
  }

  .action-btn:hover {
    background: #f1f3f4;
  }
</style>
