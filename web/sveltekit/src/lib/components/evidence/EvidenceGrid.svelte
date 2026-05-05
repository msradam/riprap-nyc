<script lang="ts">
  import type { EvidenceItem } from '$lib/types/evidence';
  import type { Tier } from '$lib/types/tier';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
  import EvidenceCard from './EvidenceCard.svelte';

  interface Props { items: EvidenceItem[]; }
  let { items }: Props = $props();

  function tally(t: Tier) {
    return items.filter((e) => e.tier === t).length;
  }
</script>

<section class="evidence-grid" aria-label="Evidence cards">
  <div class="evidence-grid-head">
    <span class="section-label">Evidence · {items.length} cards</span>
    <span class="evidence-grid-meta">
      <span class="evidence-grid-tally"><TierGlyph tier="empirical" size={9} /> {tally('empirical')}</span>
      <span class="evidence-grid-tally"><TierGlyph tier="modeled" size={9} /> {tally('modeled')}</span>
      <span class="evidence-grid-tally"><TierGlyph tier="proxy" size={9} /> {tally('proxy')}</span>
      <span class="evidence-grid-tally"><TierGlyph tier="synthetic" size={9} /> {tally('synthetic')}</span>
    </span>
  </div>
  <div class="evidence-grid-rail">
    {#each items as ev (ev.id)}
      <EvidenceCard {ev} />
    {/each}
  </div>
</section>
