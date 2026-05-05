<script lang="ts">
  import type { StoneMember } from '$lib/types/card';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
  import Self from './ProvenanceTrace.svelte';

  /** Indented specialist tree. Each row: status pip · mono id · italic-
   *  serif name · note. Recursive via self-import (svelte:self is
   *  deprecated in Svelte 5). */
  let { members, depth = 0 }: { members: StoneMember[]; depth?: number } = $props();

  /** v0.4.5 status pip — five distinct shapes per V0.4.5_SPEC.md §1.
   *
   *    fired             ● solid square (tier-colored)
   *    silent_by_design  ○ open circle (neutral)
   *    warned            ▲ solid triangle (warn ochre)
   *    errored           ■ solid filled (red)
   *    not_invoked       □ hollow gray square
   */
  function pip(status: StoneMember['status']): string {
    return ({
      fired: '●',
      silent_by_design: '○',
      warned: '▲',
      errored: '■',
      not_invoked: '□',
    } as const)[status];
  }
  function pipColorVar(m: StoneMember): string {
    if (m.status === 'warned') return '#B7791F';
    if (m.status === 'errored') return '#B91C1C';
    if (m.status === 'silent_by_design') return 'var(--ink-tertiary)';
    if (m.status === 'not_invoked') return 'var(--ink-tertiary)';
    if (m.tier) return `var(--tier-${m.tier})`;
    return 'var(--ink)';
  }
</script>

<ul class="prov-tree" style="--depth: {depth};">
  {#each members as m (m.id)}
    <li class="prov-row prov-status-{m.status}">
      <span class="prov-pip" style="color: {pipColorVar(m)};" aria-hidden="true">{pip(m.status)}</span>
      <span class="prov-id">{m.id}</span>
      {#if m.tier}
        <span class="prov-tier">
          <TierGlyph tier={m.tier} size={9} color={`var(--tier-${m.tier})`} />
        </span>
      {/if}
      <span class="prov-name">{m.name}</span>
      {#if m.note}<span class="prov-note">— {m.note}</span>{/if}
      {#if m.ms != null}<span class="prov-ms">{m.ms < 1000 ? `${m.ms}ms` : `${(m.ms / 1000).toFixed(1)}s`}</span>{/if}
    </li>
    {#if m.children?.length}
      <li class="prov-children">
        <Self members={m.children} depth={depth + 1} />
      </li>
    {/if}
  {/each}
</ul>

<style>
  .prov-tree {
    list-style: none;
    margin: 0;
    padding: 0;
    padding-left: calc(var(--depth, 0) * 16px);
  }
  .prov-row {
    display: grid;
    grid-template-columns: 14px max-content max-content 1fr auto;
    gap: var(--s-2);
    align-items: baseline;
    padding: 3px 0;
    font-family: var(--font-mono);
    font-size: 11px;
    border-bottom: 1px dotted var(--rule-soft);
  }
  .prov-row:last-child { border-bottom: 0; }
  .prov-pip {
    text-align: center;
    font-size: 10px;
    line-height: 1;
  }
  .prov-id {
    color: var(--ink);
    letter-spacing: 0.04em;
    text-transform: lowercase;
  }
  .prov-tier {
    display: inline-flex;
    align-items: center;
  }
  .prov-name {
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 13px;
    color: var(--ink);
  }
  .prov-note {
    font-family: var(--font-sans);
    font-size: 12px;
    color: var(--ink-tertiary);
  }
  .prov-ms {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--ink-tertiary);
  }
  /* v0.4.5 status row treatments */
  .prov-status-silent_by_design .prov-name {
    color: var(--ink-tertiary);
    font-style: italic;
  }
  .prov-status-warned .prov-name { color: #B7791F; }
  .prov-status-errored .prov-name { color: #B91C1C; }
  .prov-status-errored .prov-pip { font-weight: bold; }
  .prov-status-not_invoked .prov-name {
    color: var(--ink-tertiary);
    font-style: italic;
  }
  .prov-status-not_invoked .prov-id {
    color: var(--ink-tertiary);
    opacity: 0.6;
  }
  .prov-children { padding: 0; }
</style>
