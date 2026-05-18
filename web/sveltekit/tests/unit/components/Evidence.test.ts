/**
 * Evidence components — EvidenceCard + EvidenceGrid. Each fmt variant
 * (scalar / table / spark / histogram / forecast / thumb) renders the
 * appropriate body. EvidenceGrid tallies + groups items.
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import EvidenceCard from '$lib/components/evidence/EvidenceCard.svelte';
import EvidenceGrid from '$lib/components/evidence/EvidenceGrid.svelte';
import type { EvidenceItem, EvidenceFmt } from '$lib/types/evidence';

function item(id: string, fmt: EvidenceFmt, overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id,
    citeId: `cite-${id}`,
    tier: 'empirical',
    source: 'TestSource',
    title: `Test ${id}`,
    docId: id,
    vintage: '2026-05',
    fmt,
    ...overrides,
  };
}

describe('EvidenceCard renders every fmt variant', () => {
  it.each<[string, EvidenceFmt]>([
    ['scalar',    { kind: 'scalar', value: '2.17', unit: 'ft', aux: 'MLLW' }],
    ['table',     { kind: 'table', columns: ['k', 'v'], rows: [['a', '1']] }],
    ['spark',     { kind: 'spark', data: [1, 2, 3], headline: '3 readings', sub: 'last 3h' }],
    ['histogram', { kind: 'histogram', data: [1, 2, 3, 4], headline: 'distribution', sub: '4 bins' }],
    ['forecast',  { kind: 'forecast', data: [{ year: 2050, low: 0.3, mid: 0.5, high: 1.0 }] }],
    ['thumb',     { kind: 'thumb', thumbKind: 'stormwater', sub: 'DEP scenario' }],
  ])('fmt=%s renders title + source + vintage', (kind, fmt) => {
    const { container } = render(EvidenceCard, { props: { ev: item(kind, fmt) } });
    const text = container.textContent ?? '';
    expect(text).toContain(`Test ${kind}`);
    expect(text).toContain('TestSource');
    expect(text).toContain('2026-05');
  });
});

describe('EvidenceGrid', () => {
  it('renders crash-free with empty items', () => {
    const { container } = render(EvidenceGrid, { props: { items: [] } });
    expect(container).toBeTruthy();
  });

  it('renders one card per item', () => {
    const items = [
      item('a', { kind: 'scalar', value: '1', unit: 'ft' }),
      item('b', { kind: 'scalar', value: '2', unit: 'ft' }),
      item('c', { kind: 'scalar', value: '3', unit: 'ft' }),
    ];
    const { container } = render(EvidenceGrid, { props: { items } });
    const text = container.textContent ?? '';
    expect(text).toContain('Test a');
    expect(text).toContain('Test b');
    expect(text).toContain('Test c');
  });
});
