/**
 * FindingsRegion — the composite that groups Stones into rows + cards.
 * Renders all 5 stones in canonical order, even when a stone has zero
 * cards (it still shows "silent" affordance). The user's screenshots
 * caught this region rendering NYC pebbles for a Boston query — the
 * StoneRegion + cardAdapter tests already seal that; this test seals
 * the composite's structural promises.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render } from '@testing-library/svelte';
import FindingsRegion from '$lib/components/findings/FindingsRegion.svelte';
import type { FindingsData, StoneTrace, StoneKey } from '$lib/types/card';
import { resetStores, seedForCity } from '../helpers/stores';
import { ALL_CITIES, BOSTON, NYC, NYC_LEAK_NEEDLES } from '../fixtures/cities';

function emptyTrace(stone: StoneKey): StoneTrace {
  return {
    stone, members: [], fired: 0, silent_by_design: 0, errored: 0, ms: 0,
  };
}

const EMPTY_FINDINGS: FindingsData = {
  cards: [],
  stones: ['cornerstone', 'touchstone', 'keystone', 'lodestone', 'capstone']
    .map((s) => emptyTrace(s as StoneKey)),
  wallSeconds: 0,
};

beforeEach(resetStores);

describe('FindingsRegion renders 5 Stones in canonical order', () => {
  it('NYC scaffold seeded → renders all five Stone names', () => {
    seedForCity(NYC);
    const { container } = render(FindingsRegion, {
      props: { data: EMPTY_FINDINGS },
    });
    const text = container.textContent ?? '';
    for (const name of ['Cornerstone', 'Touchstone', 'Keystone', 'Lodestone', 'Capstone']) {
      expect(text).toContain(name);
    }
  });

  it('Boston scaffold seeded → no NYC needle in the entire region', () => {
    seedForCity(BOSTON);
    const { container } = render(FindingsRegion, {
      props: { data: EMPTY_FINDINGS },
    });
    const text = container.textContent ?? '';
    for (const needle of NYC_LEAK_NEEDLES) {
      expect(text, `Boston FindingsRegion leaked "${needle}"`).not.toContain(needle);
    }
  });

  it.each(ALL_CITIES.filter((c) => c.key !== 'nyc' && c.key !== 'elsewhere'))(
    'tagline for $key Cornerstone uses the deployment description',
    (city) => {
      resetStores();
      seedForCity(city);
      const { container } = render(FindingsRegion, {
        props: { data: EMPTY_FINDINGS },
      });
      const text = container.textContent ?? '';
      const expected = city.manifest.stones.find((s) => s.id === 'cornerstone')?.description;
      if (expected) expect(text).toContain(expected);
    },
  );
});
