/**
 * AppFooter — footer with the "informational only" disclaimer.
 * Previously hardcoded the NYC-only residents-resource links
 * (FloodHelpNY, FloodNet NYC) into every footer render. Now those
 * are gated on the active deployment being NYC.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render } from '@testing-library/svelte';
import AppFooter from '$lib/components/shell/AppFooter.svelte';
import { resetStores, seedForCity } from '../helpers/stores';
import { ALL_CITIES, BOSTON, NYC } from '../fixtures/cities';

beforeEach(resetStores);

describe('AppFooter NYC-only resource links are deployment-gated', () => {
  it('renders FloodHelpNY + FloodNet NYC under NYC chip', () => {
    seedForCity(NYC);
    const { container } = render(AppFooter);
    const text = container.textContent ?? '';
    expect(text).toContain('FloodHelpNY');
    expect(text).toContain('FloodNet NYC');
  });

  it('hides FloodHelpNY + FloodNet NYC under Boston chip', () => {
    seedForCity(BOSTON);
    const { container } = render(AppFooter);
    const text = container.textContent ?? '';
    expect(text).not.toContain('FloodHelpNY');
    expect(text).not.toContain('FloodNet NYC');
  });

  it.each(ALL_CITIES.filter((c) => c.key !== 'nyc').map((c) => [c.key, c] as const))(
    '%s footer contains zero NYC-only resource link',
    (_key, city) => {
      resetStores();
      seedForCity(city);
      const { container } = render(AppFooter);
      const text = container.textContent ?? '';
      expect(text).not.toContain('FloodHelpNY');
      expect(text).not.toContain('FloodNet NYC');
      expect(text).not.toContain('floodhelpny.org');
      expect(text).not.toContain('floodnet.nyc');
    },
  );

  it('always shows the universal disclaimer regardless of deployment', () => {
    seedForCity(BOSTON);
    const { container } = render(AppFooter);
    const text = container.textContent ?? '';
    expect(text).toContain('Riprap is a reference dossier');
    expect(text).toContain('informational only');
  });
});
