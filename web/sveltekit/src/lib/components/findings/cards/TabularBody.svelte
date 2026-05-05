<script lang="ts">
  import type { Card } from '$lib/types/card';
  let { card }: { card: Card } = $props();
</script>

<div class="body body-tabular">
  <table class="t">
    <thead>
      <tr>
        {#each card.columns ?? [] as h}<th>{h}</th>{/each}
      </tr>
    </thead>
    <tbody>
      {#each card.rows ?? [] as row}
        <tr>{#each row as cell}<td>{cell}</td>{/each}</tr>
      {/each}
    </tbody>
  </table>
  {#if card.sub}<div class="body-sub">{card.sub}</div>{/if}
</div>

<style>
  .body-tabular { padding: var(--s-2) var(--s-4) var(--s-3); }
  :global(.fc.is-compact) .body-tabular { padding: var(--s-2) var(--s-3); }
  .t {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-mono);
    font-size: 12px;
  }
  .t th {
    text-align: left;
    font-weight: 500;
    color: var(--ink-tertiary);
    padding: 4px 8px 4px 0;
    border-bottom: 1px solid var(--rule-soft);
    text-transform: lowercase;
    letter-spacing: 0.04em;
  }
  .t td {
    padding: 4px 8px 4px 0;
    border-bottom: 1px solid var(--rule-soft);
    color: var(--ink);
  }
  .t tr:last-child td { border-bottom: 0; }
  :global(.fc.is-compact) .t th,
  :global(.fc.is-compact) .t td { padding: 2px 6px 2px 0; font-size: 11px; }
  .body-sub {
    margin-top: var(--s-2);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    line-height: 1.5;
  }
</style>
