<script lang="ts">
  import type { Card } from '$lib/types/card';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';

  /** Hover-linking comes from the parent `FindingCard` chrome (which is
   *  itself a button when card.mapLayer is set) — it sets `linkedKey`
   *  on pointerenter / focus / keydown, so the map's `is-link-…` /
   *  outline + badge fires for the whole register card.
   *
   *  v0.4.5 §8 click-to-fitBounds() per-row is a documented follow-up:
   *  it requires plumbing a MapLibre handle through FindingsRegion →
   *  StoneRegion → FindingCard → here, plus a register-points feature
   *  index keyed by sourceId. Out of scope for this polish pass. */
  let { card }: { card: Card } = $props();
</script>

<div class="body body-register">
  <ul class="reg-list">
    {#each card.registers ?? [] as r}
      <li class="reg-row" class:silent={!r.label}>
        <span class="reg-tag" title={r.tier}>
          <TierGlyph tier={r.tier} size={9} color="var(--tier-{r.tier})" />
          <span>{r.reg}</span>
        </span>
        {#if r.label}
          <span class="reg-label" title={r.detail ? `${r.label} — ${r.detail}` : r.label}>{r.label}</span>
          <span class="reg-source">{r.sourceId ?? ''}</span>
        {:else}
          <span class="reg-silent">{r.note}</span>
        {/if}
      </li>
    {/each}
  </ul>
  {#if card.sub}<div class="body-sub">{card.sub}</div>{/if}
</div>

<style>
  .body-register { padding: var(--s-2) var(--s-4) var(--s-3); }
  :global(.fc.is-compact) .body-register { padding: var(--s-2) var(--s-3); }
  .reg-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
  }
  .reg-row {
    display: grid;
    grid-template-columns: 70px 1fr auto;
    gap: var(--s-2);
    align-items: baseline;
    padding: 5px 0;
    border-bottom: 1px solid var(--rule-soft);
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.4;
  }
  .reg-row:last-child { border-bottom: 0; }
  :global(.fc.is-compact) .reg-row { padding: 3px 0; font-size: 11px; }
  .reg-tag {
    display: inline-flex;
    gap: 4px;
    align-items: center;
    color: var(--ink-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 500;
  }
  .reg-label {
    color: var(--ink);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .reg-source {
    color: var(--ink-tertiary);
    font-size: 10px;
    letter-spacing: 0.05em;
  }
  .reg-silent {
    grid-column: 2 / span 2;
    color: var(--ink-tertiary);
    font-style: italic;
  }
  .reg-row.silent { opacity: 0.65; }
  .body-sub {
    margin-top: var(--s-2);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    line-height: 1.5;
  }
</style>
