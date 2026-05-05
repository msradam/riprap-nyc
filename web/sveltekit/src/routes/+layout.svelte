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

  // The /print/<id> route renders its own self-contained artifact and
  // the landing at `/` is a self-contained marketing surface — both
  // bring their own chrome, so the layout's AppHeader / AppFooter sit
  // out for them. The cold-start at /app and the briefing at /q/<id>
  // still get the app chrome.
  let isPrint = $derived(page.url.pathname.startsWith('/print/'));
  let isLanding = $derived(page.url.pathname === '/');
  let chromeFree = $derived(isPrint || isLanding);
</script>

{#if !chromeFree}
  <SkipLinks />
  <AppHeader query={query()} onResetCold={() => (window.location.href = '/app')} />
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
