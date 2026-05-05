<script lang="ts">
  import { page } from '$app/state';
  import { briefingState } from '$lib/stores/briefingState.svelte';

  interface Props {
    query?: string | null;
    onResetCold?: () => void;
  }
  let { query = null, onResetCold }: Props = $props();

  /**
   * Open the curated print artifact in a new tab. The print route
   * hydrates from localStorage (key riprap:print:<queryId>), renders
   * briefing + citations only, and auto-fires window.print(). Hidden
   * until the live page signals briefingState.ready — we don't want
   * users exporting a half-streamed report.
   */
  function openPrintView() {
    if (typeof window === 'undefined') return;
    const id = page.params.queryId ?? (page.url.pathname === '/q/sample' ? 'sample' : '');
    if (!id) return;
    window.open(`/print/${encodeURIComponent(id)}`, '_blank', 'noopener');
  }
</script>

<header class="app-header no-print" data-screen-label="App header">
  <div class="app-header-inner">
    <div class="app-header-left">
      <a href="/" class="riprap-wordmark" aria-label="Riprap — home">riprap</a>
      <span class="app-header-sep">/</span>
      <span class="app-header-context">flood-exposure briefing</span>
    </div>
    <div class="app-header-mid">
      {#if query}
        <button
          type="button"
          class="app-header-query"
          onclick={onResetCold}
          aria-label="Edit query"
        >
          <span class="app-header-query-icon" aria-hidden="true">⌕</span>
          <span class="app-header-query-text">{query}</span>
          <span class="app-header-query-edit">edit</span>
        </button>
      {/if}
    </div>
    <div class="app-header-right">
      <a class="app-header-link" href="#methodology">methodology</a>
      {#if briefingState.ready}
        <button
          type="button"
          class="app-header-link app-header-link-button"
          onclick={openPrintView}
          aria-label="Open curated PDF view of completed briefing in new tab"
        >export PDF</button>
      {/if}
      <span class="app-header-status" aria-live="polite">
        <span class="app-header-status-dot" aria-hidden="true"></span>
        live
      </span>
    </div>
  </div>
</header>

<style>
  .app-header-link-button {
    background: transparent;
    border: 0;
    padding: 0;
    font: inherit;
    cursor: pointer;
  }
</style>
