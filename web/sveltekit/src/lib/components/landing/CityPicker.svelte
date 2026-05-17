<script lang="ts">
  import { goto } from '$app/navigation';

  /** CityPicker — five-city selector row below the search input.
   *
   *  Per Claude Design handoff §5: showcases the multi-city
   *  generalisation claim without requiring text input. Each pill
   *  jumps to a curated anchor address in that city so the user
   *  immediately sees a working cross-city briefing.
   *
   *  Anchors match probe_cities.py's smoke-test addresses so what
   *  loads here is identical to what `scripts/probe_cities.py`
   *  exercises in CI.
   */

  interface CityAnchor {
    city: string;
    address: string;
  }

  const CITIES: CityAnchor[] = [
    { city: 'NYC',           address: '189 Atlantic Avenue, Brooklyn, NY' },
    { city: 'Chicago',       address: '233 S Wacker Dr, Chicago, IL' },
    { city: 'Seattle',       address: '2100 5th Ave, Seattle, WA' },
    { city: 'San Francisco', address: '1 Dr Carlton B Goodlett Pl, San Francisco, CA' },
    { city: 'Boston',        address: '1 City Hall Square, Boston, MA' },
  ];

  function pick(addr: string) {
    goto(`/q/${encodeURIComponent(addr)}`);
  }
</script>

<div class="city-picker" role="region" aria-label="Try a shipped city">
  <span class="city-picker-label">Or pick a city:</span>
  <div class="city-picker-row">
    {#each CITIES as c (c.city)}
      <button
        type="button"
        class="city-picker-pill"
        onclick={() => pick(c.address)}
        title="Brief the anchor address for {c.city}: {c.address}"
      >{c.city}</button>
    {/each}
  </div>
</div>

<style>
  .city-picker {
    margin-top: 14px;
    display: flex;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
    max-width: 760px;
  }
  .city-picker-label {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ink-tertiary);
  }
  .city-picker-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .city-picker-pill {
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.02em;
    color: var(--accent);
    background: white;
    border: 1px solid var(--accent);
    padding: 5px 12px;
    cursor: pointer;
    transition: background-color 120ms ease, color 120ms ease;
  }
  .city-picker-pill:hover {
    background: var(--accent);
    color: white;
  }
  .city-picker-pill:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 2px;
  }
</style>
