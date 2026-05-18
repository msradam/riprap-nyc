<script lang="ts">
  import type { Card, Density, ProvenanceMode, StoneKey, StoneTrace } from '$lib/types/card';
  import { STONE_META, STONE_ORDER } from '$lib/types/card';
  import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';
  import FindingCard from './FindingCard.svelte';
  import StoneTally from './StoneTally.svelte';
  import ProvenanceTrace from './ProvenanceTrace.svelte';

  /** A Stone group: header (serif italic name + role · tag · run-tally),
   *  card grid, smart provenance toggle. */
  interface Props {
    stone: StoneKey;
    cards: Card[];
    trace: StoneTrace;
    density?: Density;
    provenanceMode?: ProvenanceMode;
    linkedKey?: string | null;
    onCite?: (citeId: string) => void;
    onLink?: (key: string | null) => void;
  }

  let {
    stone,
    cards,
    trace,
    density = 'comfortable',
    provenanceMode = 'smart',
    linkedKey = null,
    onCite,
    onLink,
  }: Props = $props();

  let meta = $derived(STONE_META[stone]);
  // The deployment's stones.yaml `description` is the city-specific
  // tagline ("Reads what Boston remembers about flooding…"). Fall back
  // to the hardcoded NYC-flavoured STONE_META tag only if the manifest
  // hasn't loaded yet — that keeps the per-query chip honest instead
  // of saying "what NYC's ground remembers" under a Boston chip.
  let manifestStone = $derived(
    pebbleManifest.stones.find((s) => s.id === stone)
  );
  let tagText = $derived(manifestStone?.description || meta.tag);
  let stoneNum = $derived(`${STONE_ORDER.indexOf(stone) + 1}`.padStart(2, '0'));
  let isCapstone = $derived(stone === 'capstone');

  function flatten(ms: StoneTrace['members']): StoneTrace['members'] {
    return ms.flatMap((m) => (m.children ? [m, ...flatten(m.children)] : [m]));
  }
  let flat = $derived(flatten(trace.members));
  let traceCount = $derived(flat.length);
  // v0.4.5: smart-expand when any specialist warned, errored, or was
  // not_invoked. silent_by_design is normal operation, not an anomaly,
  // so it doesn't trigger the auto-expand. The "anomaly" tag itself
  // (v0.4.4) is dropped — the per-stone count chips carry the same
  // info without the redundant label (V0.4.5_SPEC.md §6).
  let hasInterestingState = $derived(
    flat.some((m) => m.status === 'warned' || m.status === 'errored' || m.status === 'not_invoked')
  );
  let smartOpen = $derived(
    provenanceMode === 'all-expanded' ? true :
    provenanceMode === 'all-collapsed' ? false :
    hasInterestingState
  );

  let userOpen = $state<boolean | null>(null);
  let traceOpen = $derived(userOpen ?? smartOpen);

  // Reset user override when the mode changes.
  $effect(() => {
    provenanceMode;
    userOpen = null;
  });
</script>

<section class="region region-{stone}" aria-labelledby={`region-h-${stone}`} data-stone={stone}>
  <header class="region-head">
    <div class="region-head-left">
      <span class="region-num">{stoneNum}</span>
      <h3 id={`region-h-${stone}`} class="region-name">{meta.name}</h3>
      <span class="region-role">· {meta.role}</span>
      <span class="region-tag">{tagText}</span>
    </div>
    <StoneTally cardCount={cards.length} members={trace.members} />
  </header>

  {#if cards.length === 0}
    <div class="silent">
      <span class="silent-tag">silent</span>
      <p class="silent-prose">
        {#if stone === 'lodestone'}
          No projection cards landed for this query. Atomic functions still ran (see provenance) and returned silence rather than confabulation.
        {:else}
          No cards for this Stone on this query.
        {/if}
      </p>
    </div>
  {:else}
    <div class="rail" class:rail-capstone={isCapstone}>
      {#each cards as card (card.id)}
        <FindingCard
          {card}
          {density}
          {linkedKey}
          {onCite}
          {onLink}
        />
      {/each}
    </div>
  {/if}

  <div class="prov">
    <button
      type="button"
      class="prov-toggle"
      aria-expanded={traceOpen}
      aria-controls={`prov-body-${stone}`}
      onclick={() => (userOpen = !traceOpen)}
    >
      <span class="prov-caret" aria-hidden="true">{traceOpen ? '▾' : '▸'}</span>
      <span class="prov-label">{traceOpen ? 'Hide' : 'Show'} provenance</span>
      <span class="prov-meta">
        · {traceCount} function{traceCount === 1 ? '' : 's'}
      </span>
    </button>
    {#if traceOpen}
      <div id={`prov-body-${stone}`} class="prov-body">
        <ProvenanceTrace members={trace.members} />
      </div>
    {/if}
  </div>
</section>

<style>
  .region {
    border-top: 1px solid var(--rule-soft);
    padding: var(--s-5) 0 var(--s-5);
    background: transparent;
  }
  .region:first-of-type { border-top: 0; }

  /* v0.4.5 §9 — Stone-tinted accent: 3px left-rule on the header strip,
     keyed to the Stone's accent token. Hint-level decoration; the
     four-tier palette inside cards is the load-bearing epistemic
     signal. Print degrades to #999 via the tokens.css override. */
  .region-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--s-4);
    margin-bottom: var(--s-3);
    flex-wrap: wrap;
    border-left: 3px solid var(--stone-tint, var(--rule-soft));
    padding-left: var(--s-3);
  }
  .region-cornerstone .region-head { --stone-tint: var(--stone-cornerstone); }
  .region-keystone    .region-head { --stone-tint: var(--stone-keystone); }
  .region-touchstone  .region-head { --stone-tint: var(--stone-touchstone); }
  .region-lodestone   .region-head { --stone-tint: var(--stone-lodestone); }
  .region-capstone    .region-head { --stone-tint: var(--stone-capstone); }
  .region-head-left {
    display: flex;
    align-items: baseline;
    gap: var(--s-2);
    flex-wrap: wrap;
  }
  .region-num {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    letter-spacing: 0.1em;
  }
  .region-name {
    margin: 0;
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 26px;
    font-weight: 500;
    color: var(--ink);
    letter-spacing: -0.005em;
    line-height: 1.1;
  }
  .region-role {
    font-family: var(--font-sans);
    font-size: 14px;
    color: var(--ink-secondary);
  }
  .region-tag {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    letter-spacing: 0.05em;
    margin-left: var(--s-2);
  }
  .rail {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: var(--s-3);
  }
  .rail :global(> .fc) { grid-column: span 4; }
  .rail :global(> .fc.fc-register),
  .rail :global(> .fc.fc-timeseries),
  .rail :global(> .fc.fc-timeseries-ft),
  .rail :global(> .fc.fc-forecast),
  .rail :global(> .fc.fc-raster),
  .rail :global(> .fc.fc-raster-pred),
  .rail :global(> .fc.fc-lulc),
  .rail :global(> .fc.fc-comparison) {
    grid-column: span 6;
  }
  .rail-capstone :global(> .fc) { grid-column: span 6; }
  @media (max-width: 920px) {
    .rail { grid-template-columns: repeat(6, 1fr); }
    .rail :global(> .fc) { grid-column: span 6; }
  }

  .silent {
    border: 1px dashed var(--rule-soft);
    padding: var(--s-4);
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
    background: var(--paper-deep);
  }
  .silent-tag {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--ink-tertiary);
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }
  .silent-prose {
    margin: 0;
    font-size: 13px;
    color: var(--ink-secondary);
    line-height: 1.5;
    max-width: var(--measure);
  }

  .prov { margin-top: var(--s-3); }
  .prov-toggle {
    background: transparent;
    border: 0;
    padding: 4px 0;
    cursor: pointer;
    display: inline-flex;
    align-items: baseline;
    gap: var(--s-1);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-secondary);
    letter-spacing: 0.05em;
  }
  .prov-toggle:hover { color: var(--ink); }
  .prov-caret { font-size: 10px; color: var(--ink-tertiary); }
  .prov-meta { color: var(--ink-tertiary); }
  .prov-body {
    margin-top: var(--s-2);
    padding: var(--s-2) 0;
    border-top: 1px solid var(--rule-soft);
    border-bottom: 1px solid var(--rule-soft);
  }
</style>
