<script lang="ts">
  import type { Tier } from '$lib/types/tier';

  interface Props {
    tier: Tier;
    size?: number;
    color?: string;
    title?: string;
  }

  let { tier, size = 12, color = 'currentColor', title }: Props = $props();

  const TIER_DESC: Record<Tier, string> = {
    empirical: 'Empirical: directly measured or observed',
    modeled: 'Modeled: scenario-based prediction',
    proxy: 'Proxy: indirect indicator',
    synthetic: 'Synthetic prior: generated, not observed'
  };

  let stroke = $derived(Math.max(1, Math.round(size / 9)));
  let label = $derived(title ?? TIER_DESC[tier]);
  let patternId = $derived(`rip-stripe-${tier}-${size}`);
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 {size} {size}"
  role="img"
  aria-label={label}
  style="flex: none; display: inline-block; vertical-align: -0.12em;"
>
  <title>{label}</title>
  {#if tier === 'empirical'}
    <rect x="0" y="0" width={size} height={size} fill={color} />
  {:else if tier === 'modeled'}
    <rect
      x={stroke / 2}
      y={stroke / 2}
      width={size - stroke}
      height={size - stroke}
      fill="none"
      stroke={color}
      stroke-width={stroke}
    />
  {:else if tier === 'proxy'}
    <circle cx={size / 2} cy={size / 2} r={size / 2 - 0.5} fill={color} />
  {:else}
    <defs>
      <pattern
        id={patternId}
        width="3"
        height="3"
        patternUnits="userSpaceOnUse"
        patternTransform="rotate(45)"
      >
        <line x1="0" y1="0" x2="0" y2="3" stroke={color} stroke-width="1.5" />
      </pattern>
    </defs>
    <rect
      x={stroke / 2}
      y={stroke / 2}
      width={size - stroke}
      height={size - stroke}
      fill="url(#{patternId})"
      stroke={color}
      stroke-width={stroke}
    />
  {/if}
</svg>
