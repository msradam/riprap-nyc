<script lang="ts">
  import type {
    Card, Density, FindingsData, ProvenanceMode, StoneKey, StoneTrace
  } from '$lib/types/card';
  import { STONE_ORDER } from '$lib/types/card';
  import RunHealthStrip from './RunHealthStrip.svelte';
  import StoneRegion from './StoneRegion.svelte';
  import CardGrammarReference from './CardGrammarReference.svelte';

  /** Findings region: 5 Stones in canonical order, top-banner run-health
   *  strip, optional dev-only card-grammar catalog. linkedKey is owned by
   *  the parent route (`q/[queryId]/+page.svelte` or `q/sample/+page.svelte`)
   *  so the briefing's map can read it without a store. */
  interface Props {
    data: FindingsData;
    density?: Density;
    provenanceMode?: ProvenanceMode;
    showGrammar?: boolean;
    linkedKey?: string | null;
    onCite?: (citeId: string) => void;
    onLink?: (key: string | null) => void;
  }

  let {
    data,
    density = 'comfortable',
    provenanceMode = 'smart',
    showGrammar = false,
    linkedKey = null,
    onCite,
    onLink,
  }: Props = $props();

  // Index cards by Stone, keep order from `data.cards`.
  let cardsByStone = $derived.by<Record<StoneKey, Card[]>>(() => {
    const out: Record<StoneKey, Card[]> = {
      cornerstone: [], keystone: [], touchstone: [], lodestone: [], capstone: [],
    };
    for (const c of data.cards) out[c.stone].push(c);
    return out;
  });

  // Index traces by Stone with safe defaults so a missing Stone still
  // renders an empty region rather than crashing.
  let tracesByStone = $derived.by<Record<StoneKey, StoneTrace>>(() => {
    const out: Record<StoneKey, StoneTrace> = {
      cornerstone: { key: 'cornerstone', members: [] },
      keystone:    { key: 'keystone', members: [] },
      touchstone:  { key: 'touchstone', members: [] },
      lodestone:   { key: 'lodestone', members: [] },
      capstone:    { key: 'capstone', members: [] },
    };
    for (const t of data.stones) out[t.key] = t;
    return out;
  });
</script>

<section class="findings" aria-label="Findings, grouped by Stone">
  <header class="findings-head">
    <h2 class="findings-h2">Findings · grouped by Stone</h2>
    <span class="findings-tagline">cards = what each Stone found · provenance collapses below</span>
  </header>

  <RunHealthStrip
    cards={data.cards}
    stones={data.stones}
    wallSeconds={data.wallSeconds}
    cacheHit={data.cacheHit}
    emissions={data.emissions}
  />

  {#each STONE_ORDER as key (key)}
    <StoneRegion
      stone={key}
      cards={cardsByStone[key]}
      trace={tracesByStone[key]}
      {density}
      {provenanceMode}
      {linkedKey}
      {onCite}
      {onLink}
    />
  {/each}

  {#if showGrammar}
    <CardGrammarReference {density} />
  {/if}
</section>

<style>
  .findings {
    background: var(--paper);
    color: var(--ink);
  }
  .findings-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--s-3);
    padding: var(--s-3) 0 var(--s-2);
  }
  .findings-h2 {
    margin: 0;
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 22px;
    font-weight: 500;
    color: var(--ink);
  }
  .findings-tagline {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    letter-spacing: 0.05em;
  }
</style>
