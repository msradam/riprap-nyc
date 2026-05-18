/**
 * ErrorCard — the polite-redirect card for geocoder / all-silent /
 * grounding / backend failure states. Previously each spec was
 * hardcoded with NYC-specific language (FloodNet sensor, Sandy
 * overlap, "five boroughs only") so a Boston query that triggered
 * all-silent rendered nonsense like "no nearby FloodNet sensor and
 * no Sandy overlap" under a Boston chip.
 *
 * Now message text interpolates `deployment.current.city` and avoids
 * city-specific civic-infrastructure names. These tests are the
 * regression seal: zero NYC needle in any spec for any non-NYC city.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render } from '@testing-library/svelte';
import ErrorCard from '$lib/components/states/ErrorCard.svelte';
import { resetStores, seedForCity } from '../helpers/stores';
import { ALL_CITIES, BOSTON, NYC, ELSEWHERE, NYC_LEAK_NEEDLES } from '../fixtures/cities';
import type { ErrorKey } from '$lib/types/states';

const ERROR_STATES: ErrorKey[] = ['geocoder', 'all-silent', 'grounding', 'backend'];

beforeEach(resetStores);

describe('ErrorCard renders city-aware text per deployment', () => {
  it('geocoder under Boston names Boston, not NYC', () => {
    seedForCity(BOSTON);
    const { container } = render(ErrorCard, { props: { state: 'geocoder' } });
    const text = container.textContent ?? '';
    expect(text).toContain('Boston');
    expect(text).not.toMatch(/\bNYC\b/);
    expect(text).not.toContain('five boroughs');
  });

  it('geocoder under NYC still mentions NYC', () => {
    seedForCity(NYC);
    const { container } = render(ErrorCard, { props: { state: 'geocoder' } });
    expect(container.textContent ?? '').toContain('NYC');
  });

  it('all-silent body has no FloodNet/Sandy/borough leakage for Boston', () => {
    seedForCity(BOSTON);
    const { container } = render(ErrorCard, { props: { state: 'all-silent' } });
    const text = container.textContent ?? '';
    expect(text).not.toContain('FloodNet sensor');
    expect(text).not.toContain('Sandy overlap');
    expect(text).not.toContain('five boroughs');
  });

  it('backend body uses generic phrasing (no NYC-only msradam/L4 specifics)', () => {
    seedForCity(BOSTON);
    const { container } = render(ErrorCard, { props: { state: 'backend' } });
    const text = container.textContent ?? '';
    expect(text).not.toContain('msradam/riprap-vllm');
    expect(text).not.toContain('NVIDIA L4');
  });
});

describe('ErrorCard cross-city × all states: zero NYC needles', () => {
  for (const city of ALL_CITIES.filter((c) => c.key !== 'nyc')) {
    for (const state of ERROR_STATES) {
      it(`${city.key}/${state} contains no NYC needle`, () => {
        resetStores();
        seedForCity(city);
        const { container } = render(ErrorCard, { props: { state } });
        const text = container.textContent ?? '';
        for (const needle of NYC_LEAK_NEEDLES) {
          expect(text, `${city.key}/${state} leaked NYC needle "${needle}"`).not.toContain(needle);
        }
      });
    }
  }
});

describe('ErrorCard out-of-coverage uses neutral fallback', () => {
  it('ELSEWHERE / geocoder drops the "in X" suffix (no city resolved)', () => {
    seedForCity(ELSEWHERE);
    const { container } = render(ErrorCard, { props: { state: 'geocoder' } });
    const text = container.textContent ?? '';
    // The neutral / unknown deployment state used to render as "in
    // Not in any shipped deployment." — reads like a parse error.
    // Now the suffix is dropped entirely.
    expect(text).toContain("couldn't resolve");
    expect(text).not.toContain('Not in any shipped deployment');
    expect(text).not.toContain('NYC');
  });
});
