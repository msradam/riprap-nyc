<script lang="ts">
  import type { Card } from '$lib/types/card';
  let { card }: { card: Card } = $props();
</script>

<div class="body body-headline">
  <div class="headline" style="color: var(--tier-{card.tier});">{card.headline ?? ''}</div>
  {#if card.subhead}<div class="subhead">{card.subhead}</div>{/if}
  {#if card.body}<p class="body-prose">{card.body}</p>{/if}
</div>

<style>
  .body-headline {
    padding: var(--s-3) var(--s-4) var(--s-2);
    display: flex;
    flex-direction: column;
    gap: var(--s-1);
  }
  :global(.fc.is-compact) .body-headline { padding: var(--s-2) var(--s-3); }
  .headline {
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 28px;
    font-weight: 500;
    line-height: 1.1;
    letter-spacing: -0.01em;
  }
  :global(.fc.is-compact) .headline { font-size: 22px; }
  .subhead {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    letter-spacing: 0.04em;
  }
  .body-prose {
    margin: var(--s-2) 0 0;
    font-size: 13px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
</style>
