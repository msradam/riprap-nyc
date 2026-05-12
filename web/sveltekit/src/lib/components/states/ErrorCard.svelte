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

  const SPECS: Record<ErrorKey, Spec> = {
    geocoder: {
      eyebrow: 'Address not resolved',
      headline: "We couldn't resolve that to a NYC address.",
      body:
        'Try a more specific street address — for example, "80 Pioneer Street, Brooklyn." Riprap covers the five boroughs only; international addresses, NJ addresses, and points outside NYC aren\'t supported.',
      tier: 'proxy',
      defaultActions: ['Use a sample query', 'Edit query']
    },
    'all-silent': {
      eyebrow: 'Outside evidence coverage',
      headline: 'No specialists found evidence at this point.',
      body:
        'The address resolved, but every flood-evidence specialist returned silent. This is rare and usually means parkland, water, or a point with no nearby 311, no FloodNet sensor, and no Sandy overlap. Try a nearby street address or expand to neighborhood-mode.',
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
      headline: 'All routing targets exhausted.',
      body:
        "The inference backend (msradam/riprap-vllm, NVIDIA L4) didn't respond. This usually clears within 5 minutes during a deploy window. The hardware-pill in the header is currently red.",
      tier: 'proxy',
      defaultActions: ['Retry now', 'Switch backend']
    }
  };

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
