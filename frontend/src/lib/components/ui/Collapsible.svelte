<script lang="ts">
  export let title: string;
  export let open = false;
  export let class: string = '';

  let expanded = open;
</script>

<div class="rounded-card border border-border bg-surface {className}">
  <button
    type="button"
    class="flex w-full items-center justify-between gap-2 rounded-card px-md py-sm text-sm font-medium text-text hover:bg-surface/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
    aria-expanded={expanded}
    onclick={() => (expanded = !expanded)}
  >
    <span>{title}</span>
    <span
      class="text-text-muted transition-transform duration-200 {expanded ? 'rotate-180' : ''}"
      aria-hidden="true"
    >
      ▾
    </span>
  </button>
  {#if expanded}
    <div class="px-md pb-md pt-xs text-sm text-text-muted">
      {@render children?.()}
    </div>
  {/if}
</div>
