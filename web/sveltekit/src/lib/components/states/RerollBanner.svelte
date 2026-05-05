<script lang="ts">
  /**
   * v0.4.2 §11 — Mellea regrounding banner shown when the rejection
   * sampler advances to attempt 2+. The previous draft is dimmed at 60%
   * opacity below this banner (caller renders that block separately so
   * we don't need to know its content).
   */
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';

  interface Props {
    attempt?: number;
    max?: number;
  }

  let { attempt = 2, max = 3 }: Props = $props();
</script>

<div class="reroll-banner" role="status" aria-live="polite">
  <TierGlyph tier="modeled" size={11} color="var(--tier-modeled)" />
  <div class="reroll-body">
    <span class="reroll-head">Regenerating to satisfy citation grounding</span>
    <span class="reroll-sub">Mellea reconciler · attempt {attempt} of {max} · previous draft dimmed below</span>
  </div>
  <span class="reroll-spinner" aria-hidden="true">↻</span>
</div>
