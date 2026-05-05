<script lang="ts">
  interface Props { data: number[]; color: string; }
  let { data, color }: Props = $props();
  const w = 180, h = 36;
  let max = $derived(Math.max(...data, 1));
  let n = $derived(data.length);
</script>

<svg viewBox="0 0 {w} {h}" width="100%" height={h} preserveAspectRatio="none" aria-hidden="true">
  {#each data as v, i (i)}
    <rect
      x={(i / n) * w + 0.5}
      y={h - (v / max) * h}
      width={Math.max(2, w / n - 1.5)}
      height={(v / max) * h}
      fill={color}
    />
  {/each}
</svg>
