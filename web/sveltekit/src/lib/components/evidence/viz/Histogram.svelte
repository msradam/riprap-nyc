<script lang="ts">
  import Sparkline from './Sparkline.svelte';
  interface Props { data: number[]; color: string; }
  let { data, color }: Props = $props();
</script>

<Sparkline {data} {color} />
