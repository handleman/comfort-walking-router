<script lang="ts">
  /**
   * Attribution display (spec 014, T10, AC-8/AC-9): shows the required
   * provider credit wherever a suggestion/route is displayed.
   * Renders nothing when `text` is empty.
   */
  export let text: string

  const isMapbox = text.toLowerCase().includes('mapbox')
</script>

{#if text !== ''}
  <p class="attribution" role="note">
    {#if isMapbox}
      © <a href="https://www.mapbox.com/about/maps/" target="_blank" rel="noopener noreferrer"
        >Mapbox</a
      >
      ©
      <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer"
        >OpenStreetMap</a
      >
    {:else}
      © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer"
        >OpenStreetMap</a
      > contributors
    {/if}
  </p>
{/if}

<style>
  .attribution {
    font-size: 0.75rem;
    color: var(--color-muted, #6b7280);
    margin: 0;
  }
</style>
