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

  // The landing at / and the print artifact at /print/<id> both bring
  // their own chrome, so the layout's AppHeader / AppFooter sit out
  // for those. Briefings at /q/<id> still get the app chrome.
  let isPrint = $derived(page.url.pathname.startsWith('/print/'));
  let isLanding = $derived(page.url.pathname === '/');
  let chromeFree = $derived(isPrint || isLanding);
</script>

{#if !chromeFree}
  <SkipLinks />
  <AppHeader query={query()} onResetCold={() => (window.location.href = '/')} />
{/if}
<main>{@render children()}</main>
{#if !chromeFree}
  <AppFooter />
{/if}

<style>
  main {
    min-height: calc(100vh - 200px);
  }
</style>
