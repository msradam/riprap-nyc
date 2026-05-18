<script lang="ts">
  import { goto } from '$app/navigation';

  const SAMPLE_QUERIES = [
    {
      mode: 'address',
      q: '80 Pioneer Street, Red Hook, Brooklyn',
      sub: 'Address-mode · Sandy edge · IBZ · NYCHA proximity'
    },
    {
      mode: 'neighborhood',
      q: 'Far Rockaway flood exposure briefing',
      sub: 'Neighborhood-mode · chronic stormwater · 2050 SLR'
    },
    {
      mode: 'development',
      q: 'Hunts Point proposed rezoning — flood-context check',
      sub: 'Development-check · CEQR §817 · 311 proxy density'
    }
  ];

  let v = $state('');

  function submit(query: string) {
    const q = query.trim();
    if (!q) return;
    goto(`/q/${encodeURIComponent(q)}`);
  }

  function onSubmit(e: SubmitEvent) {
    e.preventDefault();
    submit(v);
  }
</script>

<section class="cold-start" aria-label="Empty query state">
  <div class="cold-start-band">
    <p class="cold-start-deck">
      <strong>Riprap</strong> is a citation-grounded flood-exposure briefing tool for New York City.
      Type an address, neighborhood, or proposed development — Riprap returns a written briefing
      where every numeric claim links to its primary public-record source.
    </p>
    <p class="cold-start-deck cold-start-deck-secondary">
      Built for agency analysts, planners, journalists, community boards, and researchers.
      <strong>Not for individual residents making personal property decisions.</strong>
      For residents seeking flood guidance, see
      <a href="https://www.floodhelpny.org" class="cold-start-redir">FloodHelpNY</a>.
      For real-time conditions, see
      <a href="https://www.floodnet.nyc" class="cold-start-redir">FloodNet NYC</a>.
    </p>
  </div>

  <form class="cold-start-form" onsubmit={onSubmit} role="search">
    <label for="riprap-query" class="cold-start-label section-label">Query</label>
    <div class="cold-start-input-row">
      <input
        id="riprap-query"
        type="text"
        bind:value={v}
        placeholder="address · neighborhood · proposed development"
        class="cold-start-input"
        autocomplete="off"
      />
      <button type="submit" class="cold-start-submit">Generate briefing →</button>
    </div>
  </form>

  <div class="cold-start-samples">
    <span class="section-label cold-start-samples-label">Sample queries</span>
    <div class="cold-start-samples-grid">
      {#each SAMPLE_QUERIES as s, i (i)}
        <button type="button" class="cold-start-sample" onclick={() => submit(s.q)}>
          <span class="cold-start-sample-mode">{s.mode}</span>
          <span class="cold-start-sample-q">{s.q}</span>
          <span class="cold-start-sample-sub">{s.sub}</span>
          <span class="cold-start-sample-arrow" aria-hidden="true">↗</span>
        </button>
      {/each}
    </div>
  </div>

  <div class="cold-start-trust">
    <span class="section-label">How Riprap is built</span>

    <!-- v0.4.5 §9 — five-Stones one-liner with Stone-tinted dots beside
         each name. Tints are hint-level decoration; print degrades them
         to neutral gray via the @media print rule in tokens.css. -->
    <ul class="cold-start-stones">
      <li>
        <span class="stone-dot" style="background: var(--stone-cornerstone);" aria-hidden="true"></span>
        <em>Cornerstone</em> remembers — what the ground remembers.
      </li>
      <li>
        <span class="stone-dot" style="background: var(--stone-keystone);" aria-hidden="true"></span>
        <em>Keystone</em> tallies — what's exposed.
      </li>
      <li>
        <span class="stone-dot" style="background: var(--stone-touchstone);" aria-hidden="true"></span>
        <em>Touchstone</em> watches — what's happening now.
      </li>
      <li>
        <span class="stone-dot" style="background: var(--stone-lodestone);" aria-hidden="true"></span>
        <em>Lodestone</em> projects — what's coming.
      </li>
      <li>
        <span class="stone-dot" style="background: var(--stone-capstone);" aria-hidden="true"></span>
        <em>Capstone</em> writes it all down with citations.
      </li>
    </ul>

    <ul class="cold-start-trust-list">
      <li>All foundation models <strong>Apache-2.0</strong>; no commercial APIs at runtime.</li>
      <li>All data from public-record federal, state, and city sources.</li>
      <li>Four epistemic tiers — empirical, modeled, proxy, synthetic prior — visible in the briefing margin and the trace.</li>
      <li>Sections without supporting documents are omitted entirely. Silence over confabulation.</li>
    </ul>
    <a href="#methodology" class="cold-start-method-link">Methodology paper →</a>
  </div>
</section>

<style>
  .cold-start-stones {
    list-style: none;
    margin: 12px 0 16px;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .cold-start-stones li {
    display: flex;
    align-items: baseline;
    gap: 10px;
    font-family: var(--font-sans);
    font-size: 14px;
    color: var(--ink-secondary);
    line-height: 1.5;
  }
  .cold-start-stones em {
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 16px;
    color: var(--ink);
    margin-right: 2px;
  }
  .stone-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex: none;
    align-self: center;
  }
</style>
