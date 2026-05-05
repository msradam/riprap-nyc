<script lang="ts">
  interface Point { year: number; low: number; mid: number; high: number; }
  interface Props { data: Point[]; color: string; }
  let { data, color }: Props = $props();

  const w = 220, h = 80, pad = 4;

  let xs = $derived(data.map((_, i) => pad + (i / (data.length - 1)) * (w - pad * 2)));
  let max = $derived(Math.max(...data.map((d) => d.high)));
  function y(v: number) { return h - pad - (v / max) * (h - pad * 2); }
  let midPath = $derived(xs.map((x, i) => `${i ? 'L' : 'M'} ${x} ${y(data[i].mid)}`).join(' '));
  let areaPath = $derived(() => {
    const top = xs.map((x, i) => `${x} ${y(data[i].low)}`).join(' L ');
    const bot = [...xs].map((x, i) => ({ x, hi: y(data[i].high) })).reverse()
      .map((r) => `${r.x} ${r.hi}`).join(' L ');
    return `M ${top} L ${bot} Z`;
  });
</script>

<svg viewBox="0 0 {w} {h}" width="100%" height={h} aria-hidden="true">
  <path d={areaPath()} fill={color} fill-opacity="0.18" />
  <path d={midPath} fill="none" stroke={color} stroke-width="1.5" />
  {#each data as d, i (i)}
    <g>
      <circle cx={xs[i]} cy={y(d.mid)} r="2" fill={color} />
      <text x={xs[i]} y={h - 1} font-size="9" font-family="IBM Plex Mono" text-anchor="middle" fill="#6B6B6B">{d.year}</text>
    </g>
  {/each}
</svg>
