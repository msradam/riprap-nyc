<script lang="ts">
  /** v0.4.5 §"Landing page" — Five Stones strip. 5-column grid, one
   *  cell per Stone, oversized italic-serif numerals 01..05 top-right
   *  of each cell (in --rule-soft, decorative). Stone tints applied as
   *  a 3px left-rule per cell to mirror the Findings region. */

  type Frieze = {
    name: string;
    role: string;
    tag: string;
    sources: string;
    tint: string;
  };

  // Hazard- and city-agnostic taglines. Each Stone names a class of
  // evidence; the concrete data sources vary by deployment (NYC ships
  // 23 pebbles, Boston ships 4, etc.). The examples below are
  // categories, not exhaustive lists, so they hold across every
  // active deployment.
  const STONE_FRIEZE: Frieze[] = [
    { name: 'Cornerstone', role: 'the hazard reader',  tag: 'what the ground remembers',     sources: 'Historical inundation extents · FEMA NFHL flood panels · LiDAR microtopography · published high-water marks', tint: 'var(--stone-cornerstone)' },
    { name: 'Keystone',    role: 'the asset register', tag: "what's exposed",                sources: 'Transit entrances · public housing · schools · hospitals · whatever asset registers a jurisdiction publishes',  tint: 'var(--stone-keystone)' },
    { name: 'Touchstone',  role: 'the live observer',  tag: "what's happening now",          sources: 'Real-time street-flood sensors · 311 service requests · NWS hourly observations · NOAA tide gauges',           tint: 'var(--stone-touchstone)' },
    { name: 'Lodestone',   role: 'the projector',      tag: "what's coming",                 sources: 'Sea-level rise projections · time-series surge forecasts · 311 recurrence forecasts · NWS active alerts',         tint: 'var(--stone-lodestone)' },
    { name: 'Capstone',    role: 'the synthesizer',    tag: 'writes the cited briefing',     sources: 'IBM Granite 4.1 reconciler · Mellea rejection sampling · 13-predicate compliance audit',                          tint: 'var(--stone-capstone)' },
  ];
</script>

<section class="land-section-stones-detail" id="methodology">
  <div class="land-page">
    <div class="land-section-head">
      <span class="section-label">How Riprap reads a place</span>
      <span class="land-section-meta">Five Stones · one taxonomy · every briefing</span>
    </div>
    <p class="land-stones-deck">
      Each briefing routes through a fixed taxonomy of public-record specialists. Each Stone is a class of evidence.
      Together they form the briefing, and every claim in the output traces back to the Stone that produced it.
    </p>
    <div class="land-stones-detail">
      {#each STONE_FRIEZE as s, i (s.name)}
        <article class="land-stones-detail-cell" style:--stone-tint={s.tint}>
          <div class="land-stones-detail-num">{String(i + 1).padStart(2, '0')}</div>
          <h3 class="land-stones-detail-name">{s.name}</h3>
          <div class="land-stones-detail-role">{s.role}</div>
          <p class="land-stones-detail-tag">{s.tag}</p>
          <div class="land-stones-detail-sources">{s.sources}</div>
        </article>
      {/each}
    </div>
  </div>
</section>

<style>
  .land-section-stones-detail {
    background: var(--paper-deep);
    padding: 56px 32px;
    border-top: 1px solid var(--rule-soft);
  }
  .land-page { max-width: 1200px; margin: 0 auto; }
  .land-section-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 16px;
    margin-bottom: 22px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--rule-soft);
  }
  .land-section-meta {
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 14px;
    color: var(--ink-tertiary);
  }
  .land-stones-deck {
    font-family: var(--font-serif);
    font-size: 17px;
    line-height: 1.6;
    color: var(--ink-secondary);
    max-width: 70ch;
    margin: 0 0 22px;
  }
  .land-stones-detail {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 0;
    background: white;
    border: 1px solid var(--rule-soft);
    border-bottom: 2px solid var(--ink);
  }
  .land-stones-detail-cell {
    position: relative;
    padding: 28px 18px 22px;
    border-right: 1px solid var(--rule-soft);
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow: hidden;
    border-left: 3px solid var(--stone-tint, var(--rule-soft));
  }
  .land-stones-detail-cell:last-child { border-right: none; }
  .land-stones-detail-num {
    position: absolute;
    top: 6px;
    right: 10px;
    font-family: var(--font-serif);
    font-style: italic;
    font-weight: 400;
    font-size: 38px;
    line-height: 1;
    color: var(--rule-soft);
    letter-spacing: -0.02em;
    pointer-events: none;
  }
  .land-stones-detail-name {
    font-family: var(--font-serif);
    font-size: 22px;
    font-weight: 500;
    margin: 0;
    color: var(--ink);
  }
  .land-stones-detail-role {
    font-family: var(--font-sans);
    font-size: 13px;
    color: var(--ink-secondary);
  }
  .land-stones-detail-tag {
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 14px;
    color: var(--ink-tertiary);
    margin: 0 0 6px;
    line-height: 1.45;
  }
  .land-stones-detail-sources {
    margin-top: auto;
    padding-top: 10px;
    border-top: 1px dashed var(--rule-soft);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-secondary);
    line-height: 1.55;
  }
  @media (max-width: 880px) {
    .land-stones-detail { grid-template-columns: 1fr; }
    .land-stones-detail-cell {
      border-right: none;
      border-bottom: 1px solid var(--rule-soft);
    }
    .land-stones-detail-cell:last-child { border-bottom: none; }
  }
</style>
