/**
 * AppHeader — the header chip the user kept catching showing "NYC"
 * for a Boston query. With per-query routing wired through the SSE
 * `deployment` event, the chip should reflect whichever city
 * `deployment.current` resolves to.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import AppHeader from '$lib/components/shell/AppHeader.svelte';
import { resetStores, seedForCity } from '../helpers/stores';
import { ALL_CITIES, NYC_LEAK_NEEDLES, NYC } from '../fixtures/cities';

beforeEach(resetStores);

describe('AppHeader chip text per deployment', () => {
  it.each(ALL_CITIES.map((c) => [c.key, c] as const))(
    'renders %s deployment\'s city + hazard',
    (_key, city) => {
      seedForCity(city);
      const { container } = render(AppHeader, {
        props: { queryId: 'test-query' },
      });
      // City pill text
      const pill = container.querySelector('.app-header-city-pill');
      expect(pill, `city pill missing for ${city.key}`).not.toBeNull();
      expect(pill).toHaveTextContent(city.deployment.city);
      // Hazard text — rendered lowercase per the chip styling
      expect(container.textContent?.toLowerCase()).toContain(
        city.deployment.hazard.toLowerCase(),
      );
    },
  );

  it('non-NYC city renders no NYC-only text in the chip', () => {
    for (const city of ALL_CITIES.filter((c) => c.key !== 'nyc')) {
      resetStores();
      seedForCity(city);
      const { container } = render(AppHeader, {
        props: { queryId: 'test-query' },
      });
      const text = container.textContent ?? '';
      // The header chip should not contain the string "NYC" anywhere
      // when the deployment is not NYC. (Hits the bug where a Boston
      // run still showed "NYC" pill.)
      expect(text, `${city.key} chip contains 'NYC': ${text.slice(0, 200)}`)
        .not.toMatch(/\bNYC\b/);
    }
  });

  it('falls back gracefully when deployment.current is null', () => {
    // Pre-load state (deployment.current=null), still renders something.
    const { container } = render(AppHeader, {
      props: { queryId: 'test-query' },
    });
    expect(container.textContent).toBeTruthy();
  });
});

describe('AppHeader regression: NYC needles must not leak into other cities', () => {
  for (const city of ALL_CITIES.filter((c) => c.key !== 'nyc')) {
    it(`${city.key} render has no NYC needle in the header`, () => {
      resetStores();
      seedForCity(city);
      const { container } = render(AppHeader, {
        props: { queryId: 'test-query' },
      });
      const text = container.textContent ?? '';
      for (const needle of NYC_LEAK_NEEDLES) {
        expect(text, `${city.key} header leaked NYC needle "${needle}"`)
          .not.toContain(needle);
      }
    });
  }
});

describe('AppHeader baseline: NYC city renders the NYC pill', () => {
  it('shows "NYC" pill when seeded with NYC fixture', () => {
    seedForCity(NYC);
    render(AppHeader, { props: { queryId: 'test-query' } });
    expect(screen.getByText('NYC')).toBeInTheDocument();
  });
});
