/**
 * Vitest config — Node-side unit tests with Svelte 5 runes support.
 *
 * Targets `tests/unit/**` for things we want to assert without a
 * browser: cardAdapter (given an API response + manifest, what cards
 * does the UI emit?), data-flow stores, etc.
 *
 * jsdom is the test environment so `$lib/stores/*.svelte.ts` files
 * (which use Svelte 5 runes) compile and execute under @vitest/vite.
 *
 * `npm run test:unit` runs the suite. Distinct from `test:e2e`
 * (Playwright, needs a live uvicorn) — these run fully offline.
 */
import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [svelte({ hot: false })],
  resolve: {
    // Mirror the SvelteKit `$lib` alias so tests can import the same
    // way the app code does (`import { ... } from '$lib/...'`).
    alias: {
      $lib: resolve(__dirname, 'src/lib'),
      $app: resolve(__dirname, 'src/.tests-shim/app'),
    },
    conditions: ['browser']
  },
  test: {
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.ts'],
    globals: true
  }
});
