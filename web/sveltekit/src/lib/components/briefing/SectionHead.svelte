<script lang="ts">
  import type { Tier } from '$lib/types/tier';
  import TierBadge from '$lib/components/glyphs/TierBadge.svelte';

  interface Props { n: string; label: string; tier?: Tier; title?: string; }
  let { n, label, tier, title }: Props = $props();
</script>

<h3 class="briefing-section-head">
  <span class="briefing-section-num">{n}</span>
  <span class="briefing-section-label">{label}</span>
  {#if tier}
    <span class="briefing-section-tier"><TierBadge {tier} compact /></span>
  {/if}
  {#if title}
    <span class="briefing-section-title">{title}</span>
  {/if}
</h3>
