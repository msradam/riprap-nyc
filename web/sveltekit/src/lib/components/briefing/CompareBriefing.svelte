<script lang="ts">
  import Briefing from './Briefing.svelte';
  import { parseBriefing } from '$lib/client/parseBriefing';
  import type { Citation } from '$lib/types/claim';

  interface Target {
    label: string;
    address: string;
  }

  interface Props {
    paragraph: string;
    citations: Record<string, Citation>;
    targets: Target[];
    /** Per-place step result payloads from the agent stream, keyed by step name. */
    structuredA?: Record<string, unknown>;
    structuredB?: Record<string, unknown>;
  }

  let { paragraph, citations, targets, structuredA = {}, structuredB = {} }: Props = $props();

  // Split the merged compare paragraph at the --- divider.
  // Each half begins with `## PLACE A/B: <address>` which we strip to get
  // clean 4-section markdown for parseBriefing.
  function splitParagraph(para: string): { address: string; md: string }[] {
    const halves = para.split(/\n\s*---\s*\n/, 2);
    return halves.map((half, i) => {
      const m = /^##\s+PLACE\s+[AB]:\s+(.+?)(\n|$)/m.exec(half.trim());
      const address = m?.[1]?.trim() ?? targets[i]?.address ?? `Place ${String.fromCharCode(65 + i)}`;
      const md = half.replace(/^##\s+PLACE\s+[AB]:\s+.+(\n|$)/m, '').trim();
      return { address, md };
    });
  }

  const halves = $derived(splitParagraph(paragraph));
  const parsedA = $derived(parseBriefing(halves[0]?.md ?? '', citations));
  const parsedB = $derived(parseBriefing(halves[1]?.md ?? '', citations));

  // Both columns share the merged citation registry so cross-column
  // doc_id numbering stays consistent.
  const allCitations = $derived({
    ...citations,
    ...parsedA.citations,
    ...parsedB.citations
  });

  interface DeltaRow {
    label: string;
    ctx: string;
    aVal: string;
    bVal: string;
  }

  function getNum(steps: Record<string, unknown>, stepName: string, field: string): number | undefined {
    const r = steps[stepName];
    if (!r || typeof r !== 'object') return undefined;
    const v = (r as Record<string, unknown>)[field];
    return typeof v === 'number' ? v : undefined;
  }

  function getBool(steps: Record<string, unknown>, stepName: string, field: string): boolean | undefined {
    const r = steps[stepName];
    if (!r || typeof r !== 'object') return undefined;
    const v = (r as Record<string, unknown>)[field];
    return typeof v === 'boolean' ? v : undefined;
  }

  // Derive diff rows from structured specialist step payloads.
  // This avoids parsing prose for numbers, which incorrectly picks up
  // address street numbers as "Status" comparisons.
  const deltaRows = $derived.by<DeltaRow[]>(() => {
    const rows: DeltaRow[] = [];

    // Sandy inundation zone membership
    const sandyA = getBool(structuredA, 'sandy_inundation', 'inside');
    const sandyB = getBool(structuredB, 'sandy_inundation', 'inside');
    if (sandyA !== undefined && sandyB !== undefined && sandyA !== sandyB) {
      rows.push({ label: 'Sandy zone', ctx: '', aVal: sandyA ? 'inside' : 'outside', bVal: sandyB ? 'inside' : 'outside' });
    }

    // 311 flood complaints (5-year radius)
    const n311A = getNum(structuredA, 'nyc311', 'n');
    const n311B = getNum(structuredB, 'nyc311', 'n');
    if (n311A !== undefined && n311B !== undefined && n311A !== n311B) {
      rows.push({ label: '311 complaints', ctx: '5 y', aVal: String(n311A), bVal: String(n311B) });
    }

    // Terrain elevation
    const elevA = getNum(structuredA, 'microtopo_lidar', 'elev_m');
    const elevB = getNum(structuredB, 'microtopo_lidar', 'elev_m');
    if (elevA !== undefined && elevB !== undefined && Math.abs(elevA - elevB) > 0.5) {
      rows.push({ label: 'Elevation', ctx: '', aVal: `${elevA.toFixed(1)} m`, bVal: `${elevB.toFixed(1)} m` });
    }

    // FloodNet sensor flood events (3-year)
    const fnA = getNum(structuredA, 'floodnet', 'n_events_3y');
    const fnB = getNum(structuredB, 'floodnet', 'n_events_3y');
    if (fnA !== undefined && fnB !== undefined && fnA !== fnB) {
      rows.push({ label: 'Sensor events', ctx: 'last 3 y', aVal: String(fnA), bVal: String(fnB) });
    }

    // Ida 2021 high-water mark (nearest within 800 m)
    const idaA = getNum(structuredA, 'ida_hwm_2021', 'max_height_above_gnd_ft');
    const idaB = getNum(structuredB, 'ida_hwm_2021', 'max_height_above_gnd_ft');
    if (idaA !== undefined && idaB !== undefined && Math.abs(idaA - idaB) > 0.1) {
      rows.push({ label: 'Ida 2021 HWM', ctx: 'ft above gnd', aVal: `${idaA.toFixed(2)} ft`, bVal: `${idaB.toFixed(2)} ft` });
    }

    return rows.slice(0, 4);
  });
</script>

<div class="compare-layout">
  {#if deltaRows.length > 0}
    <div class="compare-delta-bar" aria-label="Key differences">
      <span class="compare-delta-title">Key differences</span>
      <div class="compare-delta-rows">
        {#each deltaRows as row}
          <div class="compare-delta-row">
            <span class="compare-delta-section">{row.label}</span>
            <span class="compare-delta-claim">
              {#if row.ctx}<span class="compare-delta-ctx">{row.ctx}:</span>{/if}
              <strong class="compare-delta-a">{row.aVal}</strong>
              <span class="compare-delta-vs"> vs </span>
              <strong class="compare-delta-b">{row.bVal}</strong>
            </span>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <div class="compare-cols">
    {#each halves as half, i}
      <div class="compare-col">
        <h2 class="compare-address-header address-header">
          {halves[i].address}
        </h2>
        <Briefing
          blocks={i === 0 ? parsedA.blocks : parsedB.blocks}
          citations={allCitations}
          streaming={false}
        />
      </div>
      {#if i === 0}
        <div class="compare-divider" role="separator" aria-hidden="true"></div>
      {/if}
    {/each}
  </div>
</div>

<style>
  .compare-layout {
    width: 100%;
  }

  /* Delta summary bar — above both columns */
  .compare-delta-bar {
    border: 1px solid var(--rule-soft);
    background: var(--paper-deep);
    padding: var(--s-3) var(--s-4);
    margin-bottom: var(--s-5);
    display: flex;
    gap: var(--s-4);
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .compare-delta-title {
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--ink-tertiary);
    flex-shrink: 0;
    padding-top: 1px;
  }
  .compare-delta-rows {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-2) var(--s-5);
    flex: 1;
  }
  .compare-delta-row {
    display: inline-flex;
    align-items: baseline;
    gap: var(--s-2);
    font-family: var(--font-mono);
    font-size: 12px;
  }
  .compare-delta-section {
    color: var(--ink-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 10px;
    flex-shrink: 0;
  }
  .compare-delta-claim {
    color: var(--ink);
    display: inline-flex;
    align-items: baseline;
    gap: 3px;
  }
  .compare-delta-ctx {
    color: var(--ink-secondary);
    margin-right: 2px;
  }
  .compare-delta-a,
  .compare-delta-b {
    color: var(--accent);
    font-weight: 600;
  }
  .compare-delta-vs {
    color: var(--ink-tertiary);
    font-style: italic;
  }

  /* Two-column layout on desktop */
  .compare-cols {
    display: grid;
    grid-template-columns: 1fr 1px 1fr;
    gap: 0 var(--s-5);
    align-items: start;
  }
  .compare-col {
    min-width: 0;
  }
  /* Vertical rule between the two columns */
  .compare-divider {
    background: var(--rule-soft);
    align-self: stretch;
  }

  /* Address header — same mono treatment as .region-head-meta but larger */
  .compare-address-header {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.04em;
    color: var(--ink);
    border-bottom: 1px solid var(--rule-soft);
    padding-bottom: var(--s-2);
    margin-top: 0;
    margin-bottom: var(--s-4);
    line-height: 1.4;
  }

  /* Narrow viewport (< 900 px): stack columns vertically */
  @media (max-width: 899px) {
    .compare-cols {
      grid-template-columns: 1fr;
      gap: 0;
    }
    .compare-divider {
      width: 100%;
      height: 1px;
      margin: var(--s-5) 0;
      align-self: auto;
    }
  }
</style>
