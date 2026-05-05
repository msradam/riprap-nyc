<script lang="ts">
  import type { Card, StoneTrace } from '$lib/types/card';

  /** Top-of-Findings status row. Mirrors findings.jsx RunHealth44:
   *  Stones · functions fired · evidence cards · wall-clock · silent /
   *  warn / error chips when nonzero. */
  interface Props {
    cards: Card[];
    stones: StoneTrace[];
    wallSeconds?: number;
    cacheHit?: number;
  }

  let { cards, stones, wallSeconds, cacheHit }: Props = $props();

  function flatten(ms: StoneTrace['members']): StoneTrace['members'] {
    return ms.flatMap((m) => (m.children ? [m, ...flatten(m.children)] : [m]));
  }
  let allMembers = $derived(stones.flatMap((s) => flatten(s.members)));
  let total = $derived(allMembers.length);
  let fired = $derived(allMembers.filter((m) => m.status === 'ok').length);
  let silent = $derived(allMembers.filter((m) => m.status === 'silent').length);
  let warn = $derived(allMembers.filter((m) => m.status === 'warn').length);
  let err = $derived(allMembers.filter((m) => m.status === 'error').length);

  let wall = $derived(wallSeconds == null
    ? '—'
    : wallSeconds < 1 ? `${Math.round(wallSeconds * 1000)}ms` : `${wallSeconds.toFixed(1)}s`);
</script>

<div class="rh">
  <span class="rh-item"><strong>{stones.length}</strong> Stones</span>
  <span class="rh-sep">·</span>
  <span class="rh-item"><strong>{fired}/{total}</strong> functions fired</span>
  <span class="rh-sep">·</span>
  <span class="rh-item"><strong>{cards.length}</strong> evidence card{cards.length === 1 ? '' : 's'}</span>
  <span class="rh-sep">·</span>
  <span class="rh-item"><strong>{wall}</strong> wall-clock</span>
  {#if cacheHit != null}
    <span class="rh-sep">·</span>
    <span class="rh-item"><strong>{Math.round(cacheHit * 100)}%</strong> cache</span>
  {/if}
  {#if silent > 0}
    <span class="rh-sep">·</span>
    <span class="rh-item rh-silent">{silent} silent</span>
  {/if}
  {#if warn > 0}
    <span class="rh-sep">·</span>
    <span class="rh-item rh-warn">{warn} warn</span>
  {/if}
  {#if err > 0}
    <span class="rh-sep">·</span>
    <span class="rh-item rh-err">{err} error</span>
  {/if}
</div>

<style>
  .rh {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--s-2);
    padding: var(--s-2) var(--s-4);
    background: var(--paper-deep);
    border-top: 1px solid var(--rule-soft);
    border-bottom: 1px solid var(--rule-soft);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    letter-spacing: 0.04em;
  }
  .rh-item strong {
    font-weight: 600;
    color: var(--ink);
    margin-right: 2px;
  }
  .rh-sep { opacity: 0.5; }
  .rh-silent { color: var(--ink-tertiary); }
  .rh-warn { color: #B7791F; }
  .rh-err { color: #B91C1C; }
</style>
