<script lang="ts">
  export let title = ''
  export let padded = true
</script>

<div
  class="rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800"
>
  {#if title}
    <h3
      class="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-900 dark:border-slate-700 dark:text-slate-100"
    >
      {title}
    </h3>
  {/if}
  <div class={padded ? 'p-4' : ''}>
    <slot />
  </div>
</div>
