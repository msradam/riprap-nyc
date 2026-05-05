<script lang="ts">
  import '../app.css';
  import type { Snippet } from 'svelte';
  import AppHeader from '$lib/components/shell/AppHeader.svelte';
  import AppFooter from '$lib/components/shell/AppFooter.svelte';
  import SkipLinks from '$lib/components/shell/SkipLinks.svelte';
  import { page } from '$app/state';

  interface Props { children: Snippet; }
  let { children }: Props = $props();

  let query = $derived(() => {
    const id = page.params.queryId;
    if (!id) return null;
    try {
      return decodeURIComponent(id);
    } catch {
      return id;
    }
  });

  // The /print/<id> route renders its own self-contained artifact (no
  // header / footer / skip-links). It's a print target, not an app surface.
  let isPrint = $derived(page.url.pathname.startsWith('/print/'));
</script>

{#if !isPrint}
  <SkipLinks />
  <AppHeader query={query()} onResetCold={() => (window.location.href = '/')} />
{/if}
<main>{@render children()}</main>
{#if !isPrint}
  <AppFooter />
{/if}

<style>
  main {
    min-height: calc(100vh - 200px);
  }
</style>
