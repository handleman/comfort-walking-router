<script lang="ts">
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

  /** Human-readable off-route distance, e.g. "42 m" or "1.2 km". */
  $: distanceLabel =
    distanceMeters >= 1000
      ? `${(distanceMeters / 1000).toFixed(1)} km`
      : `${Math.round(distanceMeters)} m`
</script>

<div class="reroute-warning" role="alert">
  <span class="reroute-text">Off route — reroute? ({distanceLabel} off route)</span>
  <button type="button" class="reroute-accept" on:click={onReroute}>Reroute</button>
  <button type="button" class="reroute-dismiss" on:click={onDismiss}>Dismiss</button>
</div>

<style>
  .reroute-warning {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
</style>
