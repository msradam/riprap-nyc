<script lang="ts">
  import type { Card } from '$lib/types/card';
  let { card }: { card: Card } = $props();
</script>

<div class="body body-meta">
  <dl class="meta-list">
    {#each card.metaRows ?? [] as r}
      <div class="meta-row">
        <dt>{r.k}</dt>
        <dd>{r.v}</dd>
      </div>
    {/each}
  </dl>
  {#if card.sub}<div class="body-sub">{card.sub}</div>{/if}
</div>

<style>
  .body-meta { padding: var(--s-2) var(--s-4) var(--s-3); }
  :global(.fc.is-compact) .body-meta { padding: var(--s-2) var(--s-3); }
  .meta-list {
    margin: 0;
    display: grid;
    grid-template-columns: 1fr;
    gap: 4px;
  }
  .meta-row {
    display: grid;
    grid-template-columns: minmax(110px, max-content) 1fr;
    gap: var(--s-3);
    padding: 3px 0;
    border-bottom: 1px solid var(--rule-soft);
    align-items: baseline;
  }
  .meta-row:last-child { border-bottom: 0; }
  dt {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    text-transform: lowercase;
    letter-spacing: 0.04em;
  }
  dd {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--ink);
  }
  .body-sub {
    margin-top: var(--s-2);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    line-height: 1.5;
  }
</style>
