<script lang="ts">
  import type { Tier } from '$lib/types/tier';
  import { TIER_META } from '$lib/types/tier';
  import TierGlyph from './TierGlyph.svelte';

  interface Props {
    tier: Tier;
    compact?: boolean;
  }

  let { tier, compact = false }: Props = $props();
  let meta = $derived(TIER_META[tier]);
</script>

<span
  class="tier-badge tier-badge-{tier}"
  title={meta.desc}
  style:color="var(--tier-{tier})"
>
  <TierGlyph {tier} size={10} color="var(--tier-{tier})" />
  {compact ? meta.short : meta.label}
</span>

<style>
  .tier-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 500;
  }
</style>
