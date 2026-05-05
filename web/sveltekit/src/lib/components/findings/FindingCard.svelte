<script lang="ts">
  import type { Card, Density } from '$lib/types/card';
  import { TIER_META } from '$lib/types/tier';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
  import CardBody from './cards/CardBody.svelte';

  /** Findings card chrome: header (tier glyph + source + vintage), title,
   *  body (variant dispatch), footer (docId + tier badge + cite arrow).
   *
   *  Synthetic-tier cards get a 1px dashed top-rule (telegraph "no
   *  observed data here"), per the v0.4.4 spec. Comparison and
   *  raster-pred always render synthetic.
   *
   *  Hover linking: card sets `linkedKey` to its `mapLayer` on
   *  pointerenter / focus and clears on pointerleave / blur. The map
   *  reads `linkedKey` and lights up the matching layer.
   */
  interface Props {
    card: Card;
    density?: Density;
    linkedKey?: string | null;
    onCite?: (citeId: string) => void;
    onLink?: (key: string | null) => void;
  }

  let {
    card,
    density = 'comfortable',
    linkedKey = null,
    onCite,
    onLink,
  }: Props = $props();

  let isLinked = $derived(linkedKey != null && card.mapLayer != null && card.mapLayer === linkedKey);
  let tierShort = $derived(TIER_META[card.tier].short);

  let interactive = $derived(card.mapLayer != null);

  function handleEnter() { if (card.mapLayer) onLink?.(card.mapLayer); }
  function handleLeave() { if (card.mapLayer) onLink?.(null); }
  function handleCite(e: Event) {
    e.stopPropagation();
    if (card.citeId) onCite?.(card.citeId);
  }
  function handleKey(e: KeyboardEvent) {
    if (!interactive) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onLink?.(card.mapLayer ?? null);
    }
  }
</script>

<svelte:element
  this={interactive ? 'button' : 'article'}
  type={interactive ? 'button' : undefined}
  role={interactive ? 'button' : 'article'}
  class="fc fc-{card.variant} fc-tier-{card.tier}"
  class:is-compact={density === 'compact'}
  class:is-linked={isLinked}
  class:is-interactive={interactive}
  class:has-illustrative={card.illustrative || card.tier === 'synthetic' || card.variant === 'comparison'}
  aria-labelledby={`fc-${card.id}-title`}
  aria-label={`${TIER_META[card.tier].label} card · ${card.title} · ${card.source}`}
  onpointerenter={handleEnter}
  onpointerleave={handleLeave}
  onfocus={handleEnter}
  onblur={handleLeave}
  onkeydown={handleKey}
>
  <header class="fc-head">
    <div class="fc-head-source">
      <TierGlyph tier={card.tier} size={11} color="var(--tier-{card.tier})" />
      <span class="fc-head-source-label" title={card.agency}>{card.source}</span>
    </div>
    <span class="fc-head-vintage">v. {card.vintage}</span>
  </header>

  <h4 id={`fc-${card.id}-title`} class="fc-title">{card.title}</h4>

  <CardBody {card} />

  <footer class="fc-foot">
    {#if card.citeId}
      <button
        type="button"
        class="fc-foot-cite"
        onclick={handleCite}
        title={`Open ${card.docId} in citation drawer`}
      >
        <span class="fc-foot-docid">{card.docId}</span>
        <span class="fc-foot-arrow" aria-hidden="true">→</span>
      </button>
    {:else}
      <span class="fc-foot-docid fc-foot-docid-mute">{card.docId}</span>
    {/if}
    <span class="fc-tier-badge fc-tier-badge-{card.tier}" aria-label={`epistemic tier ${tierShort}`}>
      <TierGlyph tier={card.tier} size={9} color="var(--tier-{card.tier})" />
      <span>{tierShort}</span>
    </span>
  </footer>
</svelte:element>

<style>
  .fc {
    background: var(--paper);
    border: 1px solid var(--rule-soft);
    display: flex;
    flex-direction: column;
    transition: background-color 200ms ease, border-color 200ms ease, outline-color 200ms ease;
    outline: 0 solid transparent;
    outline-offset: 0;
    /* When the article is rendered as a button (interactive cards), strip
       the default browser button chrome so it looks like the article. */
    color: inherit;
    text-align: left;
    font: inherit;
    padding: 0;
    width: 100%;
    /* Fade each card in as it lands in the rail. Respects
       prefers-reduced-motion via the global rule in tokens.css. */
    animation: fc-fade-in 360ms ease-out both;
  }
  @keyframes fc-fade-in {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .fc.is-interactive { cursor: pointer; }
  .fc:hover { background: var(--paper-deep); }
  .fc.is-linked {
    outline: 2px solid var(--accent-graphical);
    outline-offset: 0;
  }

  /* Synthetic + comparison + illustrative cards get a dashed top rule. */
  .has-illustrative { border-top: 1px dashed var(--tier-synthetic-line); }
  .fc-tier-synthetic { border-top: 1px dashed var(--tier-synthetic-line); }

  .fc-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--s-2) var(--s-4);
    border-bottom: 1px solid var(--rule-soft);
    background: var(--paper-deep);
  }
  :global(.fc.is-compact) .fc-head { padding: 6px var(--s-3); }
  .fc-head-source {
    display: inline-flex;
    align-items: center;
    gap: var(--s-2);
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ink);
  }
  .fc-head-source-label {
    cursor: help;
  }
  .fc-head-vintage {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--ink-tertiary);
    letter-spacing: 0.05em;
  }

  .fc-title {
    margin: 0;
    padding: var(--s-3) var(--s-4) 0;
    font-family: var(--font-sans);
    font-size: 14px;
    font-weight: 600;
    line-height: 1.35;
    color: var(--ink);
  }
  :global(.fc.is-compact) .fc-title { padding: var(--s-2) var(--s-3) 0; font-size: 13px; }

  .fc-foot {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--s-2) var(--s-4);
    border-top: 1px solid var(--rule-soft);
    background: var(--paper-deep);
    gap: var(--s-3);
    margin-top: auto;
  }
  :global(.fc.is-compact) .fc-foot { padding: 6px var(--s-3); }

  .fc-foot-cite {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: transparent;
    border: 0;
    padding: 0;
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.05em;
    color: var(--accent);
  }
  .fc-foot-cite:hover { color: var(--ink); }
  .fc-foot-docid {
    text-transform: uppercase;
  }
  .fc-foot-docid-mute {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--ink-tertiary);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .fc-foot-arrow {
    font-family: var(--font-mono);
    font-size: 11px;
  }

  .fc-tier-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .fc-tier-badge-empirical { color: var(--tier-empirical); }
  .fc-tier-badge-modeled { color: var(--tier-modeled); }
  .fc-tier-badge-proxy { color: var(--tier-proxy); }
  .fc-tier-badge-synthetic { color: var(--tier-synthetic); }
</style>
