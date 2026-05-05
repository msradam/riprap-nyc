<script lang="ts">
  import { goto } from '$app/navigation';

  /** v0.4.5 landing hero: serif italic emphasis on "any place", deck,
   *  query box, cycling examples on a fixed dotted-underline rail.
   *  Mirrors docs/design_handoff/design_files/Riprap Landing.html. */

  const SAMPLE_QUERIES = [
    '80 Pioneer Street, Red Hook',
    'Coney Island Hospital',
    'PS 188, Lower East Side',
    'Hammels Houses, Rockaway',
    'Bowling Green station',
    '555 W 57th Street',
  ];

  let q = $state('');
  let i = $state(0);

  $effect(() => {
    if (typeof window === 'undefined') return;
    const t = setInterval(() => {
      i = (i + 1) % SAMPLE_QUERIES.length;
    }, 2200);
    return () => clearInterval(t);
  });

  function submit() {
    const v = q.trim();
    if (!v) return;
    goto(`/q/${encodeURIComponent(v)}`);
  }

  function pickExample() {
    const v = SAMPLE_QUERIES[i];
    goto(`/q/${encodeURIComponent(v)}`);
  }
</script>

<main class="land-hero">
  <h1 class="land-hero-h1">
    <span class="land-hero-headline">A flood exposure briefing<br /> for <em>any place</em> in New York City.</span>
    <span class="land-hero-deck">
      Type an address. Get a written briefing where every numeric claim links to its primary public-record source.
    </span>
  </h1>

  <form class="land-query" onsubmit={(e) => { e.preventDefault(); submit(); }} role="search">
    <span class="land-query-prompt" aria-hidden="true">›</span>
    <input
      type="text"
      bind:value={q}
      placeholder="Address, neighborhood, or BBL. e.g. 80 Pioneer Street, Red Hook"
      class="land-query-input"
      aria-label="Query an address, neighborhood, or BBL"
    />
    <button type="submit" class="land-query-submit">Brief this place →</button>
  </form>

  <div class="land-cycling" aria-live="polite">
    <span class="land-cycling-label">Try:</span>
    <button type="button" class="land-cycling-rail" onclick={pickExample} title="Run this example">
      {#each SAMPLE_QUERIES as s, idx (s)}
        <span class="land-cycling-item" class:is-active={idx === i} aria-hidden={idx !== i}>
          {s}
        </span>
      {/each}
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
  .land-hero-headline em { font-style: italic; font-weight: 500; }
  .land-hero-deck {
    font-family: var(--font-serif);
    font-size: 18px;
    line-height: 1.55;
    color: var(--ink-secondary);
    max-width: 64ch;
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

  .land-cycling {
    margin-top: 18px;
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: baseline;
    column-gap: 10px;
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
  }
  .land-cycling-rail {
    position: relative;
    min-width: 0;
    height: 1.4em;
    line-height: 1.4em;
    background: transparent;
    border: 0;
    padding: 0;
    cursor: pointer;
    text-align: left;
  }
  .land-cycling-item {
    position: absolute;
    inset: 0;
    line-height: 1.4em;
    opacity: 0;
    transition: opacity 240ms ease;
    color: var(--ink);
    border-bottom: 1px dotted var(--rule-soft);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-family: var(--font-mono);
    font-size: 13px;
  }
  .land-cycling-item.is-active { opacity: 1; }

  @media (max-width: 640px) {
    .land-hero-headline { font-size: 38px; }
    .land-hero { padding: 40px 24px 32px; }
  }
</style>
