/**
 * MapLegend — the right-rail "Layers · grouped by Stone" panel that
 * the user screenshotted listing NYC pebbles for a Boston query.
 *
 * The fix: layers derive from pebbleManifest.byStone filtered by
 * display.map_layer = true, so a Boston query sees Boston's layers
 * (boston_311), not the hardcoded NYC table.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render } from '@testing-library/svelte';
import MapLegend from '$lib/components/map/MapLegend.svelte';
import { resetStores, seedForCity } from '../helpers/stores';
import { ALL_CITIES, NYC, BOSTON, CHICAGO, SF, SEATTLE, NYC_LEAK_NEEDLES } from '../fixtures/cities';

const ALL_ON = { empirical: true, modeled: true, proxy: true, synthetic: true };

beforeEach(resetStores);

describe('MapLegend derives layers from the loaded deployment\'s manifest', () => {
  it.each([
    ['nyc',     NYC,     ['Sandy Inundation Zone', 'Hurricane Ida', 'MTA subway entrances']],
    ['boston',  BOSTON,  ['Boston 311 service requests']],
    ['chicago', CHICAGO, ['Chicago 311 service requests']],
    ['sf',      SF,      ['SF 311 service requests']],
  ])(
    '%s renders the deployment\'s map-layer pebbles as rows',
    (_key, city, expectedRows) => {
      seedForCity(city);
      const { container } = render(MapLegend, {
        props: { active: ALL_ON, onToggle: () => {} },
      });
      const text = container.textContent ?? '';
      for (const row of expectedRows) {
        expect(text, `${city.key} legend missing expected row "${row}"`).toContain(row);
      }
    },
  );

  it('Seattle has no map_layer pebbles → every Stone shows the "no map layers" placeholder', () => {
    seedForCity(SEATTLE);
    const { container } = render(MapLegend, {
      props: { active: ALL_ON, onToggle: () => {} },
    });
    const text = container.textContent ?? '';
    // Seattle's manifest has zero map_layer=true pebbles, so every
    // non-capstone Stone collapses to the "no map layers" message.
    expect(text).toContain('no map layers — see Findings cards');
    // And no NYC ghost layers anywhere.
    for (const needle of NYC_LEAK_NEEDLES) {
      expect(text, `Seattle legend leaked NYC needle "${needle}"`).not.toContain(needle);
    }
  });
});

describe('MapLegend cross-city: zero NYC layers in any non-NYC render', () => {
  for (const city of ALL_CITIES.filter((c) => c.key !== 'nyc')) {
    it(`${city.key} legend contains no NYC needle`, () => {
      resetStores();
      seedForCity(city);
      const { container } = render(MapLegend, {
        props: { active: ALL_ON, onToggle: () => {} },
      });
      const text = container.textContent ?? '';
      for (const needle of NYC_LEAK_NEEDLES) {
        expect(text, `${city.key} legend leaked "${needle}"`).not.toContain(needle);
      }
    });
  }
});

describe('MapLegend Stone tagline reflects deployment description', () => {
  it('Boston cornerstone tag uses Boston wording, not NYC', () => {
    seedForCity(BOSTON);
    const { container } = render(MapLegend, {
      props: { active: ALL_ON, onToggle: () => {} },
    });
    const text = container.textContent ?? '';
    expect(text).toContain('Reads what Boston remembers about flooding');
    expect(text).not.toContain("what NYC's ground remembers");
  });
});
