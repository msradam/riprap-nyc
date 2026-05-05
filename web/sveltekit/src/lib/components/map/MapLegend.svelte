<script lang="ts">
  import type { Tier } from '$lib/types/tier';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
  import TierBadge from '$lib/components/glyphs/TierBadge.svelte';

  type LayerKey = 'empirical' | 'modeled' | 'synthetic' | 'proxy';
  interface Layer { key: LayerKey; tier: Tier; label: string; source: string; }
  interface Props {
    active: Record<LayerKey, boolean>;
    /**
     * Number of features in each tier source. Layers with `0` (or
     * undefined when the FC hasn't loaded yet) are dropped from the
     * legend — silence over confabulation, same rule as briefing
     * sections without supporting documents (handoff hard rule #3).
     * Pass `null` to show all four (e.g. for the spec page).
     */
    featureCounts?: Record<LayerKey, number> | null;
    onToggle: (key: LayerKey) => void;
  }

  let { active, featureCounts, onToggle }: Props = $props();

  const LAYERS: Layer[] = [
    { key: 'empirical', tier: 'empirical', label: 'Sandy Inundation Zone (2012)', source: 'NYC OEM' },
    { key: 'modeled', tier: 'modeled', label: 'FEMA / DEP scenarios', source: 'FEMA · NYC DEP' },
    { key: 'synthetic', tier: 'synthetic', label: 'Synthetic SAR (TerraMind)', source: 'TerraMind v1.2' },
    { key: 'proxy', tier: 'proxy', label: '311 flood complaints', source: 'NYC 311' }
  ];

  /**
   * Decide which legend rows to render. `featureCounts === null` means
   * the caller wants all four shown (no data-driven filtering). Any
   * key with count > 0 (or `undefined` while a fetch is still in
   * flight) renders; explicit zero is dropped.
   */
  let visibleLayers = $derived(
    featureCounts === null
      ? LAYERS
      : LAYERS.filter((l) => {
          const n = featureCounts?.[l.key];
          return n === undefined || n > 0;
        })
  );
</script>

{#if visibleLayers.length}
<div class="map-legend" role="group" aria-label="Map layer toggles">
  <div class="map-legend-head">
    <span class="section-label">Layers · {visibleLayers.length}</span>
  </div>
  {#each visibleLayers as l (l.key)}
    <button
      type="button"
      class="map-legend-item"
      class:is-on={active[l.key]}
      class:is-off={!active[l.key]}
      onclick={() => onToggle(l.key)}
      aria-pressed={active[l.key]}
    >
      <span class="map-legend-swatch" aria-hidden="true">
        <TierGlyph tier={l.tier} size={11} color="var(--tier-{l.tier})" />
      </span>
      <span class="map-legend-text">
        <span class="map-legend-label">{l.label}</span>
        <span class="map-legend-source">{l.source} · <TierBadge tier={l.tier} compact /></span>
      </span>
      <span class="map-legend-toggle" aria-hidden="true">{active[l.key] ? 'ON' : 'OFF'}</span>
    </button>
  {/each}
</div>
{/if}
