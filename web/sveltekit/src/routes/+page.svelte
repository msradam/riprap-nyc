<script lang="ts">
  /** v0.4.5 marketing landing page at `/`.
   *
   *  Per docs/design_handoff/README.md §"Landing page": four-section
   *  vertical scroll inside a 1200px-max paper-background frame:
   *
   *    1. Header (wordmark · context · nav)
   *    2. Hero (italic-serif headline · deck · query box · cycling examples)
   *    3. "What you'll get back" preview (excerpt · evidence cards · mini map)
   *    4. Five Stones strip (5-cell explanation grid with oversized numerals)
   *    5. Footer (tier legend + build line)
   *
   *  Cold-start (the analyst's "ready to query" page) lives at /app.
   *  Live briefings remain at /q/<query>; sample at /q/sample.
   */
  import SkipLink from '$lib/components/shell/SkipLink.svelte';
  import PhaseBanner from '$lib/components/landing/PhaseBanner.svelte';
  import LandHeader from '$lib/components/landing/LandHeader.svelte';
  import LandHero from '$lib/components/landing/LandHero.svelte';
  import CityPicker from '$lib/components/landing/CityPicker.svelte';
  import SourceStrip from '$lib/components/landing/SourceStrip.svelte';
  import UseBand from '$lib/components/landing/UseBand.svelte';
  import StandardsStrip from '$lib/components/landing/StandardsStrip.svelte';
  import LandStones from '$lib/components/landing/LandStones.svelte';
  import LandFooter from '$lib/components/landing/LandFooter.svelte';

  // LandPreview was removed: its "Briefing excerpt" pane fabricated
  // citation chrome around numbers no one had queried (a `4.7 ft Sandy
  // HWM` claim with a `[c1] USGS HWM · Sandy 2012` chip, all
  // synthetic). LandStones below is the structural explainer for
  // "what you'll get back" and contains no fabricated data.
</script>

<svelte:head>
  <title>Riprap — climate-exposure briefings for any US place</title>
  <meta name="description" content="Riprap composes federal, state, and city open data into a written, citation-grounded climate-exposure briefing for any US address. Open source, Apache-2.0. Five cities live: NYC, Chicago, Seattle, San Francisco, Boston." />
</svelte:head>

<SkipLink />
<PhaseBanner />

<div class="land">
  <LandHeader />
  <div class="land-page" id="main-content">
    <LandHero />
    <div class="land-trust">
      <CityPicker />
      <SourceStrip />
      <UseBand />
      <StandardsStrip />
    </div>
  </div>
  <LandStones />
  <LandFooter />
</div>

<style>
  .land {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background: var(--paper);
    color: var(--ink);
  }
  .land-page { max-width: 1200px; margin: 0 auto; width: 100%; }
  .land-trust {
    /* Trust-signal stack — city picker + source counts + responsible-use
       + standards. Inset by the same horizontal padding as LandHero so
       the visual rhythm holds across the column. */
    padding: 0 32px 8px;
    max-width: 880px;
  }
  @media (max-width: 640px) {
    .land-trust { padding: 0 24px 8px; }
  }
</style>
