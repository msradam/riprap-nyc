<script lang="ts">
  import { goto } from '$app/navigation';

  /** Landing hero — Civic-Hydrology voice (Claude Design handoff, 2026-05-17).
   *  H1: "A climate-exposure briefing for <city>." with rotating city.
   *  Deck names the four primary source families (FEMA / NOAA / USGS /
   *  city open data) so the trust-strip claim is foreshadowed inline.
   *  Cycling "Try:" rail still rotates real probe examples.
   */

  // "New York City" rather than "NYC" so the H1 line-break rhythm
  // stays consistent across the rotation. NYC is short enough to fit
  // beside "A climate-exposure briefing for", which makes the line
  // visibly shorter than for Chicago / Seattle / San Francisco /
  // Boston, where the city always falls to its own line. Using the
  // long form keeps the city on the second line every cycle.
  const CITIES = ['New York City', 'Chicago', 'Seattle', 'San Francisco', 'Boston'];

  const SAMPLE_QUERIES = [
    '80 Pioneer Street, Red Hook',
    '233 S Wacker Dr, Chicago',
    '1 City Hall Square, Boston',
    '2100 5th Ave, Seattle',
    '1 Dr Carlton B Goodlett Pl, San Francisco',
    'PS 188, Lower East Side',
    'Hammels Houses, Rockaway',
  ];

  let q = $state('');
  let cityIdx = $state(0);
  let queryIdx = $state(0);
  let cityFading = $state(false);

  $effect(() => {
    if (typeof window === 'undefined') return;
    // Fade-out → swap text → fade-in. Avoids the absolute-positioning
    // layout drift that detaches the trailing period from the H1.
    // Period stays glued to the city because the city is a single span
    // whose text content swaps in place.
    const t = setInterval(() => {
      cityFading = true;
      setTimeout(() => {
        cityIdx = (cityIdx + 1) % CITIES.length;
        queryIdx = (queryIdx + 1) % SAMPLE_QUERIES.length;
        cityFading = false;
      }, 240);
    }, 2400);
    return () => clearInterval(t);
  });

  function submit() {
    const v = q.trim();
    if (!v) return;
    goto(`/q/${encodeURIComponent(v)}`);
  }

  function pickExample() {
    const v = SAMPLE_QUERIES[queryIdx];
    goto(`/q/${encodeURIComponent(v)}`);
  }
</script>

<main class="land-hero">
  <h1 class="land-hero-h1">
    <span class="land-hero-headline">
      A climate-exposure briefing for <span
        class="city-rotate"
        class:is-fading={cityFading}
        aria-live="polite"
      >{CITIES[cityIdx]}</span>.
    </span>
    <span class="land-hero-deck">
      Type an address. Get a written briefing on flood, heat, or air-quality
      exposure. Every claim cites a public record from FEMA, NOAA, USGS, or
      city open data.
    </span>
  </h1>

  <form class="land-query" onsubmit={(e) => { e.preventDefault(); submit(); }} role="search">
    <span class="land-query-prompt" aria-hidden="true">›</span>
    <label class="visually-hidden" for="land-query-input">Address, neighborhood, or BBL</label>
    <input
      id="land-query-input"
      type="text"
      bind:value={q}
      placeholder="Address, neighborhood, or BBL. e.g. 80 Pioneer Street, Red Hook"
      class="land-query-input"
      autocomplete="street-address"
      enterkeyhint="search"
      aria-label="Address, neighborhood, or BBL"
    />
    <button type="submit" class="land-query-submit">Brief this place →</button>
  </form>

  <div class="land-cycling" aria-live="polite">
    <span class="land-cycling-label">Try:</span>
    <button type="button" class="land-cycling-rail" onclick={pickExample} title="Run this example">
      <span class="land-cycling-item" class:is-fading={cityFading}>{SAMPLE_QUERIES[queryIdx]}</span>
    </button>
  </div>
</main>

<style>
  .land-hero { padding: 64px 32px 48px; }
  .land-hero-h1 {
    display: flex;
    flex-direction: column;
    gap: 18px;
    margin: 0 0 30px;
    max-width: 880px;
  }
  .land-hero-headline {
    font-family: var(--font-serif);
    font-weight: 500;
    font-size: 52px;
    line-height: 1.08;
    color: var(--ink);
    letter-spacing: -0.015em;
  }
  .land-hero-deck {
    font-family: var(--font-serif);
    font-size: 18px;
    line-height: 1.55;
    color: var(--ink-secondary);
    max-width: 64ch;
  }

  /* City-rotate — fade-out → swap text → fade-in. Single span so the
     trailing period stays glued to the city text. H1 reflows naturally
     when the city width changes (San Francisco is the widest). */
  .city-rotate {
    display: inline;
    color: var(--accent);
    font-style: italic;
    white-space: nowrap;
    transition: opacity 240ms ease;
  }
  .city-rotate.is-fading { opacity: 0; }
  @media (prefers-reduced-motion: reduce) {
    .city-rotate { transition: none; }
  }

  .visually-hidden {
    position: absolute;
    width: 1px; height: 1px;
    padding: 0; margin: -1px;
    overflow: hidden;
    clip: rect(0,0,0,0);
    white-space: nowrap;
    border: 0;
  }

  .land-query {
    display: flex;
    align-items: stretch;
    gap: 0;
    max-width: 760px;
    border: 1px solid var(--ink);
    background: white;
    font-size: 18px;
  }
  .land-query-prompt {
    display: flex;
    align-items: center;
    padding: 0 14px;
    font-family: var(--font-mono);
    font-size: 22px;
    color: var(--ink-tertiary);
    background: var(--paper-deep);
    border-right: 1px solid var(--rule-soft);
  }
  .land-query-input {
    flex: 1;
    min-width: 0;
    padding: 18px 16px;
    font: inherit;
    font-family: var(--font-sans);
    border: none;
    outline: none;
    background: white;
    color: var(--ink);
  }
  .land-query-input::placeholder { color: var(--ink-tertiary); }
  .land-query-submit {
    padding: 0 22px;
    font-family: var(--font-sans);
    font-weight: 600;
    font-size: 14px;
    background: var(--ink);
    color: var(--paper);
    border: none;
    cursor: pointer;
    white-space: nowrap;
    letter-spacing: 0.02em;
  }
  .land-query-submit:hover { background: #000; }

  /* Try-row: single-span fade pattern. Label + cycling text share a
     real text baseline so `align-items: baseline` aligns visually.
     (Previously the rail used absolute-positioned items inside a
     fixed-height button, which had no real baseline and floated the
     label upward relative to the address.) Font-sizes still differ —
     label is the small all-caps register — but baseline-align rather
     than top/center keeps the descenders on the same line. */
  .land-cycling {
    margin-top: 18px;
    display: flex;
    align-items: baseline;
    gap: 10px;
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--ink-tertiary);
    max-width: 760px;
  }
  .land-cycling-label {
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-size: 11px;
    line-height: 1.4em;
    flex: 0 0 auto;
  }
  .land-cycling-rail {
    flex: 1 1 auto;
    min-width: 0;
    background: transparent;
    border: 0;
    padding: 0;
    cursor: pointer;
    text-align: left;
    line-height: 1.4em;
  }
  .land-cycling-item {
    display: inline-block;
    color: var(--ink);
    border-bottom: 1px dotted var(--rule-soft);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
    font-family: var(--font-mono);
    font-size: 13px;
    transition: opacity 240ms ease;
  }
  .land-cycling-item.is-fading { opacity: 0; }
  @media (prefers-reduced-motion: reduce) {
    .land-cycling-item { transition: none; }
  }

  @media (max-width: 640px) {
    .land-hero-headline { font-size: 38px; }
    .land-hero { padding: 40px 24px 32px; }
  }
</style>
