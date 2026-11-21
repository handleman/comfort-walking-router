<script lang="ts">
  import type { HTMLButtonAttributes } from 'svelte/elements'

  type Variant = 'default' | 'outline' | 'ghost' | 'destructive'
  type Size = 'sm' | 'md' | 'lg' | 'icon'

  export let variant: Variant = 'default'
  export let size: Size = 'md'
  export let type: HTMLButtonAttributes['type'] = 'button'
  export let disabled = false
  export let href: string | undefined = undefined

  const variantClasses: Record<Variant, string> = {
    default: 'bg-slate-900 text-white hover:bg-slate-700',
    outline: 'border border-slate-300 bg-transparent text-slate-900 hover:bg-slate-100',
    ghost: 'bg-transparent text-slate-900 hover:bg-slate-100',
    destructive: 'bg-red-600 text-white hover:bg-red-500',
  }

  const sizeClasses: Record<Size, string> = {
    sm: 'h-8 px-3 text-xs',
    md: 'h-10 px-4 text-sm',
    lg: 'h-12 px-6 text-base',
    icon: 'h-10 w-10 p-0',
  }

  $: classes = [
    'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2',
    'disabled:pointer-events-none disabled:opacity-50',
    variantClasses[variant],
    sizeClasses[size],
  ].join(' ')
</script>

{#if href !== undefined}
  <a
    {href}
    class={classes}
    aria-disabled={disabled}
    class:pointer-events-none={disabled}
    class:opacity-50={disabled}
  >
    <slot />
  </a>
{:else}
  <button {type} class={classes} {disabled}>
    <slot />
  </button>
{/if}
