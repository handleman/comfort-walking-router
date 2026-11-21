<script lang="ts">
  import type { HTMLButtonAttributes } from 'svelte/elements';

  type Variant = 'default' | 'outline' | 'ghost' | 'destructive';
  type Size = 'default' | 'sm' | 'lg' | 'icon';

  export let variant: Variant = 'default';
  export let size: Size = 'default';
  export let type: HTMLButtonAttributes['type'] = 'button';

  const variantClasses: Record<Variant, string> = {
    default: 'bg-sky-600 text-white hover:bg-sky-700 focus-visible:ring-sky-500',
    outline:
      'border border-slate-300 bg-transparent text-slate-800 hover:bg-slate-100 focus-visible:ring-slate-400',
    ghost: 'bg-transparent text-slate-800 hover:bg-slate-100 focus-visible:ring-slate-400',
    destructive: 'bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-500'
  };

  const sizeClasses: Record<Size, string> = {
    default: 'h-9 px-4 py-2 text-sm',
    sm: 'h-8 px-3 text-xs',
    lg: 'h-10 px-6 text-base',
    icon: 'h-9 w-9 p-0'
  };

  $: classes = [
    'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
    'disabled:pointer-events-none disabled:opacity-50',
    variantClasses[variant],
    sizeClasses[size]
  ].join(' ');
</script>

<button {...$$restProps} {type} class="{classes} {$$restProps.class ?? ''}">
  <slot />
</button>
