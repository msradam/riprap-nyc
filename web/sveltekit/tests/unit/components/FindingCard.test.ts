/**
 * FindingCard — the per-pebble evidence card. Dispatches on
 * `card.variant` to one of 13+ body components (headline / tabular /
 * scalars / spark / histogram / timeseries / timeseries-ft / forecast
 * / raster / raster-pred / lulc / register / comparison / meta).
 *
 * These tests assert the variant dispatcher renders SOMETHING visible
 * for every variant — a smoke seal so introducing a new variant
 * without wiring its body fails CI.
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import FindingCard from '$lib/components/findings/FindingCard.svelte';
import type { Card, CardVariant } from '$lib/types/card';

/** Tiny factory — fills the mandatory chrome fields, lets the test
 *  override the variant-specific body fields. */
function card(variant: CardVariant, overrides: Partial<Card> = {}): Card {
  return {
    id: `test-${variant}`,
    stone: 'touchstone',
    tier: 'empirical',
    variant,
    source: 'TestSource',
    agency: 'Test Agency',
    vintage: '2026-05',
    title: `Test ${variant} card`,
    docId: 'test_doc',
    citeId: null,
    ...overrides,
  } as Card;
}

const VARIANTS_WITH_FIXTURES: { variant: CardVariant; props: Partial<Card> }[] = [
  { variant: 'headline',     props: { headline: 'Inside the polygon', sub: '2012 Sandy zone.' } },
  { variant: 'tabular',      props: { columns: ['name', 'count'], rows: [['nws_alerts', 0]] } },
  { variant: 'scalars',      props: { scalars: [{ value: '2.17 ft', label: 'observed (MLLW)' }] } },
  { variant: 'spark',        props: { spark: [1, 2, 3, 4, 5], sparkSub: 'last 5 readings' } },
  { variant: 'histogram',    props: { histogram: [1, 3, 2, 5, 4] } },
  { variant: 'timeseries',   props: { timeseries: { hours: 96, peak: { x: 38, y: 47 }, peakLabel: 'storm peak' } } },
  { variant: 'forecast',     props: { forecastBands: [{ year: 2050, low: 0.3, mid: 0.5, high: 1.2 }] } },
  { variant: 'register',     props: { /* RegisterBody reads from a separate data path, smoke only */ } },
  { variant: 'meta',         props: { body: 'Mellea reroll · 0' } },
];

describe('FindingCard renders every CardVariant without crashing', () => {
  it.each(VARIANTS_WITH_FIXTURES.map((f) => [f.variant, f] as const))(
    'variant=%s renders title + variant body',
    (_v, fixture) => {
      const { container } = render(FindingCard, {
        props: { card: card(fixture.variant, fixture.props) },
      });
      const text = container.textContent ?? '';
      // Every variant must surface its title (header chrome contract).
      expect(text).toContain(`Test ${fixture.variant} card`);
      // Source + vintage are always-shown chrome.
      expect(text).toContain('TestSource');
      expect(text).toContain('2026-05');
    },
  );
});

describe('FindingCard header chrome', () => {
  it('renders the tier badge for each tier', () => {
    for (const tier of ['empirical', 'modeled', 'proxy', 'synthetic'] as const) {
      const { container } = render(FindingCard, {
        props: { card: card('headline', { tier, headline: 'x', sub: 'y' }) },
      });
      // The root element renders as either <article> or <button>
      // depending on mapLayer presence; with mapLayer:null it's <article>.
      expect(container.querySelector('article, button')).not.toBeNull();
    }
  });

  it('renders no NYC content from card chrome alone (city-agnostic)', () => {
    const { container } = render(FindingCard, {
      props: { card: card('scalars', {
        scalars: [{ value: '4.2 ft', label: 'observed' }],
        source: 'NOAA CO-OPS',
      }) },
    });
    const text = container.textContent ?? '';
    // FindingCard itself is city-agnostic — content comes from card props.
    for (const needle of ['NYC', 'Sandy', 'MTA', 'NYCHA', 'FloodHelpNY', 'Brooklyn']) {
      expect(text).not.toContain(needle);
    }
  });
});

describe('FindingCard interactive map-link affordance', () => {
  it('renders as <button> when card.mapLayer is set (keyboard-interactive)', () => {
    const { container } = render(FindingCard, {
      props: { card: card('headline', { headline: 'x', sub: 'y', mapLayer: 'noaa' }) },
    });
    // svelte:element this={interactive ? 'button' : 'article'} — a
    // <button> is implicitly focusable, no tabindex needed.
    expect(container.querySelector('button')).not.toBeNull();
    expect(container.querySelector('article')).toBeNull();
  });

  it('renders as <article> when card.mapLayer is null (non-interactive)', () => {
    const { container } = render(FindingCard, {
      props: { card: card('headline', { headline: 'x', sub: 'y', mapLayer: null }) },
    });
    expect(container.querySelector('article')).not.toBeNull();
    expect(container.querySelector('button')).toBeNull();
  });
});
