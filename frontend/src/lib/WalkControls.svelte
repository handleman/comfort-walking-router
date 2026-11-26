<script lang="ts">
  /**
   * Walk-mode controls (spec 007, T6): Start/Stop buttons driving
   * walkMode.start/stop and the auto-center follow toggle (AC-1, AC-6).
   * Renders the off-route reroute warning banner (spec 007, T7, AC-4/AC-5).
   */
  import { autoCenter, dismissRerouteWarning, reroute, start, stop, walkMode } from './walkMode'
  import type { WalkProfile } from './walkMode'
  import WalkRerouteWarning from './WalkRerouteWarning.svelte'
  import WalkArrivedBanner from './WalkArrivedBanner.svelte'
  import type { LatLng } from './navigation/interpolate'

  /** Route to walk; Start is disabled until a route is provided. */
  export let route: LatLng[] = []
  /** Its 028 comfort profile, the baseline for the reroute comparison (029). */
  export let profile: WalkProfile = []
</script>

<div class="walk-controls">
  <button
    type="button"
    class="walk-start"
    data-testid="start-walk"
    aria-label="Start walk mode"
    on:click={() => start(route, profile)}
    disabled={$walkMode.active || route.length === 0}
  >
    Start
  </button>
  <button
    type="button"
    class="walk-stop"
    data-testid="stop-walk"
    aria-label="Stop walk mode"
    on:click={() => stop()}
    disabled={!$walkMode.active && !$walkMode.arrived}
  >
    Stop
  </button>
  <label class="walk-auto-center">
    <input type="checkbox" bind:checked={$autoCenter} aria-label="Auto-center on the walker" />
    Auto-center
  </label>
</div>

{#if $walkMode.arrived}
  <WalkArrivedBanner />
{/if}

{#if $walkMode.rerouteWarning}
  <WalkRerouteWarning
    distanceMeters={$walkMode.offRouteMeters}
    delta={$walkMode.delta ?? null}
    remainingKm={$walkMode.remainingKm ?? null}
    verdict={$walkMode.verdict ?? null}
    onReroute={() => reroute($walkMode.markerPos, $walkMode.destination)}
    onDismiss={() => dismissRerouteWarning()}
  />
{/if}

<style>
  .walk-controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
</style>
