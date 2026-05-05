<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import Briefing from '$lib/components/briefing/Briefing.svelte';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
  import { loadSnapshot, type PrintSnapshot } from '$lib/stores/briefingState.svelte';

  let queryId = $derived(page.params.queryId ?? '');
  let snapshot = $state<PrintSnapshot | null>(null);
  let hydrationFailed = $state(false);
  let printed = $state(false);

  onMount(() => {
    const s = loadSnapshot(queryId);
    if (!s) {
      hydrationFailed = true;
      return;
    }
    snapshot = s;
    // Wait one rAF so the DOM lays out before opening the print dialog.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (typeof window !== 'undefined') {
          window.print();
          printed = true;
        }
      });
    });
  });

  function reprint() {
    if (typeof window !== 'undefined') window.print();
  }

  let citationEntries = $derived(
    snapshot ? Object.values(snapshot.citations).sort((a, b) => a.n - b.n) : []
  );
  let dateLine = $derived(
    snapshot ? new Date(snapshot.generatedAt).toISOString().slice(0, 10) : ''
  );
</script>

<svelte:head>
  <title>Riprap briefing — {snapshot?.queryText ?? 'export'}</title>
</svelte:head>

{#if hydrationFailed}
  <div class="empty">
    <h1>No briefing snapshot found</h1>
    <p>
      Run a briefing first at <a href="/">riprap home</a>; once it finishes,
      use <strong>export PDF</strong> from the header to open this view.
      Snapshots are stored per-browser and persist between runs of the same query.
    </p>
  </div>
{:else if snapshot}
  <article class="print-doc">
    <header class="print-head">
      <div class="print-head-top">
        <span class="wordmark">riprap</span>
        <span class="meta">flood-exposure briefing · v0.4.2 · {dateLine}</span>
      </div>
      <h1 class="print-title">{snapshot.queryText}</h1>
      <div class="print-sub">
        intent <strong>{snapshot.intent ?? 'briefing'}</strong>
        · {snapshot.specialists} specialists
        · {snapshot.attempts ?? 1} reconcile{(snapshot.attempts ?? 1) === 1 ? '' : 's'}
        · grounded by Mellea rejection sampling
      </div>
    </header>

    <div class="print-controls no-print">
      <button type="button" onclick={reprint}>print / save as PDF</button>
      <span class="hint">
        {printed ? 'Print dialog opened. Re-print anytime.' : 'Opening print dialog…'}
      </span>
    </div>

    <Briefing blocks={snapshot.blocks} citations={snapshot.citations} streaming={false} />

    {#if citationEntries.length}
      <section class="print-citations">
        <h2>Citations</h2>
        <ol>
          {#each citationEntries as c (c.id)}
            <li>
              <span class="cn">[{c.n}]</span>
              <span class="cglyph"><TierGlyph tier={c.tier} size={9} color="var(--tier-{c.tier})" /></span>
              <span class="csrc">{c.source}</span>
              <span class="cvint">v. {c.vintage}</span>
              <div class="ctitle">{c.title}</div>
              {#if c.url && c.url.startsWith('http')}
                <div class="curl">{c.url}</div>
              {/if}
              <div class="cdocid">doc_id <code>{c.docId}</code></div>
            </li>
          {/each}
        </ol>
      </section>
    {/if}

    <footer class="print-foot">
      Generated {dateLine} ·
      Riprap is grounded by Mellea rejection sampling over IBM Granite 4.1.
      Numbers without bracketed citations are not present in source documents.
    </footer>
  </article>
{:else}
  <div class="empty"><p>Loading…</p></div>
{/if}

<style>
  .print-doc {
    max-width: 7.5in;
    margin: 0.5in auto;
    padding: 0 0.5in;
    font-family: var(--font-serif), Georgia, serif;
    color: #111;
    background: white;
  }
  .print-head { border-bottom: 1pt solid #111; padding-bottom: 8pt; margin-bottom: 14pt; }
  .print-head-top {
    display: flex; justify-content: space-between; align-items: baseline;
    font: 9pt var(--font-mono, "IBM Plex Mono"); color: #4a4a4a;
    text-transform: uppercase; letter-spacing: 0.04em;
  }
  .wordmark { font-weight: 600; color: #111; }
  .print-title {
    font: 600 22pt var(--font-sans, "IBM Plex Sans");
    margin: 8pt 0 4pt; line-height: 1.15;
  }
  .print-sub {
    font: 10pt var(--font-mono, "IBM Plex Mono"); color: #4a4a4a;
  }
  .print-controls {
    display: flex; gap: 12px; align-items: center;
    margin: 12pt 0; padding: 8pt 10pt;
    background: #f5f5f3; border: 1px solid #d8d6d2; border-radius: 4px;
    font: 10pt var(--font-sans, "IBM Plex Sans");
  }
  .print-controls button {
    font: 10pt var(--font-sans, "IBM Plex Sans");
    padding: 4pt 10pt; background: #111; color: white; border: 0;
    border-radius: 3px; cursor: pointer;
  }
  .hint { color: #4a4a4a; font-size: 9pt; }
  .print-citations {
    margin-top: 18pt; padding-top: 8pt; border-top: 1pt solid #111;
    page-break-before: always;
  }
  .print-citations h2 {
    font: 600 13pt var(--font-sans, "IBM Plex Sans"); margin: 0 0 8pt;
  }
  .print-citations ol { list-style: none; padding: 0; margin: 0; }
  .print-citations li {
    margin-bottom: 8pt; padding-left: 28pt; position: relative;
    font-size: 10pt; line-height: 1.4;
    break-inside: avoid;
  }
  .cn {
    position: absolute; left: 0; top: 0;
    font: 600 10pt var(--font-mono, "IBM Plex Mono"); color: #0B5394;
  }
  .cglyph { display: inline-block; vertical-align: middle; margin-right: 4pt; }
  .csrc { font-weight: 600; }
  .cvint { color: #4a4a4a; margin-left: 6pt; font-size: 9pt; }
  .ctitle { color: #1a1a1a; }
  .curl { font: 8.5pt var(--font-mono, "IBM Plex Mono"); color: #0B5394; word-break: break-all; }
  .cdocid { font: 8.5pt var(--font-mono, "IBM Plex Mono"); color: #6b6b6b; }
  .print-foot {
    margin-top: 18pt; padding-top: 6pt; border-top: 1pt solid #c8c6c2;
    font: 8.5pt var(--font-mono, "IBM Plex Mono"); color: #6b6b6b;
    line-height: 1.5;
  }
  .empty {
    max-width: 600px; margin: 100px auto; padding: 24px;
    font-family: var(--font-sans, "IBM Plex Sans");
    color: #1a1a1a;
  }
  .empty h1 { font-size: 20pt; margin-bottom: 8pt; }
  .empty a { color: #0B5394; }

  @media print {
    .no-print { display: none !important; }
    .print-doc { margin: 0; padding: 0; max-width: none; }
    @page {
      size: letter;
      margin: 0.85in 0.85in 0.85in 1in;
      @bottom-right {
        content: "page " counter(page) " of " counter(pages);
        font: 9pt "IBM Plex Mono"; color: #4a4a4a;
      }
      @bottom-left {
        content: "riprap.nyc";
        font: 9pt "IBM Plex Mono"; color: #4a4a4a;
      }
    }
    .print-citations { page-break-before: always; }
  }
</style>
