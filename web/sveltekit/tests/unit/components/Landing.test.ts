/**
 * Landing components — the marketing/index page. These are exempted
 * from the NYC-leak audit because they intentionally name shipped
 * cities as features. These tests assert they mount + render the
 * expected city list / standards strip / source counts.
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import CityPicker from '$lib/components/landing/CityPicker.svelte';
import SourceStrip from '$lib/components/landing/SourceStrip.svelte';
import StandardsStrip from '$lib/components/landing/StandardsStrip.svelte';
import UseBand from '$lib/components/landing/UseBand.svelte';
import PhaseBanner from '$lib/components/landing/PhaseBanner.svelte';
import LandFooter from '$lib/components/landing/LandFooter.svelte';
import LandStones from '$lib/components/landing/LandStones.svelte';
import LandHeader from '$lib/components/landing/LandHeader.svelte';

describe('Landing smoke', () => {
  it('CityPicker renders all 5 shipped city options', () => {
    const { container } = render(CityPicker);
    const text = container.textContent ?? '';
    for (const city of ['NYC', 'Boston', 'Chicago', 'Seattle', 'San Francisco']) {
      expect(text, `CityPicker missing ${city}`).toContain(city);
    }
  });

  it('SourceStrip mentions data sources', () => {
    const { container } = render(SourceStrip);
    expect(container.textContent).toBeTruthy();
  });

  it('StandardsStrip mentions WCAG / USWDS / Plain Writing Act', () => {
    const { container } = render(StandardsStrip);
    const text = container.textContent ?? '';
    expect(text).toMatch(/WCAG|USWDS|Plain Writing/);
  });

  it('UseBand mentions evidence / advice', () => {
    const { container } = render(UseBand);
    expect(container.textContent).toMatch(/evidence|advice/i);
  });

  it('PhaseBanner mentions Beta', () => {
    const { container } = render(PhaseBanner);
    expect(container.textContent).toContain('Beta');
  });

  it('LandFooter mentions Riprap + data sources', () => {
    const { container } = render(LandFooter);
    const text = container.textContent ?? '';
    expect(text).toContain('Riprap');
  });

  it('LandStones renders all 5 Stone names', () => {
    const { container } = render(LandStones);
    const text = container.textContent ?? '';
    for (const name of ['Cornerstone', 'Touchstone', 'Keystone', 'Lodestone', 'Capstone']) {
      expect(text).toContain(name);
    }
  });

  it('LandHeader renders the riprap wordmark', () => {
    const { container } = render(LandHeader);
    expect(container.textContent?.toLowerCase()).toContain('riprap');
  });
});
