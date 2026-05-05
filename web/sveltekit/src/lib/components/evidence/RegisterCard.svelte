<script lang="ts">
  /**
   * v0.4.2 §15 — Register card for the four register specialists
   * (subway entrances, NYCHA developments, schools, hospitals).
   *
   * Headline = numeric count + asset type + radius.
   * Body = 3–5 row table with per-row joined metadata.
   * Row glyph = AssetPin + most-empirical TierGlyph stacked.
   * Tap row to expand a per-field provenance grid.
   */
  import type { RegisterData } from '$lib/types/states';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
  import TierBadge from '$lib/components/glyphs/TierBadge.svelte';
  import AssetPin from '$lib/components/glyphs/AssetPin.svelte';

  interface Props { data: RegisterData; }
  let { data }: Props = $props();

  let openRow = $state<number | null>(null);

  function toggle(i: number) {
    openRow = openRow === i ? null : i;
  }
</script>

<article class="register-card" aria-label="{data.type} register">
  <header class="register-card-head">
    <div class="register-card-source">
      <TierGlyph tier="empirical" size={11} color="var(--tier-empirical)" />
      <span class="register-card-source-label">{data.sourceLabel ?? 'MTA · USGS · FEMA · NYC OEM · NYC DEP'}</span>
    </div>
    <span class="register-card-vintage">v. {data.vintage ?? '2026-04'} · joined</span>
  </header>
  <h4 class="register-card-title">
    <span class="register-card-count">{data.count}</span>
    <span class="register-card-type">{data.type} within {data.radius}</span>
  </h4>
  <table class="register-table">
    <thead>
      <tr>
        <th></th><th>asset</th><th>elev.</th><th>ADA</th>
        <th>FEMA</th><th>Sandy 2012</th><th>DEP modeled</th>
      </tr>
    </thead>
    <tbody>
      {#each data.rows as r, i (i)}
        <tr
          class="register-row"
          class:is-open={openRow === i}
          onclick={() => toggle(i)}
        >
          <td class="register-row-glyph">
            <AssetPin kind={r.asset} size={10} />
            <TierGlyph tier={r.primaryTier} size={9} color="var(--tier-{r.primaryTier})" />
          </td>
          <td class="register-row-name">{r.name}</td>
          <td>{r.elev}</td>
          <td class={r.ada ? 'register-yes' : 'register-no'}>{r.ada ? '✓' : '—'}</td>
          <td>{r.fema}</td>
          <td>{r.sandy}</td>
          <td>{r.dep}</td>
        </tr>
        {#if openRow === i}
          <tr class="register-detail">
            <td colspan="7">
              <div class="register-detail-grid">
                <div><span class="section-label">Position</span><p>Empirical · MTA station entrance dataset, lat/lon survey-grade</p></div>
                <div><span class="section-label">Elevation</span><p>Modeled · NYC DEM 1 ft · joined at entrance centroid</p></div>
                <div><span class="section-label">Sandy 2012</span><p>Empirical · NYC OEM Sandy Inundation Zone, polygon test</p></div>
                <div><span class="section-label">DEP scenario</span><p>Modeled · Stormwater Flood Map moderate (2.13 in/hr)</p></div>
              </div>
            </td>
          </tr>
        {/if}
      {/each}
    </tbody>
  </table>
  <footer class="register-card-foot">
    <span class="register-foot-note">
      Row glyph reflects most-empirical tier across joined fields. Tap row for per-field provenance.
    </span>
    <TierBadge tier="empirical" compact />
  </footer>
</article>
