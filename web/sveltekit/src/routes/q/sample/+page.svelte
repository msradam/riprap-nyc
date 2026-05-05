<script lang="ts">
  import { onMount } from 'svelte';
  import Briefing from '$lib/components/briefing/Briefing.svelte';
  import CitationDrawer from '$lib/components/briefing/CitationDrawer.svelte';
  import EvidenceGrid from '$lib/components/evidence/EvidenceGrid.svelte';
  import TraceUI from '$lib/components/trace/TraceUI.svelte';
  import RipMap from '$lib/components/map/RipMap.svelte';
  import MapLegend from '$lib/components/map/MapLegend.svelte';
  import { BRIEFING_BLOCKS, CITATIONS, EVIDENCE, TRACE_ROOT, SAMPLE_ADDRESS } from '$lib/data/sample';
  import { briefingState, persistSnapshot } from '$lib/stores/briefingState.svelte';
  import type { FeatureCollection } from 'geojson';

  let active = $state({ empirical: true, modeled: true, synthetic: true, proxy: true });
  let streamKey = $state(0);

  onMount(() => {
    // Sample is prerendered; the briefing is "complete" the moment it mounts.
    persistSnapshot({
      queryId: 'sample',
      queryText: SAMPLE_ADDRESS,
      intent: 'single_address',
      specialists: 9,
      blocks: BRIEFING_BLOCKS,
      citations: CITATIONS,
      generatedAt: new Date().toISOString(),
      attempts: 1
    });
    briefingState.markReady();
    return () => briefingState.reset();
  });

  // 80 Pioneer St, Red Hook, Brooklyn
  const queriedAddress = { label: '80 Pioneer St', lat: 40.6776, lon: -74.0096 };

  /**
   * Sample-route synthetic-prior fixture. The Prithvi water-mask data
   * doesn't cover Red Hook (Hurricane Ida 2021 hit other neighborhoods),
   * so for the prerendered worked example we ship a small synthetic
   * polygon near the queried-address pin. This makes the syn-stripe-45
   * fill pattern visible in the demo without needing a backend round-trip.
   * On the live route the layer is fetched from /api/layers/prithvi_water.
   */
  const SYN_FIXTURE: FeatureCollection = {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { source: 'sample-fixture', tier: 'synthetic' },
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [-74.0140, 40.6790],
            [-74.0070, 40.6800],
            [-74.0050, 40.6770],
            [-74.0090, 40.6755],
            [-74.0140, 40.6790]
          ]]
        }
      }
    ]
  };
</script>

<section class="hero-band">
  <div class="hero-band-inner">
    <div class="app-shell-top is-desktop">
      <main id="region-briefing" class="app-region app-region-brief" aria-labelledby="brief-h1">
        <header class="region-head">
          <span class="section-label">Briefing</span>
          <button
            type="button"
            class="region-action"
            onclick={() => (streamKey += 1)}
            aria-label="Replay streaming"
          >↻ replay stream</button>
        </header>
        <h1 id="brief-h1" class="brief-h1">
          Flood-exposure briefing
          <span class="brief-h1-addr">{SAMPLE_ADDRESS}</span>
        </h1>
        <Briefing blocks={BRIEFING_BLOCKS} citations={CITATIONS} streaming replayKey={streamKey} />
      </main>

      <div class="app-region-side" style="grid-area: side;">
        <aside id="region-map" class="app-region app-region-map" aria-label="Map region">
          <header class="region-head">
            <span class="section-label">Map</span>
            <span class="region-head-meta">Carto Positron · z15 · 40.6776°N 74.0096°W</span>
          </header>
          <div style="position: relative; flex: 1; min-height: 0;">
            <RipMap
              address={queriedAddress}
              activeLayers={active}
              syntheticPrior={SYN_FIXTURE}
            />
            <MapLegend
              {active}
              featureCounts={{
                empirical: 0,
                modeled: 0,
                synthetic: SYN_FIXTURE.features.length,
                proxy: 0
              }}
              onToggle={(k) => (active = { ...active, [k]: !active[k] })}
            />
          </div>
        </aside>

        <aside class="app-region app-region-cites" aria-label="Citations">
          <CitationDrawer citations={CITATIONS} />
        </aside>
      </div>
    </div>

    <div class="app-shell-bottom">
      <section class="app-region app-region-evidence" aria-label="Evidence">
        <EvidenceGrid items={EVIDENCE} />
      </section>

      <section id="region-trace" class="app-region app-region-trace" aria-label="Trace">
        <TraceUI root={TRACE_ROOT} />
      </section>
    </div>
  </div>
</section>
