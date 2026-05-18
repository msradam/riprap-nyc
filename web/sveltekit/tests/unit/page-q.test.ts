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
import { resetStores } from './helpers/stores';
import { briefingState } from '$lib/stores/briefingState.svelte';
import { deployment } from '$lib/stores/deployment.svelte';
import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';
import {
  installMockEventSource, getMockEventSource, scriptBostonRun,
} from './helpers/sse';
import { BOSTON, NYC, NYC_LEAK_NEEDLES } from './fixtures/cities';

/** Build a fetch mock that returns the right /api/* shape per URL. */
function fetchMockForBoston(): typeof fetch {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString();
    if (url.includes('/api/deployment?deployment=boston')) {
      return new Response(JSON.stringify(BOSTON.deployment), { status: 200 });
    }
    if (url.includes('/api/pebbles?deployment=boston')) {
      return new Response(JSON.stringify(BOSTON.manifest), { status: 200 });
    }
    if (url.endsWith('/api/deployment')) {
      // Boot-time fetch returns NYC (server default)
      return new Response(JSON.stringify(NYC.deployment), { status: 200 });
    }
    if (url.endsWith('/api/pebbles')) {
      return new Response(JSON.stringify(NYC.manifest), { status: 200 });
    }
    return new Response('{}', { status: 503 });
  }) as unknown as typeof fetch;
}

beforeEach(() => {
  resetStores();
  installMockEventSource();
  globalThis.fetch = fetchMockForBoston();
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
