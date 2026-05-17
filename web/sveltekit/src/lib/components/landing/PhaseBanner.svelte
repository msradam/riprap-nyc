<script lang="ts">
  /** PhaseBanner — GOV.UK / USWDS open-beta banner.
   *
   *  Communicates that methodology and source attribution are stable,
   *  but per-city coverage is still expanding. Conventional pattern in
   *  federal civic-tech sites (cf. gov.uk, sam.gov, login.gov phase
   *  banners).
   */
  interface Props {
    /** Phase label — "Beta", "Alpha", etc. Defaults to "Beta". */
    phase?: string;
    /** Where the "Send feedback" link goes. Defaults to the GitHub
     *  issues page. */
    feedbackHref?: string;
  }
  let {
    phase = 'Beta',
    feedbackHref = 'https://github.com/msradam/riprap-nyc/issues/new/choose',
  }: Props = $props();
</script>

<div class="phase-banner" role="region" aria-label="Phase banner">
  <span class="phase-tag">{phase}</span>
  <span>
    This is open beta. Methodology and source attribution are stable.
    Per-city coverage is expanding.
    <a href={feedbackHref} target="_blank" rel="noopener">Send feedback →</a>
  </span>
</div>

<style>
  .phase-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 20px;
    background: var(--paper-deep);
    border-bottom: 1px solid var(--rule-soft);
    font-family: var(--font-sans);
    font-size: 13px;
    color: var(--ink-secondary);
  }
  .phase-tag {
    display: inline-block;
    padding: 2px 8px;
    background: var(--accent);
    color: white;
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }
  .phase-banner a {
    color: var(--accent);
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .phase-banner a:hover { text-decoration-thickness: 2px; }
</style>
