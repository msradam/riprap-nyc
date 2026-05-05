<script lang="ts">
  import type { Card } from '$lib/types/card';
  import TimeseriesBody from './TimeseriesBody.svelte';
  let { card }: { card: Card } = $props();

  /** Fine-tuned-model timeseries variant (v0.4.5 §5).
   *
   *  Reuses TimeseriesBody for the chart, then adds a footer chrome
   *  band: HF model-card link, RMSE, "−35% vs persistence" skill chip,
   *  and an AMD MI300X hardware badge. The footer is the load-bearing
   *  AMD-fine-tune narration on the hackathon submission. */
</script>

<TimeseriesBody {card} />
<div class="ft-footer">
  {#if card.rmse}
    <span class="ft-stat"><span class="ft-stat-k">RMSE</span> {card.rmse}</span>
  {/if}
  {#if card.skillVsPersistence}
    <span class="ft-stat ft-skill">{card.skillVsPersistence}</span>
  {/if}
  {#if card.hardwareBadge}
    <span class="ft-badge" title="Trained on this hardware">{card.hardwareBadge}</span>
  {/if}
  {#if card.hfModelCard}
    <a class="ft-link"
       href={card.hfModelCard.startsWith('http') ? card.hfModelCard : `https://${card.hfModelCard}`}
       target="_blank" rel="noopener noreferrer">
      Model card ↗
    </a>
  {/if}
</div>

<style>
  .ft-footer {
    margin: var(--s-2) var(--s-4) var(--s-3);
    padding-top: var(--s-2);
    border-top: 1px dashed var(--rule-soft);
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-3);
    align-items: baseline;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
  }
  :global(.fc.is-compact) .ft-footer { margin: var(--s-2) var(--s-3); }
  .ft-stat {
    display: inline-flex;
    align-items: baseline;
    gap: 4px;
    color: var(--ink);
  }
  .ft-stat-k {
    font-size: 10px;
    color: var(--ink-tertiary);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .ft-skill {
    color: var(--tier-modeled);
    font-weight: 500;
  }
  .ft-badge {
    border: 1px solid var(--ink);
    color: var(--ink);
    padding: 1px 6px;
    font-size: 10px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    background: var(--paper);
  }
  .ft-link {
    margin-left: auto;
    color: var(--accent);
    text-decoration: none;
  }
  .ft-link:hover { text-decoration: underline; }
</style>
