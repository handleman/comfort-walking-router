<script lang="ts">
  /**
   * Arrival summary card (spec 014-walk-guidance-ux, task T9, AC-6/AC-7):
   * shown when the walk enters the 25 m arrival radius (spec 007
   * `ARRIVAL_RADIUS_M`). Reports the walked distance, duration and a
   * 0-100 comfort score. Later micro-steps add top factors and the
   * dismiss / plan-another actions.
   */

  /** Distance walked to the destination, in meters. */
  export let distanceMeters: number

  /** Total walk duration, in minutes. */
  export let durationMinutes: number

  /** Comfort score for the walk, 0-100. */
  export let comfortScore: number

  /** Short labels for the factors that contributed most to the comfort score. */
  export let topFactors: string[] = []

  /** Called when the user dismisses the card. */
  export let onDismiss: () => void = () => {}

  /** Called when the user asks to plan another walk. */
  export let onPlanAnother: () => void = () => {}

  /** Human-readable distance: km with one decimal past 1 km, rounded meters below. */
  $: distanceLabel =
    distanceMeters >= 1000
      ? `${(distanceMeters / 1000).toFixed(1)} km`
      : `${Math.round(distanceMeters)} m`
</script>

<div class="arrival-card" role="status" aria-live="polite" aria-label="Arrived at destination">
  <h2>You've arrived</h2>
  <dl>
    <div class="stat">
      <dt>Distance</dt>
      <dd>{distanceLabel}</dd>
    </div>
    <div class="stat">
      <dt>Duration</dt>
      <dd>{Math.round(durationMinutes)} min</dd>
    </div>
    <div class="stat">
      <dt>Comfort</dt>
      <dd>{Math.round(comfortScore)}/100</dd>
    </div>
  </dl>
  {#if topFactors.length > 0}
    <h3>Top factors</h3>
    <ul class="factors">
      {#each topFactors as factor, index (index)}
        <li>{factor}</li>
      {/each}
    </ul>
  {/if}
  <div class="actions">
    <button type="button" on:click={onDismiss}>Dismiss</button>
    <button type="button" on:click={onPlanAnother}>Plan another walk</button>
  </div>
</div>

<style>
  .arrival-card {
    background: #fff;
    border: 1px solid #ccc;
    border-radius: 8px;
    padding: 0.75rem 1rem;
  }
  .arrival-card h2 {
    margin: 0 0 0.5rem;
    font-size: 1.1rem;
  }
  .arrival-card dl {
    display: flex;
    gap: 1.25rem;
    margin: 0;
  }
  .stat dt {
    font-size: 0.75rem;
    color: #555;
  }
  .stat dd {
    margin: 0;
    font-weight: 600;
  }
  .factors {
    margin: 0.5rem 0 0;
    padding-left: 1.25rem;
  }
  .actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.75rem;
  }
</style>
