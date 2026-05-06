<script lang="ts">
  /**
   * Asset-pin glyphs for the four register specialists. Match the
   * MapLibre asset-pin layer shapes so the table row and the map dot
   * read as the same thing (per v0.4.2 §15).
   *
   *   subway   → filled square
   *   nycha    → open square
   *   school   → cross (plus sign)
   *   hospital → filled circle
   */
  import type { AssetKind } from '$lib/types/states';

  interface Props {
    kind: AssetKind;
    size?: number;
    color?: string;
  }

  let { kind, size = 12, color = '#0F172A' }: Props = $props();
  let half = $derived(size / 2);
</script>

<svg width={size} height={size} viewBox="0 0 {size} {size}" aria-hidden="true">
  {#if kind === 'subway'}
    <rect x="0" y="0" width={size} height={size} fill={color} />
  {:else if kind === 'nycha'}
    <rect x="1" y="1" width={size - 2} height={size - 2} fill="none" stroke={color} stroke-width="1.5" />
  {:else if kind === 'school'}
    <line x1="0" y1={half} x2={size} y2={half} stroke={color} stroke-width="2" />
    <line x1={half} y1="0" x2={half} y2={size} stroke={color} stroke-width="2" />
  {:else}
    <circle cx={half} cy={half} r={half - 0.5} fill={color} />
  {/if}
</svg>
