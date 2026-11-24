<script lang="ts">
  // Collapsed-by-default bottom drawer shell for mobile controls.
  // Renders whatever controls content is passed in via the default slot.
  import { slide } from 'svelte/transition'
  import { materialPaths } from '../map/material'

  let open = false

  function toggle() {
    open = !open
  }
</script>

<div class="bottom-drawer" data-open={open} data-testid="drawer">
  <button
    type="button"
    class="grab-handle"
    data-testid="drawer-handle"
    aria-expanded={open}
    aria-controls="bottom-drawer-body"
    aria-label={open ? 'Collapse controls' : 'Expand controls'}
    on:click={toggle}
  >
    <span class="pill" aria-hidden="true">
      <span class="pill-bar"></span>
      <svg viewBox="0 0 24 24" fill="currentColor"
        ><path d={open ? materialPaths.close : materialPaths.expand_more} /></svg
      >
    </span>
  </button>

  {#if open}
    <div
      class="drawer-body"
      id="bottom-drawer-body"
      role="region"
      aria-label="Route controls"
      transition:slide={{ duration: 200 }}
    >
      <!-- Slot contract: exactly one <ControlsContent /> (the shared controls
           used by the desktop sidebar). No inline controls here. -->
      <slot />
    </div>
  {/if}
</div>

<style>
  .bottom-drawer {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 40;
    background: var(--surface, #fff);
    border-top: 1px solid var(--border, #e2e8f0);
    border-radius: 16px 16px 0 0;
    box-shadow: 0 -4px 16px rgb(0 0 0 / 0.08);
  }

  .grab-handle {
    display: flex;
    justify-content: center;
    width: 100%;
    padding: 8px 0;
    background: transparent;
    border: none;
    cursor: pointer;
  }

  .pill {
    display: inline-flex;
    width: 24px;
    height: 24px;
    color: var(--muted, #94a3b8);
  }

  .pill {
    position: relative;
  }

  .pill :global(svg) {
    width: 100%;
    height: 100%;
  }

  /* Edge-handle bar: the visible affordance that the pill is draggable/clickable. */
  .pill-bar {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 32px;
    height: 4px;
    border-radius: 2px;
    background: var(--muted, #94a3b8);
  }

  .drawer-body {
    max-height: 70vh;
    overflow-y: auto;
    padding: 0 16px 16px;
  }
</style>
