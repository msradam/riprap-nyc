<script lang="ts">
  import type { Card } from '$lib/types/card';
  import RasterThumb from './RasterThumb.svelte';
  let { card }: { card: Card } = $props();
</script>

<div class="body body-raster">
  <div class="frame">
    <RasterThumb kind={card.rasterKind} />
    {#if card.illustrative || card.tier === 'synthetic'}
      <span class="illustrative" title="Illustrative rendering, not source pixels">illustrative</span>
    {/if}
  </div>
  {#if card.headline}
    <div class="raster-headline">
      <span style="color: var(--tier-{card.tier});">{card.headline}</span>
      {#if card.subhead}<span> · {card.subhead}</span>{/if}
    </div>
  {/if}
  {#if card.sub}<div class="body-sub">{card.sub}</div>{/if}
</div>

<style>
  .body-raster { padding: var(--s-2) var(--s-4) var(--s-3); display: flex; flex-direction: column; gap: var(--s-2); }
  :global(.fc.is-compact) .body-raster { padding: var(--s-2) var(--s-3); }
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
  .raster-headline {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--ink);
  }
  .raster-headline span:first-child {
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 18px;
    font-weight: 500;
  }
  .body-sub {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    line-height: 1.5;
  }
</style>
