<script lang="ts">
  export let label: string
  export let active = false
</script>

<section class="step" data-step={label} data-active={active}>
  <h2 class="step-label">{label}</h2>
  {#if active}
    <div class="step-body">
      <slot />
    </div>
  {/if}
</section>

<style>
  .step {
    display: block;
  }
  .step-label {
    font-size: 0.875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0 0 0.5rem;
  }
  .step-body {
    display: block;
  }
</style>
