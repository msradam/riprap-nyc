<svelte:options
  customElement={{
    tag: "r-sources-footer",
    props: {
      labels:   { type: "Object" },
      urls:     { type: "Object" },
      vintages: { type: "Object" },
    },
  }} />

<script>
  import { citeIndex, highlightedDocId } from "./stores.js";
  import { fade, scale } from "svelte/transition";
  import { cubicOut } from "svelte/easing";

  let { labels = {}, urls = {}, vintages = {} } = $props();

  let entries = $derived(
    Object.entries($citeIndex || {}).sort((a, b) => a[1] - b[1])
  );
  let hl = $derived($highlightedDocId);
</script>

{#if entries.length}
  <div class="src-h" in:fade={{ duration: 200 }}>Sources</div>
  <ol>
    {#each entries as [id, n] (id)}
      {@const url = urls[id]}
      {@const label = labels[id] || id}
      {@const vintage = vintages[id]}
      <li class:hl={id === hl}
          in:scale={{ start: 0.96, duration: 220, easing: cubicOut }}
          onmouseenter={() => highlightedDocId.set(id)}
          onclick={() => highlightedDocId.set(hl === id ? null : id)}>
        <span class="src-num">[{n}]</span>
        <div>
          {#if url}
            <a class="src-link" href={url} target="_blank" rel="noopener noreferrer"
               onclick={(e) => e.stopPropagation()}>
              {label} <span class="src-ext">↗</span>
            </a>
          {:else}
            <span>{label}</span>
          {/if}
          <span class="src-id">{id}</span>
          {#if vintage}<span class="src-vintage">{vintage}</span>{/if}
        </div>
      </li>
    {/each}
  </ol>
{/if}

<style>
  :host {
    display: block;
    border-top: 1px solid var(--line, #e5e7eb);
    background: var(--bg-soft, #f5f7fb);
    padding: 12px 16px 14px;
  }
  :host(:not(:has(ol))) { display: none; }
  .src-h {
    font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.10em;
    color: var(--text-muted, #6b7280);
    margin: 0 0 8px;
  }
  ol {
    margin: 0; padding: 0; list-style: none;
    display: grid; gap: 6px;
    font-size: 11.5px; line-height: 1.45;
  }
  li {
    display: grid; grid-template-columns: 22px 1fr;
    gap: 8px; align-items: baseline;
    padding: 4px 6px; border-radius: 3px;
    cursor: pointer;
    transition: background 0.15s;
  }
  li:hover, li.hl { background: rgba(22, 66, 223, 0.10); }
  li.hl {
    /* Brief pulse each time a chip selects this row. */
    animation: pulse 360ms cubic-bezier(.2,.7,.3,1);
  }
  @keyframes pulse {
    0%   { box-shadow: 0 0 0 0   rgba(22, 66, 223, 0.35); }
    60%  { box-shadow: 0 0 0 6px rgba(22, 66, 223, 0.00); }
    100% { box-shadow: 0 0 0 0   rgba(22, 66, 223, 0.00); }
  }
  .src-num {
    font-family: var(--mono, monospace); font-size: 10.5px;
    font-weight: 700; color: var(--nyc-blue, #1642DF);
    text-align: right;
  }
  .src-link {
    color: var(--text, #111); text-decoration: none;
    border-bottom: 1px dotted var(--text-muted, #6b7280);
  }
  .src-link:hover {
    color: var(--nyc-blue, #1642DF);
    border-bottom-color: var(--nyc-blue, #1642DF);
  }
  .src-ext { font-size: 9.5px; color: var(--text-faint, #9ca3af); margin-left: 2px; vertical-align: super; }
  .src-vintage { display: block; color: var(--text-muted, #6b7280); font-size: 9.5px; margin-top: 2px; }
  .src-id { display: inline-block; font-family: var(--mono, monospace); font-size: 9.5px; color: var(--text-faint, #9ca3af); margin-left: 6px; }
</style>
