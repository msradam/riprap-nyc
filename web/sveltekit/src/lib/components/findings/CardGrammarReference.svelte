<script lang="ts">
  import type { Card, Density } from '$lib/types/card';
  import FindingCard from './FindingCard.svelte';

  /** Dev-only catalog of all 12 card variants. Gated on import.meta.env.DEV
   *  + ?grammar=1 in the page URL. Useful for spot-checking visual fidelity
   *  while iterating on the variant components. */
  let { density = 'comfortable' as Density }: { density?: Density } = $props();

  // One stub per variant. Mirrors findings.jsx GRAMMAR_STUBS.
  const STUBS: Card[] = [
    {
      id: 'grm-headline', stone: 'cornerstone', tier: 'modeled', variant: 'headline',
      source: 'FEMA', agency: 'spec', vintage: 'spec',
      title: 'Single big number, scenario-tagged',
      headline: 'Zone AE', subhead: 'preliminary FIRM, panel ID',
      sub: 'Use when the answer is one categorical state.',
      docId: 'DS-HEADLINE',
    },
    {
      id: 'grm-tabular', stone: 'cornerstone', tier: 'empirical', variant: 'tabular',
      source: 'USGS', agency: 'spec', vintage: 'spec',
      title: 'Small table of observations',
      columns: ['id', 'value', 'dist.'],
      rows: [
        ['ROW-001', '1.2 m', '0.18 mi'],
        ['ROW-002', '0.9 m', '0.32 mi'],
        ['ROW-003', '0.7 m', '0.41 mi'],
      ],
      sub: 'Use when 3–8 records each carry the same fields.',
      docId: 'DS-TABULAR',
    },
    {
      id: 'grm-scalars', stone: 'touchstone', tier: 'empirical', variant: 'scalars',
      source: 'NWS', agency: 'spec', vintage: 'spec',
      title: 'Trio of scalar readings',
      scalars: [
        { value: '0.02 in', label: 'precip · 24h' },
        { value: '11 mph', label: 'wind' },
        { value: '63°F', label: 'temp' },
      ],
      sub: 'Use for current-state dashboards.',
      docId: 'DS-SCALARS',
    },
    {
      id: 'grm-spark', stone: 'touchstone', tier: 'empirical', variant: 'spark',
      source: 'FloodNet', agency: 'spec', vintage: 'spec',
      title: 'Sparkline of recent events',
      headline: 'n events', subhead: 'window · peak',
      spark: [1, 2, 4, 3, 7, 12, 8, 5, 3, 2, 4, 9, 6],
      docId: 'DS-SPARK',
    },
    {
      id: 'grm-histogram', stone: 'touchstone', tier: 'proxy', variant: 'histogram',
      source: 'NYC 311', agency: 'spec', vintage: 'spec',
      title: 'Histogram of binned counts',
      headline: 'n calls', subhead: 'window · seasonal note',
      histogram: [3, 2, 1, 0, 1, 4, 7, 12, 18, 11, 5, 3, 4, 2, 1, 0, 2, 3, 8, 9, 4, 2, 1, 0],
      docId: 'DS-HIST',
    },
    {
      id: 'grm-timeseries', stone: 'lodestone', tier: 'modeled', variant: 'timeseries',
      source: 'Granite TTM', agency: 'spec', vintage: 'spec',
      title: 'Forecast curve with horizon',
      headline: '+0.41 m peak', subhead: '+38h · 90% CI',
      timeseries: { hours: 96, peak: { x: 38, y: 41 }, peakLabel: '+0.41 m' },
      spatialNote: 'regional',
      sub: 'Spatial-index callout when station ≠ point-of-query.',
      docId: 'DS-TS',
    },
    {
      id: 'grm-forecast', stone: 'lodestone', tier: 'modeled', variant: 'forecast',
      source: 'NPCC4', agency: 'spec', vintage: 'spec',
      title: 'Long-horizon scenario projections',
      forecast: [
        { year: 2030, low: 4, mid: 6, high: 9 },
        { year: 2050, low: 13, mid: 22, high: 30 },
        { year: 2100, low: 38, mid: 71, high: 114 },
      ],
      sub: 'Use for decadal+ uncertainty cones.',
      docId: 'DS-FCST',
    },
    {
      id: 'grm-raster', stone: 'cornerstone', tier: 'modeled', variant: 'raster',
      source: 'NYC DEP', agency: 'spec', vintage: 'spec',
      title: 'Raster snapshot, mapped layer',
      rasterKind: 'stormwater',
      headline: 'ponding', subhead: 'scenario · pixel summary',
      sub: 'Use for any 2D model output.',
      docId: 'DS-RASTER',
    },
    {
      id: 'grm-rasterpred', stone: 'touchstone', tier: 'modeled', variant: 'raster-pred',
      source: 'Prithvi-NYC', agency: 'spec', vintage: 'spec',
      title: 'Raster prediction, illustrative',
      rasterKind: 'prithvi',
      headline: 'n% flooded', subhead: 'model · scene id',
      illustrative: true,
      sub: 'Same chrome as raster + illustrative tag.',
      docId: 'DS-RASTERPRED',
    },
    {
      id: 'grm-register', stone: 'keystone', tier: 'empirical', variant: 'register',
      source: 'NYC OpenData', agency: 'spec', vintage: 'spec',
      title: 'Composite register list',
      registers: [
        { reg: 'MTA', tier: 'empirical', label: 'Station entrance', detail: '0.18 mi · 5', sourceId: 'MTA-X', note: null },
        { reg: 'NYCHA', tier: 'empirical', label: 'Development', detail: '0.41 mi · 2,878 res.', sourceId: 'NYCHA-Y', note: null },
        { reg: 'DOH', tier: 'empirical', label: null, detail: null, sourceId: null, note: 'no acute-care hospital within 1.0 mi' },
      ],
      sub: 'Use when many specialists join into one Stone.',
      docId: 'DS-REGISTER',
    },
    {
      id: 'grm-comparison', stone: 'keystone', tier: 'synthetic', variant: 'comparison',
      source: 'EMP × SYN', agency: 'spec', vintage: 'spec',
      title: 'Documented vs. interpreted',
      left: { tier: 'empirical', label: 'documented', value: '31.4%', aux: 'n polygons' },
      right: { tier: 'synthetic', label: 'interpreted', value: '29.8%', aux: 'n polygons' },
      delta: 'Δ = −1.6 pp · agreement strong',
      sub: 'Use to surface model–ground-truth deltas.',
      docId: 'DS-CMP',
    },
    {
      id: 'grm-meta', stone: 'capstone', tier: 'modeled', variant: 'meta',
      source: 'Mellea', agency: 'spec', vintage: 'spec',
      title: 'Capstone reconciliation',
      metaRows: [
        { k: 'claims', v: '12 / 12 grounded' },
        { k: 'tier mix', v: 'EMP 5 · MOD 4 · PRX 2 · SYN 1' },
        { k: 'tier-1 freshness', v: 'median 38 d' },
        { k: 'warnings', v: '0' },
      ],
      sub: "Use to expose the synthesis layer's audit.",
      docId: 'DS-META',
    },
  ];
</script>

<section class="region region-grammar" aria-label="Card grammar reference">
  <header class="region-head">
    <div class="region-head-left">
      <span class="region-num">SPEC</span>
      <h3 class="region-name">Card grammar</h3>
      <span class="region-role">· every body variant in the system</span>
      <span class="region-tag">stubs, not findings</span>
    </div>
    <span class="grammar-count">{STUBS.length} variants</span>
  </header>
  <div class="rail">
    {#each STUBS as stub (stub.id)}
      <FindingCard card={stub} {density} />
    {/each}
  </div>
</section>

<style>
  .region-grammar {
    border-top: 2px solid var(--ink);
    padding: var(--s-5) 0;
  }
  .region-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    flex-wrap: wrap;
    gap: var(--s-3);
    margin-bottom: var(--s-3);
  }
  .region-head-left {
    display: flex;
    align-items: baseline;
    gap: var(--s-2);
    flex-wrap: wrap;
  }
  .region-num {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    letter-spacing: 0.1em;
  }
  .region-name {
    margin: 0;
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 22px;
    font-weight: 500;
  }
  .region-role {
    font-family: var(--font-sans);
    font-size: 13px;
    color: var(--ink-secondary);
  }
  .region-tag {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    letter-spacing: 0.05em;
  }
  .grammar-count {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
  }
  .rail {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: var(--s-3);
  }
  .rail :global(> .fc) { grid-column: span 4; }
  .rail :global(> .fc.fc-register),
  .rail :global(> .fc.fc-timeseries),
  .rail :global(> .fc.fc-forecast),
  .rail :global(> .fc.fc-raster),
  .rail :global(> .fc.fc-raster-pred),
  .rail :global(> .fc.fc-comparison) {
    grid-column: span 6;
  }
  @media (max-width: 920px) {
    .rail { grid-template-columns: repeat(6, 1fr); }
    .rail :global(> .fc) { grid-column: span 6; }
  }
</style>
