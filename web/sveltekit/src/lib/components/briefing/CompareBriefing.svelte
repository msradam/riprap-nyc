<script lang="ts">
  import Briefing from './Briefing.svelte';
  import { parseBriefing } from '$lib/client/parseBriefing';
  import type { BriefingBlock, Citation } from '$lib/types/claim';

  interface Target {
    label: string;
    address: string;
  }

  interface Props {
    paragraph: string;
    citations: Record<string, Citation>;
    targets: Target[];
  }

  let { paragraph, citations, targets }: Props = $props();

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

  // Collect prose text keyed by section number ('01'–'04').
  function sectionTexts(blocks: BriefingBlock[]): Map<string, string> {
    const map = new Map<string, string>();
    let cur = '';
    for (const b of blocks) {
      if (b.kind === 'head') cur = b.n;
      else if (b.kind === 'prose' && cur) {
        map.set(cur, (map.get(cur) ?? '') + ' ' + b.parts.map((p) => p.text).join(''));
      }
    }
    return map;
  }

  // Return all numbers (with optional unit suffix) in a text, in order.
  const NUM_RE = /\b(\d[\d,]*(?:\.\d+)?)\s*(%|ft|m|km|mm)?\b/g;
  function findNumbers(text: string): Array<{ full: string; start: number }> {
    const hits: Array<{ full: string; start: number }> = [];
    let m: RegExpExecArray | null;
    NUM_RE.lastIndex = 0;
    while ((m = NUM_RE.exec(text)) !== null) {
      const full = m[1] + (m[2] ?? '');
      hits.push({ full, start: m.index });
    }
    return hits;
  }

  // Up to 3 words immediately before `start` in `text`.
  function ctxBefore(text: string, start: number): string {
    const snippet = text.slice(Math.max(0, start - 40), start).trim();
    return snippet.split(/\s+/).slice(-3).join(' ');
  }

  const SECTION_LABELS: Record<string, string> = {
    '01': 'Status',
    '02': 'Empirical',
    '03': 'Modeled',
    '04': 'Policy'
  };

  interface DeltaRow {
    sectionLabel: string;
    ctx: string;
    aVal: string;
    bVal: string;
  }

  // One delta row per canonical section where the first compared number differs.
  const deltaRows = $derived.by<DeltaRow[]>(() => {
    const textsA = sectionTexts(parsedA.blocks);
    const textsB = sectionTexts(parsedB.blocks);
    const rows: DeltaRow[] = [];
    for (const [n, label] of Object.entries(SECTION_LABELS)) {
      const tA = textsA.get(n) ?? '';
      const tB = textsB.get(n) ?? '';
      if (!tA || !tB) continue;
      const numsA = findNumbers(tA);
      const numsB = findNumbers(tB);
      if (!numsA.length || !numsB.length) continue;
      const len = Math.min(numsA.length, numsB.length);
      for (let i = 0; i < len; i++) {
        if (numsA[i].full !== numsB[i].full) {
          rows.push({
            sectionLabel: label,
            ctx: ctxBefore(tA, numsA[i].start),
            aVal: numsA[i].full,
            bVal: numsB[i].full
          });
          break;
        }
      }
    }
    return rows;
  });
</script>

<div class="compare-layout">
  {#if deltaRows.length > 0}
    <div class="compare-delta-bar" aria-label="Key differences">
      <span class="compare-delta-title">Key differences</span>
      <div class="compare-delta-rows">
        {#each deltaRows as row}
          <div class="compare-delta-row">
            <span class="compare-delta-section">{row.sectionLabel}</span>
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
