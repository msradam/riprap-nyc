<script lang="ts">
  import type { Citation } from '$lib/types/claim';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
  import { citations as cstore } from '$lib/stores/citations.svelte';

  interface Props { citations: Record<string, Citation>; }
  let { citations }: Props = $props();

  let entries = $derived(Object.values(citations).sort((a, b) => a.n - b.n));
</script>

<aside class="citation-drawer" aria-label="Citations">
  <div class="citation-drawer-head">
    <span class="section-label">Citations · {entries.length}</span>
    <span class="citation-drawer-meta">live · primary sources</span>
  </div>
  <ol class="citation-list">
    {#each entries as c (c.id)}
      <li
        id="cite-{c.id}"
        class="citation-item"
        class:is-active={cstore.active === c.id}
      >
        <span class="citation-num">[{c.n}]</span>
        <div class="citation-body">
          <div class="citation-line-1">
            <TierGlyph tier={c.tier} size={10} color="var(--tier-{c.tier})" />
            <span class="citation-source">{c.source}</span>
            <span class="citation-vintage">v. {c.vintage}</span>
          </div>
          <div class="citation-title">
            {#if c.url && c.url.startsWith('http')}
              <a href={c.url} target="_blank" rel="noopener noreferrer">{c.title}</a>
            {:else}
              {c.title}
            {/if}
          </div>
          <div class="citation-meta">
            <span class="citation-docid">{c.docId}</span>
            <span class="citation-retrieved">retr. {c.retrieved}</span>
          </div>
        </div>
      </li>
    {/each}
  </ol>
  <div class="citation-drawer-foot">
    <span class="section-label">Trust signals</span>
    <p class="citation-foot-copy">
      All foundation models Apache-2.0. All data from public-record federal,
      state, and city sources. No commercial APIs contacted at runtime.
    </p>
  </div>
</aside>

<style>
  .citation-drawer :global(a) {
    color: inherit;
    border-bottom: 1px solid var(--rule-soft);
    text-decoration: none;
  }
  .citation-drawer :global(a:hover) {
    border-bottom-color: var(--accent);
    color: var(--accent);
  }
</style>
