<script lang="ts">
  /**
   * TopSearchCard (spec 040, task T1, AC-1/AC-2):
   * Presentational two-row card floating over the map. Row 1 is the
   * origin (blue my-location dot + "My location" label), row 2 is the
   * destination (red pin marker). A drag-handle divider sits between
   * the rows, and `⋯` / `↑↓` action icons live on the right. Each row
   * hosts the existing SearchInput combobox, keeping the ⌖ pick
   * buttons and the search placeholder text.
   */
  import { createEventDispatcher } from 'svelte'
  import SearchInput from './SearchInput.svelte'
  import type { Suggestion } from '../search/suggestions'
  import type { PickRole } from '../map/picker'

  /** Origin query text; bindable so the host form stays in sync. */
  export let startQuery = ''
  /** Destination query text; bindable so the host form stays in sync. */
  export let endQuery = ''
  /** Selected origin suggestion; bindable. */
  export let startSelected: Suggestion | null = null
  /** Selected destination suggestion; bindable. */
  export let endSelected: Suggestion | null = null
  /** Currently active map-pick role, mirrored for the ⌖ buttons. */
  export let activePick: PickRole | null = null

  /** Base URL forwarded to the SearchInput suggestion fetcher. */
  export let baseUrl = ''

  /** Extra classes forwarded to the host element (e.g. positioning). */
  export let extraClass: string = ''

  /** Dispatched when the user clicks a ⌖ pick button. */
  const dispatch = createEventDispatcher<{
    pick: PickRole
    swap: void
    more: void
  }>()

  function beginPick(role: PickRole): void {
    dispatch('pick', role)
  }
</script>

<div class="top-search-card {extraClass}" role="group" aria-label="Route search">
  <div class="row row-origin">
    <span class="marker marker-origin" aria-hidden="true">
      <span class="dot"></span>
      <span class="marker-label">My location</span>
    </span>
    <span class="pick-row">
      <SearchInput
        {baseUrl}
        placeholder="e.g. Marienplatz, Munich"
        required
        bind:query={startQuery}
        bind:selected={startSelected}
      />
      <button
        type="button"
        class="pick-btn"
        aria-pressed={activePick === 'start'}
        aria-label="Pick start on map"
        on:click={() => beginPick('start')}>⌖</button
      >
    </span>
  </div>

  <div class="divider" role="separator" aria-label="Drag to reorder">
    <span class="drag-handle" aria-hidden="true">⠿</span>
    <span class="divider-actions">
      <button
        type="button"
        class="action-btn"
        aria-label="More options"
        on:click={() => dispatch('more', undefined)}>⋯</button
      >
      <button
        type="button"
        class="action-btn"
        aria-label="Swap origin and destination"
        on:click={() => dispatch('swap', undefined)}>↑↓</button
      >
    </span>
  </div>

  <div class="row row-destination">
    <span class="marker marker-destination" aria-hidden="true">
      <span class="pin">📍</span>
    </span>
    <span class="pick-row">
      <SearchInput
        {baseUrl}
        placeholder="e.g. Englischer Garten"
        required
        bind:query={endQuery}
        bind:selected={endSelected}
      />
      <button
        type="button"
        class="pick-btn"
        aria-pressed={activePick === 'end'}
        aria-label="Pick end on map"
        on:click={() => beginPick('end')}>⌖</button
      >
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
  }

  .marker-origin .dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #1a73e8;
    border: 2px solid #fff;
    box-shadow: 0 0 0 2px #1a73e8;
  }

  .marker-label {
    font-size: 0.75rem;
    color: #444;
    white-space: nowrap;
  }

  .marker-destination .pin {
    font-size: 1rem;
    line-height: 1;
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

  .divider-actions {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    margin-left: auto;
  }

  .action-btn,
  .pick-btn {
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
    padding: 0.25rem 0.4rem;
    border-radius: 6px;
    color: #555;
  }

  .action-btn:hover,
  .pick-btn:hover {
    background: #f1f3f4;
  }

  .pick-btn[aria-pressed='true'] {
    background: #e8f0fe;
    color: #1a73e8;
  }
</style>
