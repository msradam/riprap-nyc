<script lang="ts">
  import type { Card } from '$lib/types/card';
  let { card }: { card: Card } = $props();

  const W = 240, H = 84, PAD = 6;

  // Synthetic surge curve: harmonic baseline + storm pulse around peak.
  // Mirrors findings.jsx exactly so the visual matches the prototype.
  const ts = $derived(card.timeseries ?? { hours: 96, peak: { x: 38, y: 47 }, peakLabel: '' });
  const points = $derived(buildPoints(ts));
  const yScale = $derived(buildScale(points, ts));
  const pathD = $derived(buildPath(points, yScale));

  type Pt = { x: number; y: number };

  function buildPoints(t: { hours: number; peak: { x: number; y: number } }): Pt[] {
    const out: Pt[] = [];
    for (let i = 0; i <= t.hours; i++) {
      const harmonic = 6 * Math.sin((i / 12.42) * Math.PI * 2);
      const pulse = 38 * Math.exp(-Math.pow((i - t.peak.x) / 12, 2));
      out.push({ x: i, y: harmonic + pulse + 4 });
    }
    return out;
  }

  function buildScale(pts: Pt[], t: { hours: number; peak: { x: number; y: number } }) {
    const maxY = Math.max(...pts.map(p => p.y), t.peak.y);
    const minY = Math.min(...pts.map(p => p.y), -10);
    return {
      sx: (i: number) => PAD + (i / t.hours) * (W - PAD * 2),
      sy: (v: number) => H - PAD - 14 - ((v - minY) / (maxY - minY)) * (H - PAD * 2 - 14),
    };
  }

  function buildPath(pts: Pt[], s: { sx: (i: number) => number; sy: (v: number) => number }): string {
    return pts.map((p, i) => `${i ? 'L' : 'M'} ${s.sx(p.x)} ${s.sy(p.y)}`).join(' ');
  }
</script>

<div class="body body-timeseries">
  <div class="ts-header">
    {#if card.headline}
      <span class="headline" style="color: var(--tier-{card.tier});">{card.headline}</span>
    {/if}
    {#if card.subhead}<span class="subhead">{card.subhead}</span>{/if}
  </div>
  <svg viewBox="0 0 {W} {H}" width="100%" height={H} aria-hidden="true">
    <line x1={PAD} y1={yScale.sy(0)} x2={W - PAD} y2={yScale.sy(0)}
          stroke="#C9C9C5" stroke-width="0.5" stroke-dasharray="2 2" />
    <path d={pathD} fill="none" stroke="var(--tier-{card.tier})" stroke-width="1.4" />
    <circle cx={yScale.sx(ts.peak.x)} cy={yScale.sy(ts.peak.y)} r="3" fill="var(--tier-{card.tier})" />
    <text x={yScale.sx(ts.peak.x)} y={yScale.sy(ts.peak.y) - 6}
          font-size="9" font-family="IBM Plex Mono"
          text-anchor="middle" fill="var(--tier-{card.tier})">{ts.peakLabel}</text>
    <text x={PAD} y={H - 2} font-size="8" font-family="IBM Plex Mono" fill="#6B6B6B">now</text>
    <text x={W - PAD} y={H - 2} font-size="8" font-family="IBM Plex Mono"
          text-anchor="end" fill="#6B6B6B">+{ts.hours}h</text>
  </svg>
  {#if card.spatialNote || card.sub}
    <div class="body-sub">
      {#if card.spatialNote}<span class="spatial-note">{card.spatialNote}</span>{/if}
      {#if card.sub}<span>{card.sub}</span>{/if}
    </div>
  {/if}
</div>

<style>
  .body-timeseries {
    padding: var(--s-3) var(--s-4) var(--s-3);
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }
  :global(.fc.is-compact) .body-timeseries { padding: var(--s-2) var(--s-3); }
  .ts-header {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: var(--s-2);
  }
  .headline {
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 22px;
    font-weight: 500;
    line-height: 1.1;
  }
  .subhead {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    letter-spacing: 0.04em;
  }
  svg { display: block; }
  .body-sub {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    line-height: 1.5;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .spatial-note {
    color: var(--accent);
    font-style: italic;
  }
</style>
