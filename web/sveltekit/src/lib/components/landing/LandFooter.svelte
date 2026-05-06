<script lang="ts">
  /** Landing-page footer. Tier legend swatches + a build line. The
   *  in-app AppFooter has more detail; this one is intentionally tighter
   *  so the landing page closes cleanly. */
</script>

<footer class="land-footer">
  <span class="land-footer-tiers">
    <span class="land-footer-tier"><span class="lm-sw lm-sw-emp"></span>empirical</span>
    <span class="land-footer-tier"><span class="lm-sw lm-sw-mod"></span>modeled</span>
    <span class="land-footer-tier"><span class="lm-sw lm-sw-prx"></span>proxy</span>
    <span class="land-footer-tier"><span class="lm-sw lm-sw-syn"></span>synthetic</span>
  </span>
  <span class="land-footer-build">Riprap v0.4.6 · NYC OpenData · FEMA NFHL · USGS · NPCC4 · Dam mark by Chintuza, Noun Project (CC-BY)</span>
</footer>

<style>
  .land-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    padding: 16px 32px;
    border-top: 1px solid var(--rule-soft);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    letter-spacing: 0.02em;
  }
  .land-footer-tiers {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }
  .land-footer-tier {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .lm-sw { display: inline-block; width: 8px; height: 8px; }
  .lm-sw-emp { background: var(--tier-empirical); }
  .lm-sw-mod {
    background: rgba(42, 111, 168, 0.4);
    border: 1px dashed var(--tier-modeled);
  }
  .lm-sw-prx {
    background: transparent;
    border: 1px solid #6B6B6B;
    border-radius: 50%;
  }
  .lm-sw-syn {
    background: rgba(42, 111, 168, 0.25);
    background-image: repeating-linear-gradient(
      45deg,
      transparent 0,
      transparent 2px,
      var(--tier-synthetic) 2px,
      var(--tier-synthetic) 3px
    );
    border: 1px solid var(--tier-synthetic);
  }
</style>
