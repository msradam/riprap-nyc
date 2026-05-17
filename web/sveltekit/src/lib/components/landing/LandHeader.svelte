<script lang="ts">
  /** Landing-page header. Wordmark · slash · context line · nav links.
   *  Subtly different from the in-app AppHeader so the marketing surface
   *  reads as a separate page. */
  import RipMark from '$lib/components/shell/RipMark.svelte';
</script>

<header class="land-header">
  <span class="riprap-wordmark"><RipMark size={22} />riprap</span>
  <span class="land-header-sep">/</span>
  <span class="land-header-context">Climate-exposure briefing</span>
  <nav class="land-header-nav">
    <a href="#methodology">Methodology</a>
    <a href="#sources">Sources</a>
  </nav>
</header>

<style>
  .land-header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    padding: 20px 32px;
    border-bottom: 1px solid var(--rule-soft);
  }
  .land-header :global(.riprap-wordmark) {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 18px;
    letter-spacing: 0.02em;
  }
  .land-header-sep { color: var(--ink-tertiary); }
  .land-header-context {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ink-secondary);
  }
  .land-header-nav {
    margin-left: auto;
    display: flex;
    gap: 18px;
    font-family: var(--font-mono);
    font-size: 12px;
  }
  .land-header-nav a {
    color: var(--ink-secondary);
    text-decoration: none;
    border-bottom: 1px dotted transparent;
  }
  .land-header-nav a:hover { border-bottom-color: var(--ink-secondary); }
</style>
