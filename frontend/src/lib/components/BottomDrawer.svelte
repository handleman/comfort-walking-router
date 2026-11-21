<script lang="ts">
  // Collapsed-by-default bottom drawer shell for mobile controls.
  // Renders whatever controls content is passed in via the default slot.
  import { slide } from 'svelte/transition'

  let open = false

  function toggle() {
    open = !open
  }
</script>

<div class="bottom-drawer" data-open={open}>
  <button
    type="button"
    class="grab-handle"
    aria-expanded={open}
    aria-controls="bottom-drawer-body"
    aria-label={open ? 'Collapse controls' : 'Expand controls'}
    on:click={toggle}
  >
    <span class="pill" aria-hidden="true"></span>
  </button>

  {#if open}
    <div class="drawer-body" id="bottom-drawer-body" transition:slide={{ duration: 200 }}>
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
    display: block;
    width: 48px;
    height: 5px;
    border-radius: 9999px;
    background: var(--muted, #94a3b8);
  }

  .drawer-body {
    max-height: 70vh;
    overflow-y: auto;
    padding: 0 16px 16px;
  }
</style>
