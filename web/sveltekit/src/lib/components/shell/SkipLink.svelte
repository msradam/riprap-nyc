<script lang="ts">
  /** SkipLink — USWDS-canonical pattern.
   *
   *  Keyboard users land on the first focusable element; "Skip to main
   *  content" lets them bypass repeated nav. Hidden visually until
   *  focused (NOT display:none, which removes from a11y tree).
   *
   *  Existing per-route `Skip to briefing / map / trace` links in
   *  the app shell continue to work; this one is the top-level
   *  canonical that USWDS audits look for.
   */
  interface Props {
    /** Anchor id to skip to. Defaults to `main-content`. */
    target?: string;
    label?: string;
  }
  let {
    target = 'main-content',
    label = 'Skip to main content',
  }: Props = $props();
</script>

<a class="skip-link" href="#{target}">{label}</a>

<style>
  .skip-link {
    position: absolute;
    left: -9999px;
    top: 8px;
    padding: 8px 12px;
    background: var(--ink);
    color: var(--paper);
    font-family: var(--font-mono);
    font-size: 13px;
    z-index: 1000;
    text-decoration: none;
  }
  .skip-link:focus,
  .skip-link:focus-visible {
    left: 8px;
    outline: 3px solid var(--accent);
    outline-offset: 2px;
  }
</style>
