<script lang="ts">
  import type { EvidenceItem } from '$lib/types/evidence';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
  import TierBadge from '$lib/components/glyphs/TierBadge.svelte';
  import Sparkline from './viz/Sparkline.svelte';
  import Histogram from './viz/Histogram.svelte';
  import ForecastChart from './viz/ForecastChart.svelte';
  import ThumbStripe from './viz/ThumbStripe.svelte';
  import { citations } from '$lib/stores/citations.svelte';

  interface Props { ev: EvidenceItem; }
  let { ev }: Props = $props();
  let tierColor = $derived(`var(--tier-${ev.tier})`);

  function openCite() {
    citations.active = ev.citeId;
    document.getElementById(`cite-${ev.citeId}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }
</script>

<article
  class="evidence-card evidence-card-{ev.tier}"
  aria-labelledby="ec-{ev.id}-title"
>
  <header class="evidence-card-head">
    <div class="evidence-card-source">
      <TierGlyph tier={ev.tier} size={11} color={tierColor} />
      <span class="evidence-card-source-label">{ev.source}</span>
    </div>
    <span class="evidence-card-vintage" title="Data vintage">v. {ev.vintage}</span>
  </header>
  <h4 id="ec-{ev.id}-title" class="evidence-card-title">{ev.title}</h4>

  <div class="evidence-card-body">
    {#if ev.fmt.kind === 'scalar'}
      <div class="evidence-scalar">
        <div class="evidence-scalar-value" style:color={tierColor}>{ev.fmt.value}</div>
        <div class="evidence-scalar-unit">{ev.fmt.unit}</div>
        {#if ev.fmt.aux}<div class="evidence-scalar-aux">{ev.fmt.aux}</div>{/if}
      </div>
    {:else if ev.fmt.kind === 'table'}
      <table class="evidence-table">
        <thead>
          <tr>{#each ev.fmt.columns as h (h)}<th>{h}</th>{/each}</tr>
        </thead>
        <tbody>
          {#each ev.fmt.rows as row, i (i)}
            <tr>{#each row as cell, j (j)}<td>{cell}</td>{/each}</tr>
          {/each}
        </tbody>
      </table>
    {:else if ev.fmt.kind === 'spark'}
      <div class="evidence-spark">
        <div class="evidence-spark-headline" style:color={tierColor}>{ev.fmt.headline}</div>
        <Sparkline data={ev.fmt.data} color={tierColor} />
        <div class="evidence-scalar-aux">{ev.fmt.sub}</div>
      </div>
    {:else if ev.fmt.kind === 'histogram'}
      <div class="evidence-spark">
        <div class="evidence-spark-headline" style:color={tierColor}>{ev.fmt.headline}</div>
        <Histogram data={ev.fmt.data} color={tierColor} />
        <div class="evidence-scalar-aux">{ev.fmt.sub}</div>
      </div>
    {:else if ev.fmt.kind === 'forecast'}
      <div class="evidence-spark">
        <ForecastChart data={ev.fmt.data} color={tierColor} />
        {#if ev.fmt.caption}
          <div class="evidence-scalar-aux">{ev.fmt.caption}</div>
        {/if}
      </div>
    {:else}
      <div class="evidence-thumb">
        <ThumbStripe kind={ev.fmt.thumbKind} />
        <div class="evidence-scalar-aux">{ev.fmt.sub}</div>
      </div>
    {/if}
  </div>

  <footer class="evidence-card-foot">
    <button type="button" class="evidence-card-cite" onclick={openCite} title="Open citation in drawer">
      <span class="evidence-card-docid">{ev.docId}</span>
      <span class="evidence-card-cite-arrow" aria-hidden="true">→</span>
    </button>
    <TierBadge tier={ev.tier} compact />
  </footer>
</article>
