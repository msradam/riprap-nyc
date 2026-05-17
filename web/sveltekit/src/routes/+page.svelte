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
  import ByodDialog from '$lib/components/landing/ByodDialog.svelte';
  import LandStones from '$lib/components/landing/LandStones.svelte';
  import LandFooter from '$lib/components/landing/LandFooter.svelte';
  import { byodRegistry } from '$lib/stores/byodRegistry.svelte';

  // LandPreview was removed: its "Briefing excerpt" pane fabricated
  // citation chrome around numbers no one had queried (a `4.7 ft Sandy
  // HWM` claim with a `[c1] USGS HWM · Sandy 2012` chip, all
  // synthetic). LandStones below is the structural explainer for
  // "what you'll get back" and contains no fabricated data.

  let byodOpen = $state(false);

  // Load BYOD registry on mount so the trigger badge shows how many
  // user pebbles are already stored in this browser.
  $effect(() => {
    if (typeof window !== 'undefined' && !byodRegistry.loaded) {
      void byodRegistry.load();
    }
  });
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
      <div class="land-byod-row">
        <button
          type="button"
          class="land-byod-trigger"
          onclick={() => (byodOpen = true)}
        >
          + Bring your own data
          {#if byodRegistry.entries.length > 0}
            <span class="land-byod-badge">{byodRegistry.entries.length}</span>
          {/if}
        </button>
        <span class="land-byod-note">Files stay in your browser. No upload.</span>
      </div>
      <UseBand />
      <StandardsStrip />
    </div>
  </div>

  <ByodDialog open={byodOpen} onClose={() => (byodOpen = false)} />
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
  .land-byod-row {
    margin-top: 18px;
    display: flex;
    align-items: baseline;
    gap: 12px;
    flex-wrap: wrap;
  }
  .land-byod-trigger {
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 500;
    color: var(--accent);
    background: transparent;
    border: 1px solid var(--accent);
    padding: 6px 14px;
    cursor: pointer;
    letter-spacing: 0.02em;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .land-byod-trigger:hover { background: var(--accent); color: white; }
  .land-byod-trigger:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 2px;
  }
  .land-byod-badge {
    display: inline-block;
    background: var(--accent);
    color: white;
    font-size: 10.5px;
    padding: 1px 6px;
    border-radius: 2px;
    margin-left: 2px;
  }
  .land-byod-trigger:hover .land-byod-badge {
    background: white;
    color: var(--accent);
  }
  .land-byod-note {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    letter-spacing: 0.02em;
  }
  @media (max-width: 640px) {
    .land-trust { padding: 0 24px 8px; }
  }
</style>
