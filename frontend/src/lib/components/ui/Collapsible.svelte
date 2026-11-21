<script lang="ts">
  import { createEventDispatcher } from 'svelte'

  export let title = ''
  export let open = false

  const dispatch = createEventDispatcher<{ toggle: boolean }>()

  $: isOpen = open

  function toggle() {
    open = !open
    dispatch('toggle', open)
  }
</script>

<div class="rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800">
  <button
    type="button"
    class="flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm font-semibold text-slate-900 hover:bg-slate-100 dark:text-slate-100 dark:hover:bg-slate-700"
    aria-expanded={isOpen}
    on:click={toggle}
  >
    <span>{title}</span>
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      class="h-4 w-4 shrink-0 text-slate-500 transition-transform duration-200 {isOpen
        ? 'rotate-180'
        : ''}"
      aria-hidden="true"
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  </button>
  {#if isOpen}
    <div class="border-t border-slate-200 px-4 py-3 dark:border-slate-700">
      <slot />
    </div>
  {/if}
</div>
