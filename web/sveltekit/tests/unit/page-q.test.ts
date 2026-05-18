/**
 * Page-level integration test for /q/[queryId]/+page.svelte.
 *
 * Mounts the actual page component with a mocked EventSource +
 * deployment-aware fetch mock. Drives a scripted Boston SSE run
 * through the lifecycle and asserts the UI pivots correctly:
 *
 *   - chip swaps from boot NYC → Boston after the `deployment` event
 *   - pebble scaffold reloads via /api/pebbles?deployment=boston
 *   - status pill hides after `done` (the "stuck on Gathering
 *     evidence (9/10)" bug from the user's screenshot)
 *   - no NYC string leaks anywhere in the final DOM
 *
 * This is what makes the UI test harness FULL: previous tests mount
 * one component at a time; this one renders the whole route as a
 * user would see it.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, waitFor } from '@testing-library/svelte';
import { tick } from 'svelte';
import Page from '../../src/routes/q/[queryId]/+page.svelte';
import { resetStores, seedForCity } from './helpers/stores';
import { briefingState } from '$lib/stores/briefingState.svelte';
import { deployment } from '$lib/stores/deployment.svelte';
import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';
import {
  installMockEventSource, getMockEventSource, scriptBostonRun, scriptCityRun,
} from './helpers/sse';
import {
  ALL_CITIES, BOSTON, NYC, CHICAGO, SEATTLE, SF, ELSEWHERE,
  NYC_LEAK_NEEDLES, type CityFixture,
} from './fixtures/cities';

/** Build a fetch mock that routes `?deployment=<name>` requests to the
 *  right CityFixture. No-arg /api/* returns the boot deployment (NYC,
 *  matching the server's default). */
function fetchMockForCities(boot: CityFixture = NYC): typeof fetch {
  const fixturesByName = new Map<string, CityFixture>(
    ALL_CITIES.map((c) => [c.key, c]),
  );
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString();
    const depMatch = url.match(/[?&]deployment=([^&]+)/);
    if (depMatch) {
      const name = decodeURIComponent(depMatch[1]);
      const fixture = fixturesByName.get(name);
      if (!fixture) return new Response('{}', { status: 404 });
      if (url.includes('/api/deployment')) {
        return new Response(JSON.stringify(fixture.deployment), { status: 200 });
      }
      if (url.includes('/api/pebbles')) {
        return new Response(JSON.stringify(fixture.manifest), { status: 200 });
      }
    }
    if (url.endsWith('/api/deployment')) {
      return new Response(JSON.stringify(boot.deployment), { status: 200 });
    }
    if (url.endsWith('/api/pebbles')) {
      return new Response(JSON.stringify(boot.manifest), { status: 200 });
    }
    return new Response('{}', { status: 503 });
  }) as unknown as typeof fetch;
}

beforeEach(() => {
  resetStores();
  installMockEventSource();
  globalThis.fetch = fetchMockForCities();
});

describe('/q/[queryId] full-page SSE lifecycle for Boston', () => {
  it('pivots chip + scaffold + status across the handshake', async () => {
    const { container } = render(Page);
    const es = getMockEventSource();

    // Initial state (before any SSE event): chip might be boot NYC,
    // scaffold loading. Status pill should be visible (phase != idle).
    await tick();

    // Drive the full Boston run through SSE
    await scriptBostonRun(es);
    // Allow microtasks: deployment.setForQuery + pebbleManifest.loadForDeployment
    // both await fetch promises before mutating stores.
    await waitFor(
      () => {
        expect(deployment.current?.name).toBe('boston');
      },
      { timeout: 1000 },
    );
    await waitFor(
      () => {
        expect(pebbleManifest.loadedFor).toBe('boston');
      },
      { timeout: 1000 },
    );

    // briefingState should settle to 'done' after the SSE 'done' event
    expect(briefingState.phase).toBe('done');
    expect(briefingState.ready).toBe(true);

    // Final DOM contains no NYC needle
    const text = container.textContent ?? '';
    const leaked = NYC_LEAK_NEEDLES.filter((needle) => text.includes(needle));
    expect(leaked,
      `Boston-run page leaked NYC needles: ${leaked.join(', ')}`,
    ).toEqual([]);

    // And contains Boston-specific content
    expect(text).toContain('Boston');
  });

  it('no error card when templated paragraph arrived (all-silent guard)', async () => {
    const { container } = render(Page);
    const es = getMockEventSource();
    await tick();
    await scriptBostonRun(es);

    await waitFor(
      () => expect(briefingState.phase).toBe('done'),
      { timeout: 1000 },
    );

    // The "Outside evidence coverage" error card should NOT render
    // when a templated paragraph arrived via the `final` event.
    const text = container.textContent ?? '';
    expect(text).not.toContain('Outside evidence coverage');
    expect(text).not.toContain('No specialists found evidence');
  });
});

describe('/q/[queryId] full-page SSE × all shipped cities — no cross-city leakage', () => {
  for (const city of [NYC, BOSTON, CHICAGO, SEATTLE, SF]) {
    it(`${city.key} run: chip + scaffold settle, only city-appropriate content`, async () => {
      const { container } = render(Page);
      const es = getMockEventSource();
      await tick();

      const pebbleIds = city.manifest.pebbles.map((p) => p.id);
      await scriptCityRun(es, {
        name: city.key,
        city: city.deployment.city,
        state: null,
        address: city.geocode.address,
        lat: city.geocode.lat,
        lon: city.geocode.lon,
        pebbles: pebbleIds,
        paragraph: `Templated paragraph for ${city.deployment.city}.`,
      });

      await waitFor(
        () => expect(deployment.current?.name).toBe(city.key),
        { timeout: 1000 },
      );
      await waitFor(
        () => expect(pebbleManifest.loadedFor).toBe(city.key),
        { timeout: 1000 },
      );
      expect(briefingState.phase).toBe('done');

      const text = container.textContent ?? '';

      // The routed-to city name appears somewhere on the page.
      expect(text,
        `${city.key} run page is missing the deployment city '${city.deployment.city}'`,
      ).toContain(city.deployment.city);

      // For non-NYC cities, zero NYC needles anywhere.
      if (city.key !== 'nyc') {
        const leaked = NYC_LEAK_NEEDLES.filter((n) => text.includes(n));
        expect(leaked,
          `${city.key} run leaked NYC needles: ${leaked.join(', ')}`,
        ).toEqual([]);
        expect(text,
          `${city.key} run still contains literal "NYC" somewhere`,
        ).not.toMatch(/\bNYC\b/);
      }

      // Every city should NOT render the "Outside evidence coverage"
      // error card when its templated paragraph arrived.
      expect(text).not.toContain('Outside evidence coverage');
    });
  }
});

describe('/q/[queryId] no-deployment (out-of-coverage) lifecycle', () => {
  it('chip falls back to neutral and no NYC leaks under ELSEWHERE', async () => {
    const { container } = render(Page);
    const es = getMockEventSource();
    await tick();

    // Emit the geocode + deployment-null sequence
    es.emit('hello', { query: 'Albuquerque' });
    es.emit('plan', { intent: 'single_address', targets: [], specialists: [],
                      rationale: '' });
    es.emit('step', { kind: 'step', step: 'geocode', ok: true,
                      result: { address: 'Civic Plaza, Albuquerque, NM',
                                lat: 35.0844, lon: -106.6504 } });
    es.emit('deployment', { name: '__none__', city: null, state: null });
    es.emit('final', { paragraph: 'Out of coverage briefing.',
                       intent: 'single_address',
                       mellea: { passed: [], failed: [], attempts: 0 },
                       citations: [] });
    es.emit('done', {});

    await waitFor(
      () => expect(deployment.current?.city).toBe('Not in any shipped deployment'),
      { timeout: 1000 },
    );

    const text = container.textContent ?? '';
    // No NYC ghosts — the neutral fallback was honest, not NYC-flavoured.
    expect(text).not.toMatch(/\bNYC\b/);
    for (const needle of NYC_LEAK_NEEDLES) {
      expect(text, `ELSEWHERE page leaked NYC needle "${needle}"`).not.toContain(needle);
    }
  });
});

describe('/q/[queryId] SSE error BEFORE the deployment handshake', () => {
  it('clears the boot NYC scaffold so the error card stands alone', async () => {
    // Pre-seed boot NYC into both stores (mirror what AppHeader's
    // $effect + the page's onMount pebbleManifest.load() would do
    // on first render — they fire BEFORE any SSE event lands).
    resetStores();
    seedForCity(NYC);
    // Boot fall-through reality: load() with no deployment arg
    // leaves loadedFor=null even though stones[]/byStone is NYC.
    pebbleManifest.loadedFor = null;
    expect(pebbleManifest.loadedFor).toBeNull();
    expect(deployment.current?.name).toBe('nyc');

    const { container } = render(Page);
    const es = getMockEventSource();
    await tick();

    // Backend dies before geocode / deployment events ever fire.
    es.emit('hello', { query: '600 4th Avenue, Seattle, WA' });
    es.emit('error', { err: 'SSE connection error: 503 Service Unavailable' });

    // Wait for the scaffold-clear to land.
    await waitFor(
      () => expect(pebbleManifest.byId).toEqual({}),
      { timeout: 1000 },
    );
    expect(pebbleManifest.stones).toEqual([]);

    // The chip should also be neutralized — it WAS NYC before the
    // error, but with the deployment handshake never completing the
    // page must not claim it's an NYC briefing.
    expect(deployment.current?.name).not.toBe('nyc');

    // The rendered DOM no longer carries NYC needles.
    const text = container.textContent ?? '';
    for (const needle of NYC_LEAK_NEEDLES) {
      expect(text,
        `pre-handshake error left NYC needle "${needle}" in the rendered page`,
      ).not.toContain(needle);
    }
  });
});
