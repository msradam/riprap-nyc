<script lang="ts">
  /**
   * v0.4.2 §11 — t=0 to ~1.4s pulse state for the briefing region.
   * Shown during the geocode → fan-out window before any reconciler tokens
   * arrive. Section heads visible-but-empty; pulses respect
   * prefers-reduced-motion (handled in tokens.css media query).
   */
  const SECTIONS: Array<{ n: string; label: string }> = [
    { n: '01', label: 'Status' },
    { n: '02', label: 'Empirical evidence' },
    { n: '03', label: 'Modeled scenarios' },
    { n: '04', label: 'Policy context' }
  ];
</script>

<div
  class="skeleton-brief"
  role="status"
  aria-live="polite"
  aria-label="Loading briefing — geocode complete, dispatching specialists"
>
  <div class="skeleton-status">
    <span class="skeleton-pulse" style:width="62%"></span>
    <span class="skeleton-pulse skeleton-pulse-meta" style:width="40%"></span>
  </div>
  {#each SECTIONS as s (s.n)}
    <div class="skeleton-section">
      <div class="skeleton-head">
        <span class="skeleton-num">{s.n}</span>
        <span class="skeleton-label">{s.label}</span>
        <span class="skeleton-spinner" aria-hidden="true">▍</span>
      </div>
      <span class="skeleton-pulse" style:width="92%"></span>
      <span class="skeleton-pulse" style:width="78%"></span>
      <span class="skeleton-pulse" style:width="85%"></span>
    </div>
  {/each}
</div>
