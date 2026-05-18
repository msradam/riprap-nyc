/**
 * RegisterCard — NYC-data-gated component for the four NYC register
 * specialists (MTA / NYCHA / DOE / DOH). The audit exempts this file
 * because the NYC strings inside it only render when NYC `registers`
 * data is present — under a Boston query the parent skips this card
 * entirely. These tests pin THAT behaviour: given NYC RegisterData,
 * the card renders; the parent never passes Boston data here.
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import RegisterCard from '$lib/components/evidence/RegisterCard.svelte';
import type { RegisterData } from '$lib/types/states';

const NYC_REGISTER: RegisterData = {
  type: 'subway entrances',
  radius: '200 m',
  count: 4,
  vintage: '2026-04',
  sourceLabel: 'MTA · USGS · FEMA · NYC OEM · NYC DEP',
  rows: [
    {
      name: 'Atlantic Av · Pacific St',
      asset: 'SUBWAY',
      primaryTier: 'empirical',
      ada: true,
      elev: '5.2 ft',
      fema: 'X',
      sandy: 'inside',
      dep: 'mod',
    } as RegisterData['rows'][0],
  ],
};

describe('RegisterCard renders NYC register data', () => {
  it('renders headline count + asset type + radius', () => {
    const { container } = render(RegisterCard, { props: { data: NYC_REGISTER } });
    const text = container.textContent ?? '';
    expect(text).toContain('4');
    expect(text).toContain('subway entrances');
    expect(text).toContain('200 m');
  });

  it('renders each row\'s name', () => {
    const { container } = render(RegisterCard, { props: { data: NYC_REGISTER } });
    expect(container.textContent).toContain('Atlantic Av');
  });

  it('renders the sourceLabel when present', () => {
    const { container } = render(RegisterCard, { props: { data: NYC_REGISTER } });
    expect(container.textContent).toContain('MTA');
  });

  it('crash-free with zero rows', () => {
    const { container } = render(RegisterCard, {
      props: { data: { ...NYC_REGISTER, count: 0, rows: [] } },
    });
    expect(container.textContent).toContain('0');
  });
});
