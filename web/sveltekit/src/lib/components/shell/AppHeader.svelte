<script lang="ts">
  import { page } from '$app/state';
  import { briefingState } from '$lib/stores/briefingState.svelte';
  import { deployment } from '$lib/stores/deployment.svelte';
  import { exportBriefingPdf, ExportPdfError } from '$lib/client/exportPdf';
  import RipMark from './RipMark.svelte';
  import StatusPill from './StatusPill.svelte';

  interface Props {
    query?: string | null;
    onResetCold?: () => void;
  }
  let { query = null, onResetCold }: Props = $props();

  // Fetch the active-deployment descriptor on mount; cheap, cached
  // by the store, returns hazard + city pulled from stones.yaml.
  $effect(() => {
    if (typeof window !== 'undefined' && !deployment.loaded) {
      void deployment.load();
    }
  });

  // Chip text:
  //   - hazard text (e.g. "Flood-exposure briefing") rendered lowercase
  //     to match the existing chip register
  //   - city rendered as a pill on the right side of the chip
  // Falls back to the hardcoded string while the API call is in flight
  // or if it fails (offline-graceful).
  const hazardText = $derived(
    deployment.current?.hazard.toLowerCase() ?? 'flood-exposure briefing'
  );
  const cityText = $derived(deployment.current?.city ?? null);

  let exporting = $state(false);
  let exportError = $state<string | null>(null);

  /** Export the completed briefing to PDF via the server-side route.
   *  The PrintSnapshot in localStorage is transformed into the body
   *  /api/print expects; the response is opened in a new tab as a
   *  blob URL. Hidden until briefingState.ready — we don't want users
   *  exporting a half-streamed report. */
  async function exportPdf() {
    if (typeof window === 'undefined') return;
    const id = page.params.queryId;
    if (!id) return;
    exporting = true;
    exportError = null;
    try {
      await exportBriefingPdf(id);
    } catch (e) {
      exportError = e instanceof ExportPdfError ? e.message : String(e);
      // Auto-clear the toast after 8s so it doesn't stick around forever.
      setTimeout(() => { exportError = null; }, 8000);
    } finally {
      exporting = false;
    }
  }
</script>

<header class="app-header no-print" data-screen-label="App header">
  <div class="app-header-inner">
    <div class="app-header-left">
      <a href="/" class="riprap-wordmark" aria-label="Riprap — home"><RipMark size={20} />riprap</a>
      <span class="app-header-sep">/</span>
      <span class="app-header-context">{hazardText}</span>
      {#if cityText}
        <span class="app-header-city-pill" aria-label="Active deployment">{cityText}</span>
      {/if}
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
          onclick={exportPdf}
          disabled={exporting}
          aria-label="Export this briefing as a PDF and open it in a new tab"
        >{exporting ? 'rendering…' : 'export PDF'}</button>
      {/if}
      <StatusPill />
    </div>
  </div>
  {#if exportError}
    <div class="app-header-toast" role="alert">{exportError}</div>
  {/if}
</header>

<style>
  .app-header-link-button {
    background: transparent;
    border: 0;
    padding: 0;
    font: inherit;
    cursor: pointer;
  }
  .app-header-link-button:disabled {
    color: var(--ink-tertiary);
    cursor: progress;
  }
  /* Inline error toast (PDF unavailable, snapshot missing, etc.). Lives
     below the header so it doesn't shift the page layout. Auto-clears
     after 8 s — set by exportPdf(). */
  .app-header-toast {
    background: #FEF3C7;
    border-top: 1px solid var(--accent-warn);
    color: var(--ink);
    font-family: var(--font-mono);
    font-size: 12px;
    padding: 8px 14px;
  }
  /* City-pill on the chip — small federal-blue tag that ties the
     header to the active deployment. Quiet, not competing with
     the wordmark. */
  .app-header-city-pill {
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.04em;
    color: var(--accent);
    background: var(--reference-bg);
    border: 1px solid var(--reference-line);
    border-radius: 3px;
    padding: 2px 7px;
    margin-left: 6px;
    text-transform: none;
    line-height: 1.3;
  }
</style>
