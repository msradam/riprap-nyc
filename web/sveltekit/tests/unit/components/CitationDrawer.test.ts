/**
 * CitationDrawer — the citation-chip resolution surface that opens
 * when a user clicks a `[N]` cite in the briefing. Renders the
 * citations map as a list of source-tier-vintage rows.
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import CitationDrawer from '$lib/components/briefing/CitationDrawer.svelte';
import type { Citation } from '$lib/types/claim';

const CITES: Record<string, Citation> = {
  noaa_tides: {
    id: 'noaa_tides', n: 1, tier: 'empirical',
    source: 'NOAA CO-OPS', title: 'Boston Harbor tide gauge',
    docId: 'noaa_tides', url: 'https://example/noaa',
    vintage: '2026-05', retrieved: '2026-05-17',
  },
  nws_alerts: {
    id: 'nws_alerts', n: 2, tier: 'modeled',
    source: 'NWS', title: 'Active alerts at point',
    docId: 'nws_alerts', url: 'https://example/nws',
    vintage: '2026-05', retrieved: '2026-05-17',
  },
};

describe('CitationDrawer rendering', () => {
  it('renders crash-free with empty citations map', () => {
    const { container } = render(CitationDrawer, { props: { citations: {} } });
    expect(container).toBeTruthy();
  });

  it('renders each citation row', () => {
    const { container } = render(CitationDrawer, { props: { citations: CITES } });
    const text = container.textContent ?? '';
    expect(text).toContain('NOAA CO-OPS');
    expect(text).toContain('Boston Harbor tide gauge');
    expect(text).toContain('NWS');
    expect(text).toContain('Active alerts at point');
  });

  it('renders sources without NYC needles when citations are non-NYC', () => {
    const { container } = render(CitationDrawer, { props: { citations: CITES } });
    const text = container.textContent ?? '';
    for (const needle of ['Sandy Inundation', 'MTA subway', 'NYCHA developments', 'FloodHelpNY']) {
      expect(text).not.toContain(needle);
    }
  });
});
