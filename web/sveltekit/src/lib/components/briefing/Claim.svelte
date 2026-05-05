<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { Tier } from '$lib/types/tier';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';

  interface Props { tier: Tier; children: Snippet; }
  let { tier, children }: Props = $props();
</script>

<span class="claim claim-{tier}" data-tier={tier}>
  <span class="claim-glyph" aria-hidden="false">
    <TierGlyph {tier} size={11} color="var(--tier-{tier})" />
  </span>
  <span class="claim-body">{@render children()}</span>
</span>
