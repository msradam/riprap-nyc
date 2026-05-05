<script lang="ts">
  import type { Card } from '$lib/types/card';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
  let { card }: { card: Card } = $props();
</script>

<div class="body body-comparison">
  <div class="cmp-grid">
    {#if card.left}
      <div class="cell">
        <div class="cell-tier">
          <TierGlyph tier={card.left.tier} size={10} color="var(--tier-{card.left.tier})" />
          <span class="cell-label">{card.left.label}</span>
        </div>
        <div class="cell-value" style="color: var(--tier-{card.left.tier});">{card.left.value}</div>
        {#if card.left.aux}<div class="cell-aux">{card.left.aux}</div>{/if}
      </div>
    {/if}
    <div class="divider" aria-hidden="true">vs</div>
    {#if card.right}
      <div class="cell">
        <div class="cell-tier">
          <TierGlyph tier={card.right.tier} size={10} color="var(--tier-{card.right.tier})" />
          <span class="cell-label">{card.right.label}</span>
        </div>
        <div class="cell-value" style="color: var(--tier-{card.right.tier});">{card.right.value}</div>
        {#if card.right.aux}<div class="cell-aux">{card.right.aux}</div>{/if}
      </div>
    {/if}
  </div>
  {#if card.delta}<div class="cmp-delta">{card.delta}</div>{/if}
  {#if card.sub}<div class="body-sub">{card.sub}</div>{/if}
</div>

<style>
  .body-comparison {
    padding: var(--s-3) var(--s-4) var(--s-3);
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }
  :global(.fc.is-compact) .body-comparison { padding: var(--s-2) var(--s-3); }
  .cmp-grid {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    gap: var(--s-3);
    align-items: stretch;
  }
  .cell { display: flex; flex-direction: column; gap: 4px; }
  .cell-tier {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--ink-tertiary);
    letter-spacing: 0.05em;
    text-transform: lowercase;
  }
  .cell-value {
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 22px;
    font-weight: 500;
  }
  .cell-aux {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--ink-tertiary);
  }
  .divider {
    align-self: center;
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 14px;
    color: var(--ink-tertiary);
    padding-top: 18px;
  }
  .cmp-delta {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink);
    border-top: 1px solid var(--rule-soft);
    padding-top: var(--s-2);
  }
  .body-sub {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    line-height: 1.5;
  }
</style>
