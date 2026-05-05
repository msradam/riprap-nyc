<script lang="ts">
  import type { Card, ForecastBand } from '$lib/types/card';
  let { card }: { card: Card } = $props();

  const W = 240, H = 88, PAD = 6;

  let data = $derived<ForecastBand[]>(card.forecast ?? []);
  let xs = $derived(data.map((_, i) => PAD + (i / Math.max(data.length - 1, 1)) * (W - PAD * 2)));
  let max = $derived(Math.max(...data.map((d) => d.high), 1));

  function y(v: number): number {
    return H - PAD - (v / max) * (H - PAD * 2 - 12);
  }

  let midD = $derived(xs.map((x, i) => `${i ? 'L' : 'M'} ${x} ${y(data[i].mid)}`).join(' '));

  let areaD = $derived.by(() => {
    if (!data.length) return '';
    const lows = xs.map((x, i) => `${x} ${y(data[i].low)}`).join(' L ');
    const highs = [...xs].reverse()
      .map((x, idx) => `${x} ${y(data[data.length - 1 - idx].high)}`)
      .join(' L ');
    return `M ${lows} L ${highs} Z`;
  });
</script>

<div class="body body-forecast">
  <svg viewBox="0 0 {W} {H}" width="100%" height={H} aria-hidden="true">
    <path d={areaD} fill="var(--tier-{card.tier})" fill-opacity="0.18" />
    <path d={midD} fill="none" stroke="var(--tier-{card.tier})" stroke-width="1.5" />
    {#each data as d, i}
      <circle cx={xs[i]} cy={y(d.mid)} r="2.2" fill="var(--tier-{card.tier})" />
      <text x={xs[i]} y={H - 1} font-size="9" font-family="IBM Plex Mono"
            text-anchor="middle" fill="#6B6B6B">{d.year}</text>
    {/each}
  </svg>
  {#if card.sub}<div class="body-sub">{card.sub}</div>{/if}
</div>

<style>
  .body-forecast { padding: var(--s-3) var(--s-4) var(--s-3); }
  :global(.fc.is-compact) .body-forecast { padding: var(--s-2) var(--s-3); }
  svg { display: block; }
  .body-sub {
    margin-top: var(--s-2);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    line-height: 1.5;
  }
</style>
