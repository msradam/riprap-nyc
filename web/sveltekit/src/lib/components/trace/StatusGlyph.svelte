<script lang="ts">
  import type { TraceStatus } from '$lib/types/trace';
  interface Props { status: TraceStatus; }
  let { status }: Props = $props();
</script>

{#if status === 'fan'}
  <span class="trace-status-glyph" aria-label="fan-out">⤳</span>
{:else if status === 'merge'}
  <span class="trace-status-glyph" aria-label="merge">⤺</span>
{:else if status === 'silent'}
  <svg width="9" height="9" viewBox="0 0 9 9" aria-label="silent">
    <rect x="0.75" y="0.75" width="7.5" height="7.5" fill="transparent" stroke="#6B6B6B" stroke-width="1.5" />
  </svg>
{:else if status === 'error'}
  <svg width="9" height="9" viewBox="0 0 9 9" aria-label="error">
    <rect x="0.75" y="0.75" width="7.5" height="7.5" fill="#005EA2" />
  </svg>
{:else}
  <svg width="9" height="9" viewBox="0 0 9 9" aria-label="ok">
    <rect x="0.75" y="0.75" width="7.5" height="7.5" fill="#0B5394" />
  </svg>
{/if}
