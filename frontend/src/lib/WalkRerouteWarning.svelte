<script lang="ts">
  import type { RerouteVerdict } from './navigation/rerouteChoice'
  /**
   * Off-route warning banner (spec 007, task T7, AC-4/AC-5).
   *
   * Rendered while walk mode is active and drift detection has flagged the
   * device as off route. Shows the off-route distance and offers Reroute
   * (invokes `onReroute`) and Dismiss (invokes `onDismiss`) actions.
   */
  /** Distance in meters from the route to display in the banner. */
  export let distanceMeters = 0
  /** Invoked by the Reroute button. */
  export let onReroute: () => void = () => {}
  /** Invoked by the Dismiss button. */
  export let onDismiss: () => void = () => {}
  /** Comfort delta of the alternative route (meters), if compared. */
  export let delta: number | null = null
  /** Remaining distance on the current route (km), if known. */
  export let remainingKm: number | null = null
  /** Comparison verdict ('keep' | 'reroute'), if a comparison ran. */
  export let verdict: RerouteVerdict | null = null

  /** Human-readable off-route distance, e.g. "42 m" or "1.2 km". */
  $: distanceLabel =
    distanceMeters >= 1000
      ? `${(distanceMeters / 1000).toFixed(1)} km`
      : `${Math.round(distanceMeters)} m`

  /** Trade summary, e.g. "Off route — reroute? +120 comfort · 3.4 km left". */
  $: tradeLabel =
    delta !== null && remainingKm !== null
      ? `Off route — reroute? ${delta !== null && delta >= 0 ? '+' : '−'}${Math.abs(delta).toFixed(
          1,
        )} comfort · ${remainingKm.toFixed(1)} km left`
      : null
</script>

<div class="reroute-warning" role="alert">
  {#if tradeLabel !== null}<span class="reroute-text">{tradeLabel}</span>{:else}<span
      class="reroute-text">Off route — reroute? ({distanceLabel} off route)</span
    >{/if}
  {#if verdict === 'keep'}<button type="button" class="reroute-dismiss" on:click={onDismiss}
      >Stay on this route</button
    >{:else}<button type="button" class="reroute-accept" on:click={onReroute}>Reroute</button
    ><button type="button" class="reroute-dismiss" on:click={onDismiss}>Dismiss</button>{/if}
</div>

<style>
  .reroute-warning {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
</style>
