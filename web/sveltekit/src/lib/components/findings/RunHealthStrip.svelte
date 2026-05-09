<script lang="ts">
  import type { Card, StoneTrace } from '$lib/types/card';
  import type { EmissionsSummary } from '$lib/client/agentStream';

  /** Top-of-Findings status row. Mirrors findings.jsx RunHealth44:
   *  Stones · functions fired · evidence cards · wall-clock · silent /
   *  warn / error chips when nonzero. Also surfaces a compact emissions
   *  chip (mWh + tokens) when the backend reports a per-call ledger. */
  interface Props {
    cards: Card[];
    stones: StoneTrace[];
    wallSeconds?: number;
    cacheHit?: number;
    emissions?: EmissionsSummary;
  }

  let { cards, stones, wallSeconds, cacheHit, emissions }: Props = $props();

  function flatten(ms: StoneTrace['members']): StoneTrace['members'] {
    return ms.flatMap((m) => (m.children ? [m, ...flatten(m.children)] : [m]));
  }
  let allMembers = $derived(stones.flatMap((s) => flatten(s.members)));
  let total = $derived(allMembers.length);
  // v0.4.5 split: see SpecialistStatus in lib/types/card.ts.
  let fired = $derived(
    allMembers.filter((m) => m.status === 'fired' || m.status === 'warned').length
  );
  let silent = $derived(allMembers.filter((m) => m.status === 'silent_by_design').length);
  let warn = $derived(allMembers.filter((m) => m.status === 'warned').length);
  let err = $derived(allMembers.filter((m) => m.status === 'errored').length);
  let notInvoked = $derived(allMembers.filter((m) => m.status === 'not_invoked').length);

  let wall = $derived(wallSeconds == null
    ? '—'
    : wallSeconds < 1 ? `${Math.round(wallSeconds * 1000)}ms` : `${wallSeconds.toFixed(1)}s`);

  // Format emissions: prefer mWh under 100, else Wh; tokens with K-suffix.
  let emEnergy = $derived.by(() => {
    if (!emissions || emissions.total_wh === 0) return null;
    const wh = emissions.total_wh;
    if (wh < 0.1) return `${emissions.total_mwh.toFixed(1)} mWh`;
    return `${wh.toFixed(2)} Wh`;
  });
  let emTokens = $derived.by(() => {
    const t = emissions?.tokens?.total;
    if (!t) return null;
    return t >= 1000 ? `${(t / 1000).toFixed(1)}K tok` : `${t} tok`;
  });
  let emHardware = $derived.by(() => {
    if (!emissions) return null;
    const labels = Object.values(emissions.by_hardware).map(h => h.label);
    return labels.length === 1 ? labels[0] : labels.join(' + ');
  });
  // Fraction of calls that came back with a real NVML reading (vs.
  // data-sheet fallback). Surfaced as a small ✓ / ~ badge so the
  // viewer can tell whether the number is measured or estimated.
  let emMeasuredFrac = $derived(
    emissions && emissions.n_calls > 0
      ? (emissions.n_measured ?? 0) / emissions.n_calls
      : 0
  );
  let emMeasuredIcon = $derived(
    emEnergy == null
      ? ''
      : emMeasuredFrac >= 0.9
        ? '✓'           // all (or nearly all) calls measured on GPU
        : emMeasuredFrac > 0
          ? '◐'         // partial coverage
          : '~'         // pure data-sheet estimate
  );
  let emTooltip = $derived.by(() => {
    if (!emissions) return '';
    const measuredLine = emissions.n_measured != null
      ? `${emissions.n_measured}/${emissions.n_calls} calls measured on GPU (others use data-sheet estimate)`
      : '';
    const lines = [
      `${emissions.n_calls} inference calls — ${emissions.total_joules} J total`,
      emHardware ? `Hardware: ${emHardware}` : '',
      measuredLine,
      emissions.tokens.total ? `Tokens: ${emissions.tokens.prompt ?? 0} prompt + ${emissions.tokens.completion ?? 0} completion` : '',
      emissions.method,
    ].filter(Boolean);
    return lines.join('\n');
  });
</script>

<div class="rh">
  <span class="rh-item"><strong>{stones.length}</strong> Stones</span>
  <span class="rh-sep">·</span>
  <span class="rh-item"><strong>{fired}</strong> fired</span>
  {#if silent > 0}
    <span class="rh-sep">·</span>
    <span class="rh-item rh-silent"><strong>{silent}</strong> silent</span>
  {/if}
  {#if warn > 0}
    <span class="rh-sep">·</span>
    <span class="rh-item rh-warn"><strong>{warn}</strong> warned</span>
  {/if}
  {#if err > 0}
    <span class="rh-sep">·</span>
    <span class="rh-item rh-err"><strong>{err}</strong> errored</span>
  {/if}
  {#if notInvoked > 0}
    <span class="rh-sep">·</span>
    <span class="rh-item rh-notinvoked"><strong>{notInvoked}</strong> not invoked</span>
  {/if}
  <span class="rh-sep">·</span>
  <span class="rh-item"><strong>{cards.length}</strong> evidence card{cards.length === 1 ? '' : 's'}</span>
  <span class="rh-sep">·</span>
  <span class="rh-item"><strong>{wall}</strong> wall-clock</span>
  {#if cacheHit != null}
    <span class="rh-sep">·</span>
    <span class="rh-item"><strong>{Math.round(cacheHit * 100)}%</strong> cache</span>
  {/if}
  <span class="rh-sep">·</span>
  <span class="rh-item rh-total"><strong>{total}</strong> registered</span>
  {#if emEnergy}
    <span class="rh-sep">·</span>
    <span class="rh-item rh-em" title={emTooltip}>
      <span class="rh-em-icon" aria-hidden="true">{emMeasuredIcon}</span>
      <strong>{emEnergy}</strong> inference
      {#if emTokens}<span class="rh-em-tok">/ {emTokens}</span>{/if}
    </span>
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
  .rh-notinvoked { color: var(--ink-tertiary); font-style: italic; }
  .rh-total strong { color: var(--ink-tertiary); }
  .rh-em {
    cursor: help;
    color: var(--ink-secondary);
  }
  .rh-em strong { color: var(--ink); }
  .rh-em-tok { margin-left: 4px; opacity: 0.75; }
  .rh-em-icon {
    margin-right: 4px;
    font-size: 10px;
    color: var(--ink-tertiary);
  }
</style>
