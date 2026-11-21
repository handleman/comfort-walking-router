<script lang="ts">
  import type { HTMLAttributes } from 'svelte/elements';

  export let class: string = '';
</script>

<div class="rounded-card border border-border bg-surface p-md {class}" {...$$restProps as rest}>
  <slot />
</div>
