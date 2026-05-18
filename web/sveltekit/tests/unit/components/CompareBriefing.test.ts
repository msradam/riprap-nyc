/**
 * CompareBriefing — the two-place compare-mode briefing. Renders the
 * reconciler paragraph, both target labels, and per-place structured
 * step data.
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import CompareBriefing from '$lib/components/briefing/CompareBriefing.svelte';
import type { Citation } from '$lib/types/claim';

const PARAGRAPH = 'PLACE A is inside the 2012 Sandy zone. PLACE B is outside.';
const CITATIONS: Record<string, Citation> = {};
const TARGETS = [
  { label: 'PLACE A', address: '189 Atlantic Avenue, Brooklyn, NY' },
  { label: 'PLACE B', address: '200 East Houston Street, New York, NY' },
];

describe('CompareBriefing rendering', () => {
  it('renders the reconciler paragraph + both target labels', () => {
    const { container } = render(CompareBriefing, {
      props: {
        paragraph: PARAGRAPH,
        citations: CITATIONS,
        targets: TARGETS,
      },
    });
    const text = container.textContent ?? '';
    expect(text).toContain('PLACE A');
    expect(text).toContain('PLACE B');
  });

  it('crash-free when targets is empty', () => {
    const { container } = render(CompareBriefing, {
      props: { paragraph: '', citations: {}, targets: [] },
    });
    expect(container).toBeTruthy();
  });
});
