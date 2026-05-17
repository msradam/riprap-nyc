<script lang="ts">
  /** UseBand — Responsible-use disclaimer.
   *
   *  Pairs the federal civic-tech evidence-not-advice pattern with the
   *  explicit non-affiliation note required by Plain Writing Act voice.
   *  Left border is amber-800 to cue "warning register" without going
   *  red.
   *
   *  Aria-label declares this as a Responsible-use region for screen
   *  readers — the heading-as-paragraph pattern is deliberate so the
   *  page's heading-outline stays semantic.
   */
</script>

<aside class="use-band" aria-label="Responsible use">
  <p class="use-band-head">Riprap returns evidence, not advice.</p>
  <div class="use-band-body">
    <p style="margin:0;">
      Riprap composes public-record data into a written briefing. It does not
      predict damage to specific properties or substitute for professional
      engineering judgment. For personal property decisions, contact your
      local resilience office or hazard-mitigation program.
    </p>
    <p class="use-band-affil">
      Independent open-source project. Not affiliated with FEMA, NOAA, USGS,
      or any city government. Data is used under each source's open-data
      terms.
    </p>
  </div>
</aside>

<style>
  .use-band {
    display: grid;
    grid-template-columns: minmax(0, 220px) minmax(0, 1fr);
    gap: 22px;
    margin-top: 28px;
    padding: 16px 22px;
    background: white;
    border: 1px solid var(--rule-soft);
    border-left: 3px solid var(--accent-warn);
    align-items: start;
  }
  .use-band-head {
    font-family: var(--font-sans);
    font-size: 14px;
    font-weight: 600;
    color: var(--ink);
    margin: 0;
    line-height: 1.4;
    letter-spacing: 0.01em;
  }
  .use-band-body {
    font-family: var(--font-sans);
    font-size: 13px;
    line-height: 1.55;
    color: var(--ink-secondary);
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .use-band-body a {
    color: var(--accent);
    border-bottom: 1px solid var(--accent);
    text-decoration: none;
  }
  .use-band-affil {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    letter-spacing: 0.02em;
    padding-top: 6px;
    border-top: 1px dashed var(--rule-soft);
    margin: 0;
  }
  @media (max-width: 720px) {
    .use-band { grid-template-columns: 1fr; gap: 12px; }
  }
</style>
