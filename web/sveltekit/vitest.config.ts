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
import { svelteTesting } from '@testing-library/svelte/vite';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  // svelteTesting() patches the vite-plugin-svelte config so component
  // tests can mount Svelte 5 runes-based components against happy-dom.
  // Skip preprocess + injected CSS — the tests assert on text content
  // (chip city, stone tagline, layer list), not on styling. Without
  // these options Vite's preprocessCSS crashes inside the test
  // worker with "Cannot create proxy with a non-object".
  plugins: [
    svelte({
      hot: false,
      preprocess: [],
      compilerOptions: { css: 'external' },
    }),
    svelteTesting(),
  ],
  resolve: {
    // Mirror the SvelteKit `$lib` alias so tests can import the same
    // way the app code does (`import { ... } from '$lib/...'`).
    // The `$app/*` aliases point at .svelte.ts shims so Svelte 5
    // runes (`$state`, `$derived`) compile correctly inside the shim
    // — bare .ts files trigger rune_outside_svelte at import time.
    alias: {
      $lib: resolve(__dirname, 'src/lib'),
      '$app/state': resolve(__dirname, 'src/.tests-shim/app/state.svelte.ts'),
      '$app/environment': resolve(__dirname, 'src/.tests-shim/app/environment.svelte.ts'),
      '$app/navigation': resolve(__dirname, 'src/.tests-shim/app/navigation.ts'),
      '$app/stores': resolve(__dirname, 'src/.tests-shim/app/state.svelte.ts'),
      $app: resolve(__dirname, 'src/.tests-shim/app'),
    },
    conditions: ['browser']
  },
  test: {
    environment: 'happy-dom',  // faster than jsdom for Svelte 5 + DOM-heavy tests
    setupFiles: ['./tests/unit/setup.ts'],
    include: ['tests/unit/**/*.test.ts'],
    globals: true
  }
});
