<script lang="ts">
  /** "What you'll get back" three-pane preview: briefing excerpt with
   *  inline citations · 2x2 evidence-card grid · mini SVG map.
   *  Lifted as-is from docs/design_handoff/design_files/Riprap Landing.html. */
</script>

<section class="land-section">
  <div class="land-section-head">
    <span class="section-label">What you'll get back</span>
    <span class="land-section-meta">A grounded paragraph with citations, not a chatbot answer.</span>
  </div>

  <div class="land-preview-grid">

    <!-- Pane 1 — briefing excerpt -->
    <div class="land-preview-pane land-preview-pane-excerpt">
      <div class="land-preview-eyebrow">Briefing excerpt</div>
      <p class="land-preview-body">
        The lot sits inside the FEMA <span class="land-preview-cite">1% AE flood zone <sup>[c3]</sup></span>,
        with Sandy high-water marks recorded
        <span class="land-preview-cite"> 4.7 ft above grade <sup>[c1]</sup></span>.
        FloodNet FN-BK-018 has logged
        <span class="land-preview-cite"> 14 nuisance floods since 2023 <sup>[c2]</sup></span>.
      </p>
      <div class="land-preview-cites">
        <div class="land-preview-cite-row">
          <span class="land-preview-cite-pin">[c1]</span>
          <span class="land-preview-cite-src">USGS HWM · Sandy 2012</span>
          <span class="land-preview-cite-tier">empirical</span>
        </div>
        <div class="land-preview-cite-row">
          <span class="land-preview-cite-pin">[c2]</span>
          <span class="land-preview-cite-src">FloodNet FN-BK-018</span>
          <span class="land-preview-cite-tier">empirical</span>
        </div>
        <div class="land-preview-cite-row">
          <span class="land-preview-cite-pin">[c3]</span>
          <span class="land-preview-cite-src">FEMA NFHL · 36047C0207</span>
          <span class="land-preview-cite-tier">modeled</span>
        </div>
      </div>
    </div>

    <!-- Pane 2 — evidence cards 2x2 -->
    <div class="land-preview-pane land-preview-pane-cards">
      <div class="land-preview-eyebrow">Evidence cards</div>
      <div class="land-evcard-grid">
        <article class="land-evcard land-evcard-empirical">
          <header class="land-evcard-head">
            <span class="land-evcard-tier">empirical</span>
            <span class="land-evcard-id">e1</span>
          </header>
          <div class="land-evcard-claim">4.7 ft Sandy storm-surge HWM at address</div>
          <div class="land-evcard-source">USGS High-Water Mark database · 2012</div>
        </article>
        <article class="land-evcard land-evcard-empirical">
          <header class="land-evcard-head">
            <span class="land-evcard-tier">empirical</span>
            <span class="land-evcard-id">e2</span>
          </header>
          <div class="land-evcard-claim">14 nuisance-flood events, 2023–2026</div>
          <div class="land-evcard-source">FloodNet FN-BK-018 · 2 blocks north</div>
        </article>
        <article class="land-evcard land-evcard-modeled">
          <header class="land-evcard-head">
            <span class="land-evcard-tier">modeled</span>
            <span class="land-evcard-id">e3</span>
          </header>
          <div class="land-evcard-claim">FEMA 1% annual-chance (AE) flood zone</div>
          <div class="land-evcard-source">FEMA NFHL · panel 36047C0207</div>
        </article>
        <article class="land-evcard land-evcard-modeled">
          <header class="land-evcard-head">
            <span class="land-evcard-tier">modeled</span>
            <span class="land-evcard-id">e5</span>
          </header>
          <div class="land-evcard-claim">+30 in MSL by 2070 (NPCC4 high)</div>
          <div class="land-evcard-source">NPCC4 SLR projection · 2024</div>
        </article>
      </div>
    </div>

    <!-- Pane 3 — mini SVG map -->
    <div class="land-preview-pane land-preview-pane-map">
      <div class="land-preview-eyebrow">Map</div>
      <div class="land-mapmini" role="img" aria-label="Sample exposure map of Red Hook">
        <svg viewBox="0 0 240 200" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice"
             style="display: block; width: 100%; height: 100%;">
          <rect width="240" height="200" fill="#F2F2EE" />
          <path d="M0,150 Q60,140 120,148 T240,140 L240,200 L0,200 Z" fill="#D6DDE0" />
          <path d="M0,90 Q40,82 90,88 L120,86 L120,150 L0,150 Z" fill="#D6DDE0" />
          <path d="M30,80 L130,76 L160,140 L40,148 Z"
                fill="rgba(42,111,168,0.22)" stroke="#2A6FA8"
                stroke-width="0.8" stroke-dasharray="3 2" />
          <path d="M50,90 Q90,84 130,90 T200,108"
                fill="none" stroke="#0B5394" stroke-width="1.2" />
          <g stroke="#B8B5AE" stroke-width="0.5" fill="none">
            <path d="M0,60 L240,52" />
            <path d="M0,110 L240,102" />
            <path d="M60,0 L72,200" />
            <path d="M120,0 L132,200" />
            <path d="M180,0 L192,200" />
          </g>
          <g transform="translate(108 92)">
            <rect x="-3" y="-3" width="6" height="6" fill="#0B5394" stroke="white" stroke-width="0.8" />
          </g>
          <g fill="none" stroke="#6B6B6B" stroke-width="0.8">
            <circle cx="80" cy="120" r="3" />
            <circle cx="86" cy="124" r="3" />
            <circle cx="92" cy="118" r="3" />
          </g>
          <g transform="translate(118 112)">
            <circle r="8" fill="none" stroke="#1A1A1A" stroke-width="1.2" />
            <circle r="2.4" fill="#1A1A1A" />
          </g>
        </svg>
        <div class="land-mapmini-legend">
          <span><span class="lm-sw lm-sw-emp"></span>empirical</span>
          <span><span class="lm-sw lm-sw-mod"></span>modeled</span>
          <span><span class="lm-sw lm-sw-prx"></span>proxy</span>
        </div>
      </div>
      <div class="land-preview-mapmeta">Red Hook · z16 · Carto Positron</div>
    </div>

  </div>
</section>

<style>
  .land-section {
    padding: 48px 32px;
    border-top: 1px solid var(--rule-soft);
  }
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

  .land-preview-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 1fr);
    gap: 14px;
    align-items: stretch;
  }
  .land-preview-pane {
    background: white;
    border: 1px solid var(--rule-soft);
    border-left: 3px solid var(--ink);
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-width: 0;
  }
  .land-preview-eyebrow {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ink-tertiary);
    margin: 0;
  }

  /* Excerpt pane */
  .land-preview-pane-excerpt .land-preview-body {
    font-family: var(--font-serif);
    font-size: 15px;
    line-height: 1.55;
    color: var(--ink);
    margin: 0;
  }
  .land-preview-cite {
    background: linear-gradient(transparent 60%, rgba(11, 83, 148, 0.14) 60%);
  }
  .land-preview-cite sup {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--tier-empirical);
    margin-left: 2px;
    vertical-align: super;
  }
  .land-preview-cites {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding-top: 10px;
    border-top: 1px dashed var(--rule-soft);
  }
  .land-preview-cite-row {
    display: grid;
    grid-template-columns: 30px 1fr 70px;
    gap: 8px;
    align-items: baseline;
    font-family: var(--font-mono);
    font-size: 11px;
  }
  .land-preview-cite-pin { color: var(--tier-empirical); font-weight: 600; }
  .land-preview-cite-src { color: var(--ink); }
  .land-preview-cite-tier {
    color: var(--ink-tertiary);
    text-align: right;
    letter-spacing: 0.04em;
  }

  /* Cards pane */
  .land-preview-pane-cards { gap: 8px; }
  .land-evcard-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
    flex: 1;
  }
  .land-evcard {
    background: var(--paper);
    border: 1px solid var(--rule-soft);
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .land-evcard-empirical { border-left: 2px solid var(--tier-empirical); }
  .land-evcard-modeled { border-left: 2px solid var(--tier-modeled); }
  .land-evcard-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.06em;
  }
  .land-evcard-tier { color: var(--ink-secondary); text-transform: uppercase; }
  .land-evcard-empirical .land-evcard-tier { color: var(--tier-empirical); }
  .land-evcard-modeled .land-evcard-tier { color: var(--tier-modeled); }
  .land-evcard-id { color: var(--ink-tertiary); }
  .land-evcard-claim {
    font-family: var(--font-sans);
    font-size: 12.5px;
    line-height: 1.35;
    color: var(--ink);
  }
  .land-evcard-source {
    font-family: var(--font-mono);
    font-size: 10.5px;
    color: var(--ink-tertiary);
  }

  /* Map pane */
  .land-preview-pane-map { padding: 16px 18px; }
  .land-mapmini {
    position: relative;
    aspect-ratio: 6 / 5;
    border: 1px solid var(--rule-soft);
    overflow: hidden;
  }
  .land-mapmini-legend {
    position: absolute;
    left: 6px;
    bottom: 6px;
    right: 6px;
    display: flex;
    gap: 10px;
    padding: 4px 6px;
    background: rgba(255, 255, 255, 0.92);
    font-family: var(--font-mono);
    font-size: 9.5px;
    letter-spacing: 0.04em;
    color: var(--ink-secondary);
  }
  .land-mapmini-legend span {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .lm-sw { display: inline-block; width: 8px; height: 8px; }
  .lm-sw-emp { background: var(--tier-empirical); }
  .lm-sw-mod {
    background: rgba(42, 111, 168, 0.4);
    border: 1px dashed var(--tier-modeled);
  }
  .lm-sw-prx {
    background: transparent;
    border: 1px solid #6B6B6B;
    border-radius: 50%;
  }
  .land-preview-mapmeta {
    font-family: var(--font-mono);
    font-size: 10.5px;
    color: var(--ink-tertiary);
  }

  @media (max-width: 1000px) {
    .land-preview-grid { grid-template-columns: 1fr 1fr; }
    .land-preview-pane-excerpt { grid-column: 1 / -1; }
  }
  @media (max-width: 640px) {
    .land-preview-grid { grid-template-columns: 1fr; }
    .land-preview-pane-excerpt { grid-column: auto; }
  }
</style>
