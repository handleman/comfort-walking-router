<script lang="ts">
  /**
   * StartLocationModal (spec 040, task T18, AC-5):
   * Shown when geolocation is unavailable or denied on start (no fix
   * after the request). Asks for the start location via a text field
   * wired to the existing suggestion search (SearchInput) plus a
   * "Pick on map" action that arms the existing `start` map-pick.
   * The modal closes once an origin is chosen (typed suggestion or
   * map pick) and never blocks the rest of the page.
   */
  import { createEventDispatcher } from 'svelte'
  import SearchInput from './SearchInput.svelte'
  import type { Suggestion } from '../search/suggestions'
  import type { PickRole } from '../map/picker'

  /** Base URL forwarded one-way to the SearchInput suggestion fetcher. */
  export let baseUrl = ''

  /** Whether the modal is visible; two-way bound with the host page. */
  export let open = false

  /** Selected start suggestion; two-way bound with the host page. */
  export let selected: Suggestion | null = null

  const dispatch = createEventDispatcher<{
    chosen: Suggestion
    pick: PickRole
    close: void
  }>()

  function onChosen(suggestion: Suggestion): void {
    dispatch('chosen', suggestion)
    open = false
  }

  // A typed suggestion chosen in the SearchInput closes the modal (AC-5).
  $: if (open && selected) onChosen(selected)
  // Clear a stale selection when (re)opening so it doesn't instantly re-close.
  $: if (!open && selected) selected = null

  function onPick(): void {
    dispatch('pick', 'start')
    open = false
  }

  function onClose(): void {
    dispatch('close')
    open = false
  }

  // Escape dismisses the modal; it never blocks the rest of the page (AC-5).
  function onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && open) onClose()
  }
</script>

<svelte:window on:keydown={onKeydown} />

{#if open}
  <div class="start-modal-backdrop" role="presentation">
    <div class="start-modal" role="dialog" aria-modal="false" aria-label="Choose start location">
      <h2 class="start-modal-title">Where do you want to start?</h2>
      <p class="start-modal-hint">
        We couldn't get your location. Search for a start point or pick it on the map.
      </p>
      <SearchInput {baseUrl} placeholder="e.g. Marienplatz, Munich" required bind:selected />
      <div class="start-modal-actions">
        <button type="button" class="start-modal-pick" on:click={onPick}> Pick on map </button>
        <button type="button" class="start-modal-dismiss" on:click={onClose}> Not now </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .start-modal-backdrop {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: 4rem 1rem 1rem;
    background: rgba(0, 0, 0, 0.25);
    pointer-events: none;
    z-index: 1000;
  }
  .start-modal {
    pointer-events: auto;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    padding: 1rem;
    max-width: 22rem;
    width: 100%;
  }
  .start-modal-title {
    margin: 0 0 0.25rem;
    font-size: 1rem;
  }
  .start-modal-hint {
    margin: 0 0 0.75rem;
    font-size: 0.85rem;
    color: #555;
  }
  .start-modal-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.75rem;
  }
  .start-modal-pick,
  .start-modal-dismiss {
    flex: 1;
    padding: 0.5rem 0.75rem;
    border-radius: 8px;
    border: 1px solid #ccc;
    background: #fff;
    cursor: pointer;
    font-size: 0.9rem;
  }
  .start-modal-pick {
    background: #1a73e8;
    border-color: #1a73e8;
    color: #fff;
  }
</style>
