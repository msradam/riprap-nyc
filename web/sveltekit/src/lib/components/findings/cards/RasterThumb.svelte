<script lang="ts">
  import type { RasterKind } from '$lib/types/card';

  /** Hand-drawn SVG approximations of each raster layer's conventional
   *  palette. Replace with real MapLibre tile snapshots when the tile
   *  pipeline is wired up. Mirrors findings.jsx → RasterThumb exactly. */
  let { kind }: { kind?: RasterKind } = $props();

  const W = 240, H = 120;
</script>

{#if kind === 'stormwater'}
  <svg viewBox="0 0 {W} {H}" width="100%" height={H} aria-hidden="true">
    <rect width={W} height={H} fill="#E8ECF2" />
    <g stroke="#D9D6CC" stroke-width="0.6">
      <line x1="0" y1="40" x2={W} y2="40" />
      <line x1="0" y1="80" x2={W} y2="80" />
      <line x1="60" y1="0" x2="60" y2={H} />
      <line x1="160" y1="0" x2="160" y2={H} />
    </g>
    <path d="M20 50 Q 60 38 90 56 Q 120 76 150 64 Q 180 50 180 86 Q 130 100 70 96 Q 30 92 20 76 Z"
          fill="rgba(42,111,168,0.32)" stroke="#2A6FA8" stroke-width="0.7" />
    <path d="M40 60 Q 80 54 110 70 Q 140 84 160 78 Q 165 90 130 92 Q 80 90 50 82 Z"
          fill="rgba(11,83,148,0.36)" stroke="#0B5394" stroke-width="0.6" />
    <circle cx="120" cy="74" r="3.2" fill="#005EA2" stroke="#F4F6F9" stroke-width="1.3" />
    <text x={W - 6} y={H - 5} font-size="8" font-family="IBM Plex Mono" text-anchor="end" fill="#6B6B6B">2.13 in/hr · MOD</text>
  </svg>
{:else if kind === 'stormwater-dry'}
  <svg viewBox="0 0 {W} {H}" width="100%" height={H} aria-hidden="true">
    <rect width={W} height={H} fill="#E8ECF2" />
    <g stroke="#D9D6CC" stroke-width="0.6">
      <line x1="0" y1="40" x2={W} y2="40" />
      <line x1="0" y1="80" x2={W} y2="80" />
      <line x1="60" y1="0" x2="60" y2={H} />
      <line x1="160" y1="0" x2="160" y2={H} />
    </g>
    <path d="M180 92 Q 200 88 215 96 Q 220 105 200 104 Q 185 102 180 96 Z"
          fill="rgba(42,111,168,0.18)" stroke="#2A6FA8" stroke-width="0.5" stroke-dasharray="2 2" />
    <circle cx="120" cy="60" r="3.2" fill="#005EA2" stroke="#F4F6F9" stroke-width="1.3" />
    <text x={W - 6} y={H - 5} font-size="8" font-family="IBM Plex Mono" text-anchor="end" fill="#6B6B6B">no ponding · MOD</text>
  </svg>
{:else if kind === 'prithvi'}
  <svg viewBox="0 0 {W} {H}" width="100%" height={H} aria-hidden="true">
    <defs>
      <pattern id="rt-s2-rgb" x="0" y="0" width="6" height="6" patternUnits="userSpaceOnUse">
        <rect width="6" height="6" fill="#7A8E6A" />
        <rect x="0" y="0" width="3" height="3" fill="#8D9C7A" />
        <rect x="3" y="3" width="3" height="3" fill="#69795D" />
      </pattern>
    </defs>
    <rect width={W} height={H} fill="url(#rt-s2-rgb)" />
    <rect x="0" y="55" width={W} height="6" fill="#A8A496" />
    <rect x="115" y="0" width="8" height={H} fill="#A8A496" />
    <ellipse cx="50" cy="92" rx="6" ry="3" fill="#2A6FA8" fill-opacity="0.65" />
    <text x="6" y="14" font-size="9" font-family="IBM Plex Mono" fill="#F4F6F9">PRITHVI · 0.3%</text>
    <text x={W - 6} y={H - 5} font-size="8" font-family="IBM Plex Mono" text-anchor="end" fill="#F4F6F9">scene 2026-05-02</text>
  </svg>
{:else if kind === 'lulc'}
  <svg viewBox="0 0 {W} {H}" width="100%" height={H} aria-hidden="true">
    <rect width={W} height={H} fill="#E8ECF2" />
    <rect x="0" y="0" width="80" height="60" fill="#C66" />
    <rect x="80" y="0" width="60" height="60" fill="#C66" />
    <rect x="140" y="0" width="100" height="38" fill="#C66" />
    <rect x="140" y="38" width="100" height="22" fill="#5B7FB4" />
    <rect x="0" y="60" width="100" height="60" fill="#C66" />
    <rect x="100" y="60" width="50" height="40" fill="#5B8A4A" />
    <rect x="150" y="60" width="50" height="60" fill="#D9C75A" />
    <rect x="200" y="60" width="40" height="60" fill="#C66" />
    <rect x="100" y="100" width="50" height="20" fill="#A89A78" />
    <text x="6" y="14" font-size="9" font-family="IBM Plex Mono" fill="#F4F6F9">LULC · TerraMind</text>
    <text x={W - 6} y={H - 5} font-size="8" font-family="IBM Plex Mono" text-anchor="end" fill="#F4F6F9">scene 2026-05-02</text>
  </svg>
{:else if kind === 'buildings'}
  <svg viewBox="0 0 {W} {H}" width="100%" height={H} aria-hidden="true">
    <rect width={W} height={H} fill="#3A3A38" />
    {#each [
      [10,10,28,18],[42,10,30,16],[78,10,40,22],[124,10,32,18],[162,10,30,18],[198,10,32,18],
      [10,32,28,16],[42,30,30,18],[124,32,32,16],[162,32,30,16],[198,32,32,16],
      [10,55,28,18],[42,55,30,18],[78,55,40,18],[124,55,32,18],[162,55,30,18],[198,55,32,18],
      [10,80,28,16],[42,80,30,16],[78,80,40,16],[124,80,32,16],[162,80,30,16],
      [10,100,28,12],[42,100,30,12],[78,100,40,12]
    ] as r}
      <rect x={r[0]} y={r[1]} width={r[2]} height={r[3]}
            fill="rgba(42,111,168,0.55)" stroke="#2A6FA8" stroke-width="0.4" />
    {/each}
    <text x="6" y="14" font-size="9" font-family="IBM Plex Mono" fill="#F4F6F9">BLDG · TerraMind</text>
    <text x={W - 6} y={H - 5} font-size="8" font-family="IBM Plex Mono" text-anchor="end" fill="#F4F6F9">36.2% built</text>
  </svg>
{:else}
  <div class="thumb-placeholder">raster preview</div>
{/if}

<style>
  svg { display: block; }
  .thumb-placeholder {
    height: 120px;
    background: var(--paper-deep);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--ink-tertiary);
    font-family: var(--font-mono);
    font-size: 11px;
    border: 1px dashed var(--rule-soft);
  }
</style>
