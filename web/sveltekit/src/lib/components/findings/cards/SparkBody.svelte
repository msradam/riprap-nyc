<script lang="ts">
  import type { Card } from '$lib/types/card';
  let { card }: { card: Card } = $props();

  /** spark + histogram both render the same shape — bars filling 240×38. */
  const W = 240, H = 38;
  let data = $derived(card.spark ?? card.histogram ?? []);
  let max = $derived(Math.max(...data, 1));
  let n = $derived(data.length);
  let barW = $derived(Math.max(2, W / Math.max(n, 1) - 1.5));
</script>

<div class="body body-spark">
  {#if card.headline}
    <div class="headline" style="color: var(--tier-{card.tier});">{card.headline}</div>
  {/if}
  {#if card.subhead}<div class="subhead">{card.subhead}</div>{/if}
  <svg viewBox="0 0 {W} {H}" width="100%" height={H} preserveAspectRatio="none" aria-hidden="true">
    {#each data as v, i}
      <rect
        x={(i / n) * W + 0.5}
        y={H - (v / max) * H}
        width={barW}
        height={(v / max) * H}
        fill="var(--tier-{card.tier})"
      />
    {/each}
  </svg>
  {#if card.sparkSub}<div class="body-sub">{card.sparkSub}</div>{/if}
  {#if !card.sparkSub && card.sub}<div class="body-sub">{card.sub}</div>{/if}
</div>

<style>
  .body-spark {
    padding: var(--s-3) var(--s-4) var(--s-3);
    display: flex;
    flex-direction: column;
    gap: var(--s-1);
  }
  :global(.fc.is-compact) .body-spark { padding: var(--s-2) var(--s-3); }
  .headline {
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 22px;
    font-weight: 500;
    line-height: 1.1;
  }
  .subhead {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    letter-spacing: 0.04em;
    margin-bottom: var(--s-1);
  }
  svg { display: block; }
  .body-sub {
    margin-top: var(--s-2);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    line-height: 1.5;
  }
</style>
