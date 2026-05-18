<script lang="ts">
  /**
   * v0.4.2 §12 — four canonical error states, each in polite-redirect
   * register. Same tone as cold-start: explanatory, helpful, never
   * alarming. The card announces via aria-live=assertive; first action
   * receives focus (caller wires `bind:focusEl` if needed).
   */
  import type { Tier } from '$lib/types/tier';
  import type { ErrorKey } from '$lib/types/states';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
  import { deployment } from '$lib/stores/deployment.svelte';

  interface Action {
    label: string;
    onClick?: () => void;
    href?: string;
  }

  interface Props {
    state: ErrorKey;
    actions?: Action[];
    /** Override headline / body for context-specific messages. */
    eyebrowOverride?: string;
    headlineOverride?: string;
    bodyOverride?: string;
  }

  let {
    state,
    actions,
    eyebrowOverride,
    headlineOverride,
    bodyOverride
  }: Props = $props();

  interface Spec {
    eyebrow: string;
    headline: string;
    body: string;
    tier: Tier;
    defaultActions: string[];
  }

  // City-name interpolation. The geocoder + all-silent messages
  // referenced NYC / FloodNet NYC / Sandy by name; under a Boston
  // chip those strings are misleading. Pull the city from
  // deployment.current. When no city resolved at all (the chip
  // shows the neutral "Not in any shipped deployment" string), drop
  // the "in X" suffix — "address in Not in any shipped deployment"
  // reads like a parse error.
  let depName = $derived(deployment.current?.name);
  let isUnknown = $derived(!depName || depName === 'unknown' || depName === '__none__');
  let cityName = $derived(deployment.current?.city ?? '');

  const SPECS = $derived<Record<ErrorKey, Spec>>({
    geocoder: {
      eyebrow: 'Address not resolved',
      headline: isUnknown
        ? "We couldn't resolve that input to a street address."
        : `We couldn't resolve that to an address in ${cityName}.`,
      body:
        `Try a more specific street address. Riprap currently routes per-query to one of the shipped city deployments; international addresses, question-form queries, and addresses outside every shipped deployment's bounding box aren't supported.`,
      tier: 'proxy',
      defaultActions: ['Use a sample query', 'Edit query']
    },
    'all-silent': {
      eyebrow: 'Outside evidence coverage',
      headline: 'No specialists found evidence at this point.',
      body:
        `The address resolved, but every flood-evidence specialist returned silent. This is rare and usually means parkland, water, or a point with no nearby civic data. Try a nearby street address or expand to neighborhood-mode.`,
      tier: 'proxy',
      defaultActions: ['Try nearby address', 'Switch to neighborhood-mode']
    },
    grounding: {
      eyebrow: 'Grounding failure',
      headline: "Briefing prose couldn't be composed within citation constraints.",
      body:
        'Mellea rejected all reroll attempts. The underlying evidence is fine — only the prose composition failed. Download the structured evidence below, or contact support.',
      tier: 'modeled',
      defaultActions: ['Download evidence (JSON)', 'Contact support', 'Try again']
    },
    backend: {
      eyebrow: 'Backend unavailable',
      headline: 'Inference backend did not respond.',
      body:
        "The configured inference backend didn't respond within the routing budget. This usually clears within a few minutes during a deploy window. The hardware-pill in the header reflects the current state.",
      tier: 'proxy',
      defaultActions: ['Retry now', 'Switch backend']
    }
  });

  let spec = $derived(SPECS[state]);
  let resolvedActions = $derived<Action[]>(
    actions ?? spec.defaultActions.map((label) => ({ label }))
  );
</script>

<article class="error-card error-card-{state}" role="alert" aria-live="assertive">
  <header class="error-card-head">
    <TierGlyph tier={spec.tier} size={11} color="var(--tier-{spec.tier})" />
    <span class="error-card-eyebrow">{eyebrowOverride ?? spec.eyebrow}</span>
  </header>
  <h3 class="error-card-headline">{headlineOverride ?? spec.headline}</h3>
  <p class="error-card-body">{bodyOverride ?? spec.body}</p>
  <div class="error-card-actions">
    {#each resolvedActions as a, i (i)}
      {#if a.href}
        <a class="error-card-action" class:is-primary={i === 0} href={a.href}>{a.label}</a>
      {:else}
        <button
          type="button"
          class="error-card-action"
          class:is-primary={i === 0}
          onclick={a.onClick}
        >{a.label}</button>
      {/if}
    {/each}
  </div>
  <footer class="error-card-foot">
    <span class="section-label">Trust signals · still on</span>
    <span class="error-card-foot-copy">All foundation models Apache-2.0 · No commercial APIs at runtime</span>
  </footer>
</article>
