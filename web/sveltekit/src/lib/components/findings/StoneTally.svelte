<script lang="ts">
  import type { StoneMember } from '$lib/types/card';

  /** Run-tally chip in the Stone-region header. Mirrors findings.jsx
   *  StoneTally44: shows card count, fired count, silent / warn / error
   *  counts (when nonzero), and the heaviest-specialist runtime. */
  interface Props {
    cardCount: number;
    members: StoneMember[];
  }

  let { cardCount, members }: Props = $props();

  function flatten(ms: StoneMember[]): StoneMember[] {
    return ms.flatMap((m) => (m.children ? [m, ...flatten(m.children)] : [m]));
  }
  let flat = $derived(flatten(members));
  let fired = $derived(flat.filter((m) => m.status === 'ok').length);
  let silent = $derived(flat.filter((m) => m.status === 'silent').length);
  let warn = $derived(flat.filter((m) => m.status === 'warn').length);
  let err = $derived(flat.filter((m) => m.status === 'error').length);
  let ms = $derived(members.reduce((a, m) => Math.max(a, m.ms ?? 0), 0));

  function fmtMs(x: number): string {
    if (x === 0) return '—';
    if (x < 1000) return `${x}ms`;
    return `${(x / 1000).toFixed(1)}s`;
  }
</script>

<span class="tally">
  <span class="cards">{cardCount} card{cardCount === 1 ? '' : 's'}</span>
  <span class="sep">·</span>
  <span class="fired"><strong>{fired}</strong> fired</span>
  {#if silent > 0}
    <span class="sep">·</span>
    <span class="silent"><strong>{silent}</strong> silent</span>
  {/if}
  {#if warn > 0}
    <span class="sep">·</span>
    <span class="warn"><strong>{warn}</strong> warn</span>
  {/if}
  {#if err > 0}
    <span class="sep">·</span>
    <span class="err"><strong>{err}</strong> error</span>
  {/if}
  <span class="sep">·</span>
  <span class="ms"><strong>{fmtMs(ms)}</strong></span>
</span>

<style>
  .tally {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    letter-spacing: 0.04em;
    flex-wrap: wrap;
  }
  strong {
    font-weight: 600;
    color: var(--ink);
  }
  .silent strong { color: var(--ink-tertiary); }
  .warn strong { color: #B7791F; }
  .err strong { color: #B91C1C; }
  .sep { color: var(--ink-tertiary); opacity: 0.6; }
</style>
