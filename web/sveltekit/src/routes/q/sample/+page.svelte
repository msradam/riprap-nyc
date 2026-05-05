<script lang="ts">
  import { onMount } from 'svelte';
  import Briefing from '$lib/components/briefing/Briefing.svelte';
  import CitationDrawer from '$lib/components/briefing/CitationDrawer.svelte';
  import RipMap from '$lib/components/map/RipMap.svelte';
  import MapLegend from '$lib/components/map/MapLegend.svelte';
  import FindingsRegion from '$lib/components/findings/FindingsRegion.svelte';
  import { BRIEFING_BLOCKS, CITATIONS, SAMPLE_ADDRESS } from '$lib/data/sample';
  import { SAMPLE_FINDINGS } from '$lib/data/findingsSample';
  import { briefingState, persistSnapshot } from '$lib/stores/briefingState.svelte';
  import type { Density, ProvenanceMode } from '$lib/types/card';
  import type { FeatureCollection } from 'geojson';

  /** Cross-linking state, lifted to the page so the briefing's map can
   *  read the Findings card under hover. */
  let linkedKey = $state<string | null>(null);
  let density = $state<Density>('comfortable');
  let provenanceMode = $state<ProvenanceMode>('smart');
  /** Dev-only card-grammar catalog. Toggle with ?grammar=1 in the URL.
   *  Read only on the client — adapter-static forbids url.searchParams
   *  at prerender time. */
  let showGrammar = $state(false);
  $effect(() => {
    if (typeof window !== 'undefined') {
      showGrammar = new URL(window.location.href).searchParams.get('grammar') === '1';
    }
  });

  function handleLink(key: string | null) {
    linkedKey = key;
  }
  function handleCite(citeId: string) {
    // Citation drawer is below; scroll it into view + flag for now.
    // (Real wiring lands in C8 once CitationDrawer exposes an open()
    // method.)
    const el = document.getElementById('region-cites');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    void citeId;
  }

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

        <aside id="region-cites" class="app-region app-region-cites" aria-label="Citations">
          <CitationDrawer citations={CITATIONS} />
        </aside>
      </div>
    </div>

    <div class="app-shell-bottom">
      <section class="app-region app-region-findings" aria-label="Findings">
        <FindingsRegion
          data={SAMPLE_FINDINGS}
          {density}
          {provenanceMode}
          {showGrammar}
          {linkedKey}
          onLink={handleLink}
          onCite={handleCite}
        />
      </section>
    </div>
  </div>
</section>
