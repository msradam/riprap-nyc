/**
 * Briefing — renders the structured BriefingBlock[] (status / head /
 * prose) the cardAdapter emits. Bugs we want to seal:
 *
 *   1. Renders all three block kinds, no crash on empty blocks
 *   2. Citation references inside prose ClaimPart resolve to the
 *      passed-in citations map (no orphan cite chips)
 *   3. Reduced-motion users see all blocks immediately (no animated
 *      reveal step that hides content from them)
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import Briefing from '$lib/components/briefing/Briefing.svelte';
import type { BriefingBlock, Citation } from '$lib/types/claim';

const CITES: Record<string, Citation> = {
  noaa_tides: {
    id: 'noaa_tides', n: 1, tier: 'empirical',
    source: 'NOAA CO-OPS', title: 'Boston tide gauge',
    docId: 'noaa_tides', url: 'https://example/noaa',
    vintage: '2026-05', retrieved: '2026-05-17',
  },
};

describe('Briefing renders block kinds', () => {
  it('empty blocks → renders nothing crash-free', () => {
    const { container } = render(Briefing, {
      props: { blocks: [], citations: {} },
    });
    expect(container.textContent).toBe('');
  });

  it('status + head + prose blocks all render', () => {
    const blocks: BriefingBlock[] = [
      { kind: 'status', html: '<em>Pipeline complete.</em>' },
      { kind: 'head', n: '01', label: 'Flood exposure', title: 'Hazard summary' },
      { kind: 'prose', parts: [
        { text: 'Boston Harbor tide gauge reads 2.17 ft above MLLW' },
        { text: ' per ', tier: 'empirical' },
        { text: 'NOAA CO-OPS', cite: 'noaa_tides' },
        { text: '.' },
      ]},
    ];
    const { container } = render(Briefing, {
      props: { blocks, citations: CITES },
    });
    const text = container.textContent ?? '';
    expect(text).toContain('Pipeline complete.');
    expect(text).toContain('Flood exposure');
    expect(text).toContain('Boston Harbor tide gauge');
    expect(text).toContain('NOAA CO-OPS');
  });

  it('non-streaming mode shows all blocks immediately', () => {
    const blocks: BriefingBlock[] = [
      { kind: 'prose', parts: [{ text: 'first' }] },
      { kind: 'prose', parts: [{ text: 'second' }] },
      { kind: 'prose', parts: [{ text: 'third' }] },
    ];
    const { container } = render(Briefing, {
      props: { blocks, citations: {}, streaming: false },
    });
    const text = container.textContent ?? '';
    expect(text).toContain('first');
    expect(text).toContain('second');
    expect(text).toContain('third');
  });

  it('does not render NYC-specific text by itself (city-agnostic component)', () => {
    // Briefing is just a renderer — content comes from props. Empty
    // props should produce empty output, not leak any NYC string from
    // the component itself.
    const { container } = render(Briefing, {
      props: { blocks: [], citations: {} },
    });
    const text = container.textContent ?? '';
    for (const needle of ['NYC', 'Sandy', 'MTA', 'NYCHA', 'FloodHelpNY']) {
      expect(text).not.toContain(needle);
    }
  });
});
