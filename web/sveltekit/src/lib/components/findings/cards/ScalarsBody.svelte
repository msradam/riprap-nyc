<script lang="ts">
  import type { Card } from '$lib/types/card';
  let { card }: { card: Card } = $props();
</script>

<div class="body body-scalars">
  <div class="row">
    {#each card.scalars ?? [] as s}
      <div class="cell">
        <div class="value" style="color: var(--tier-{card.tier});">{s.value}</div>
        <div class="label">{s.label}</div>
      </div>
    {/each}
  </div>
  {#if card.sub}<div class="body-sub">{card.sub}</div>{/if}
</div>

<style>
  .body-scalars { padding: var(--s-3) var(--s-4) var(--s-3); }
  :global(.fc.is-compact) .body-scalars { padding: var(--s-2) var(--s-3); }
  .row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
    gap: var(--s-3);
  }
  .cell { display: flex; flex-direction: column; gap: 2px; }
  .value {
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 22px;
    font-weight: 500;
    line-height: 1.1;
  }
  .label {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--ink-tertiary);
    letter-spacing: 0.06em;
    text-transform: lowercase;
  }
  .body-sub {
    margin-top: var(--s-3);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    line-height: 1.5;
  }
</style>
