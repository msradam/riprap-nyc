/**
 * StoneRegion — the per-Stone group in the Findings section. Two
 * user-visible bugs lived here:
 *   1. tagline hardcoded as "what NYC's ground remembers" via STONE_META.tag,
 *      shown even under a Boston chip.
 *   2. roster of pebble rows ("□ sandy not invoked", "□ ida_hwm not
 *      invoked", …) read from pebbleManifest.byStone for every Stone
 *      — when the manifest was the boot NYC scaffold for a Boston run,
 *      every NYC pebble appeared as a "not invoked" ghost row.
 *
 * Both are deployment-store-driven now; these tests are the seal.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render } from '@testing-library/svelte';
import StoneRegion from '$lib/components/findings/StoneRegion.svelte';
import { resetStores, seedForCity } from '../helpers/stores';
import { ALL_CITIES, NYC_LEAK_NEEDLES, NYC, BOSTON } from '../fixtures/cities';
import type { StoneTrace } from '$lib/types/card';

const EMPTY_TRACE: StoneTrace = {
  stone: 'cornerstone',
  members: [],
  fired: 0,
  silent_by_design: 0,
  errored: 0,
  ms: 0,
};

beforeEach(resetStores);

describe('StoneRegion tagline reflects per-deployment description', () => {
  it.each([
    ['boston',  BOSTON,  "Reads what Boston remembers about flooding"],
    ['nyc',     NYC,     "Reads what NYC's ground remembers about flooding"],
  ])(
    'Cornerstone tagline for %s starts with the deployment-specific text',
    (_key, city, expected) => {
      seedForCity(city);
      const { container } = render(StoneRegion, {
        props: {
          stone: 'cornerstone',
          cards: [],
          trace: { ...EMPTY_TRACE, stone: 'cornerstone' },
        },
      });
      const tag = container.querySelector('.region-tag');
      expect(tag, 'region-tag missing').not.toBeNull();
      expect(tag).toHaveTextContent(expected);
    },
  );

  it('non-NYC StoneRegion does not show the NYC tagline string', () => {
    for (const city of ALL_CITIES.filter((c) => c.key !== 'nyc' && c.key !== 'elsewhere')) {
      resetStores();
      seedForCity(city);
      const { container } = render(StoneRegion, {
        props: {
          stone: 'cornerstone',
          cards: [],
          trace: { ...EMPTY_TRACE, stone: 'cornerstone' },
        },
      });
      expect(container.textContent, `${city.key} cornerstone leaked NYC tagline`)
        .not.toContain("what NYC's ground remembers");
    }
  });
});

describe('StoneRegion roster comes from pebbleManifest.byStone for the loaded city', () => {
  it('Boston cornerstone shows no NYC-only pebbles in the roster', () => {
    seedForCity(BOSTON);
    const { container } = render(StoneRegion, {
      props: {
        stone: 'cornerstone',
        cards: [],
        trace: { ...EMPTY_TRACE, stone: 'cornerstone' },
      },
    });
    const text = container.textContent ?? '';
    for (const needle of NYC_LEAK_NEEDLES) {
      expect(text, `Boston cornerstone roster contains "${needle}"`).not.toContain(needle);
    }
  });

  it('NYC cornerstone renders the NYC-specific tagline', () => {
    // The pebble roster ("□ sandy not invoked", etc.) is built upstream
    // in cardAdapter.buildStoneTraces — StoneRegion just renders the
    // StoneTrace it receives. Here we verify the tagline path; the
    // roster-population behaviour is covered by cardAdapter.test.ts.
    seedForCity(NYC);
    const { container } = render(StoneRegion, {
      props: {
        stone: 'cornerstone',
        cards: [],
        trace: { ...EMPTY_TRACE, stone: 'cornerstone' },
      },
    });
    expect(container.textContent).toContain("ground remembers about flooding");
  });
});

describe('StoneRegion cross-city sweep: no NYC needle in any non-NYC Stone', () => {
  for (const city of ALL_CITIES.filter((c) => c.key !== 'nyc')) {
    for (const stone of ['cornerstone', 'touchstone', 'keystone', 'lodestone'] as const) {
      it(`${city.key}/${stone} contains zero NYC needles`, () => {
        resetStores();
        seedForCity(city);
        const { container } = render(StoneRegion, {
          props: {
            stone,
            cards: [],
            trace: { ...EMPTY_TRACE, stone },
          },
        });
        const text = container.textContent ?? '';
        for (const needle of NYC_LEAK_NEEDLES) {
          expect(text, `${city.key}/${stone} leaked NYC needle "${needle}"`).not.toContain(needle);
        }
      });
    }
  }
});
