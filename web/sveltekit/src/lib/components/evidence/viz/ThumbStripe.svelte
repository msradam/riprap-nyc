<script lang="ts">
  interface Props { kind: 'stormwater' | 'synthetic'; }
  let { kind }: Props = $props();
</script>

<svg viewBox="0 0 220 110" width="100%" height="110" aria-hidden="true" style="display: block; background: #E8ECF2;">
  <defs>
    <pattern id="thumb-{kind}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="6" height="6" fill={kind === 'synthetic' ? 'rgba(42,111,168,0.18)' : 'rgba(42,111,168,0.30)'} />
      <line x1="0" y1="0" x2="0" y2="6" stroke={kind === 'synthetic' ? '#2A6FA8' : '#0B5394'} stroke-width="0.8" />
    </pattern>
  </defs>
  {#if kind === 'stormwater'}
    <rect x="0" y="0" width="220" height="110" fill="#F4F6F9" />
    <path d="M0 60 L60 55 L120 70 L180 80 L220 78 L220 110 L0 110 Z" fill="rgba(42,111,168,0.30)" stroke="#2A6FA8" stroke-width="1" />
    <path d="M0 75 L60 72 L120 85 L180 92 L220 90 L220 110 L0 110 Z" fill="rgba(42,111,168,0.20)" stroke="#2A6FA8" stroke-width="0.8" />
    <circle cx="100" cy="68" r="4" fill="#005EA2" stroke="#F4F6F9" stroke-width="1.5" />
  {:else}
    <rect x="0" y="0" width="220" height="110" fill="url(#thumb-{kind})" />
    <text x="8" y="100" font-family="IBM Plex Mono" font-size="9" fill="#2A6FA8">SYN · 2025-09-14</text>
  {/if}
</svg>
