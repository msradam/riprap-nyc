<script lang="ts">
  import type { Card } from '$lib/types/card';
  import RasterThumb from './RasterThumb.svelte';
  let { card }: { card: Card } = $props();

  /** v0.4.5 §4 — TerraMind LULC card body.
   *
   *  Raster thumbnail + horizontal stacked class-mix bar showing
   *  percentage by LULC class. The bar uses the conventional LULC
   *  palette (urban / water / vegetation / barren / wetland) — those
   *  are visual conventions for the layer itself, NOT new tier
   *  signals. The four-tier palette stays load-bearing inside the
   *  card chrome. */

  let total = $derived((card.classMix ?? []).reduce((acc, c) => acc + (c.pct || 0), 0) || 1);
</script>

<div class="body body-lulc">
  <div class="frame">
    <RasterThumb kind={card.rasterKind ?? 'lulc'} />
    {#if card.illustrative || card.tier === 'synthetic'}
      <span class="illustrative" title="Illustrative rendering, not source pixels">illustrative</span>
    {/if}
  </div>

  {#if card.classMix?.length}
    <div class="bar" role="img" aria-label="LULC class mix">
      {#each card.classMix as c (c.k)}
        <span
          class="bar-seg"
          style:flex-grow={c.pct / total}
          style:background={c.color}
          title="{c.k}: {c.pct}%"
        ></span>
      {/each}
    </div>
    <ul class="legend">
      {#each card.classMix as c (c.k)}
        <li>
          <span class="swatch" style:background={c.color}></span>
          <span class="legend-k">{c.k}</span>
          <span class="legend-pct">{c.pct}%</span>
        </li>
      {/each}
    </ul>
  {/if}

  {#if card.sub}<div class="body-sub">{card.sub}</div>{/if}
</div>

<style>
  .body-lulc {
    padding: var(--s-2) var(--s-4) var(--s-3);
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }
  :global(.fc.is-compact) .body-lulc { padding: var(--s-2) var(--s-3); }
  .frame { position: relative; border: 1px solid var(--rule-soft); }
  .illustrative {
    position: absolute;
    top: 6px;
    right: 6px;
    background: rgba(26, 26, 26, 0.7);
    color: var(--paper);
    font-family: var(--font-mono);
    font-size: 9px;
    padding: 2px 6px;
    letter-spacing: 0.05em;
    text-transform: lowercase;
  }
  .bar {
    display: flex;
    height: 10px;
    border: 1px solid var(--rule-soft);
    overflow: hidden;
  }
  .bar-seg {
    flex-shrink: 1;
    flex-basis: 0;
  }
  .legend {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
    gap: 4px var(--s-3);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
  }
  .legend li {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .swatch {
    display: inline-block;
    width: 10px;
    height: 10px;
    border: 1px solid var(--rule-soft);
    flex: none;
  }
  .legend-k {
    color: var(--ink);
    text-transform: lowercase;
    letter-spacing: 0.04em;
  }
  .legend-pct { color: var(--ink-tertiary); }
  .body-sub {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    line-height: 1.5;
  }
</style>
