/**
 * Vitest setup — runs once per worker before any test file.
 *
 *   - @testing-library/jest-dom plugs into expect() so we can write
 *     `expect(el).toBeInTheDocument()` etc. instead of poking at
 *     innerHTML by hand.
 *   - @testing-library/svelte's cleanup() runs after every test so
 *     each `render()` call gets a fresh DOM — without this the
 *     `<body>` accumulates mounted components across tests and
 *     queries return the wrong nodes.
 */
import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/svelte';

afterEach(() => {
  cleanup();
});

/**
 * Mock fetch globally so component $effects that call /api/* don't
 * throw ECONNREFUSED at happy-dom (no server is running in unit
 * tests). Returns a 503 by default so deployment.load() / pebbleManifest.load()
 * fall into their error branch without affecting test outcomes —
 * tests seed the stores directly via helpers/stores.ts.
 *
 * Individual tests can override per-call via vi.mocked(globalThis.fetch).
 */
globalThis.fetch = vi.fn(() =>
  Promise.resolve(new Response(JSON.stringify({ error: 'mocked' }), {
    status: 503,
    headers: { 'content-type': 'application/json' },
  })),
) as unknown as typeof fetch;
