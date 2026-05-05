import { defineConfig, devices } from '@playwright/test';

/**
 * Headless E2E for the Riprap UI. Targets a *running* uvicorn on
 * 127.0.0.1:7860 — we don't spin up our own server because the live
 * route depends on the FastAPI backend (planner, FSM, SSE, layer
 * endpoints). Static-route tests work against /q/sample which is
 * fully prerendered.
 *
 * Run with `npm run test:e2e` (uvicorn must already be up). The
 * matrix `npm run check:all` will fail loudly if uvicorn isn't on
 * the port — that's the design.
 */
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: process.env.RIPRAP_BASE_URL || 'http://127.0.0.1:7860',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    headless: true
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } }
  ]
});
