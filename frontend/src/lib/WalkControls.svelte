<script lang="ts">
  /**
   * Walk-mode controls (spec 007, T6): Start/Stop buttons driving
   * walkMode.start/stop and the auto-center follow toggle (AC-1, AC-6).
   */
  import { autoCenter, start, stop, walkMode } from './walkMode'
  import type { LatLng } from './navigation/interpolate'

  /** Route to walk; Start is disabled until a route is provided. */
  export let route: LatLng[] = []
</script>

<div class="walk-controls">
  <button
    type="button"
    class="walk-start"
    on:click={() => start(route)}
    disabled={$walkMode.active || route.length === 0}
  >
    Start
  </button>
  <button type="button" class="walk-stop" on:click={() => stop()} disabled={!$walkMode.active}>
    Stop
  </button>
  <label class="walk-auto-center">
    <input type="checkbox" bind:checked={$autoCenter} />
    Auto-center
  </label>
</div>

<style>
  .walk-controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
</style>
