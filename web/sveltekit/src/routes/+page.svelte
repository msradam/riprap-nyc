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
  import LandHeader from '$lib/components/landing/LandHeader.svelte';
  import LandHero from '$lib/components/landing/LandHero.svelte';
  import LandPreview from '$lib/components/landing/LandPreview.svelte';
  import LandStones from '$lib/components/landing/LandStones.svelte';
  import LandFooter from '$lib/components/landing/LandFooter.svelte';
</script>

<svelte:head>
  <title>Riprap — Flood Exposure Briefing for NYC</title>
  <meta name="description" content="A citation-grounded flood-exposure briefing tool for any address, neighborhood, or BBL in New York City." />
</svelte:head>

<div class="land">
  <LandHeader />
  <div class="land-page">
    <LandHero />
    <LandPreview />
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
</style>
