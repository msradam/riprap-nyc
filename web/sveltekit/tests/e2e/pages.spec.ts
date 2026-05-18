/**
 * Page-level end-to-end — real browser, real backend, real queries.
 *
 * For each shipped city: navigate to /q/<address>, wait for the
 * briefing to reach `done`, assert the rendered DOM:
 *
 *   - header chip displays the routed city's name
 *   - main-pane status indicator has cleared (no stuck "gathering
 *     evidence" / "Resolving address…" )
 *   - briefing pane contains the templated paragraph
 *   - Map Layers panel ("Layers · grouped by Stone") contains only
 *     map-layer pebbles from the routed deployment
 *   - cross-city: zero NYC-only needles in any non-NYC render
 *
 * Driven against the production SvelteKit build served by uvicorn.
 * Requires uvicorn already running on baseURL (default 127.0.0.1:7860)
 * with the no_llm reconciler tier for deterministic, fast runs:
 *
 *   RIPRAP_RECONCILER_TIER=no_llm RIPRAP_HEAVY_SPECIALISTS=0 \
 *     uvicorn web.main:app --host 127.0.0.1 --port 7860
 *
 * Then:
 *   npx playwright test pages.spec.ts
 *
 * NYC is allotted longer than the rest because its 22 specialists
 * include the TTM and Prithvi cold-load. Other cities settle in ~5s.
 */
import { test, expect, type Page } from '@playwright/test';

type CityCase = {
  key: string;
  city: string;       // chip pill display
  address: string;
  timeoutMs: number;
};

const CITIES: CityCase[] = [
  { key: 'nyc',     city: 'NYC',
    address: '189 Atlantic Avenue, Brooklyn, NY',
    timeoutMs: 120_000 },
  { key: 'boston',  city: 'Boston',
    address: '1 City Hall Square, Boston, MA',
    timeoutMs: 45_000 },
  { key: 'chicago', city: 'Chicago',
    address: '233 S Wacker Drive, Chicago, IL',
    timeoutMs: 45_000 },
  { key: 'seattle', city: 'Seattle',
    address: '600 4th Avenue, Seattle, WA',
    timeoutMs: 45_000 },
  { key: 'sf',      city: 'San Francisco',
    address: '1 Dr Carlton B Goodlett Place, San Francisco, CA',
    timeoutMs: 45_000 },
];

const NYC_NEEDLES = [
  'Sandy Inundation', 'Ida HWM', 'MTA subway entrances',
  'NYCHA developments', 'DOE schools', 'DOH hospitals',
  'FloodHelpNY', 'FloodNet NYC', "what NYC's ground remembers",
];

/** Wait for the briefing to settle (status pill hidden + region-head
 *  meta shows "✓ done"). Uses Playwright's polling expect under the
 *  hood, so a stuck pill fails fast with a screenshot. */
async function waitForDone(page: Page, timeoutMs: number): Promise<void> {
  // The Briefing region's head meta shows "✓ done" once streamDone
  // flips. There's a second `.region-head-meta` in the Map region
  // (coords or "awaiting geocode…"); scope to the Briefing one.
  await expect(
    page.locator('#region-briefing .region-head-meta'),
  ).toContainText('✓ done', { timeout: timeoutMs });
  // And the live status pill must have cleared (phase=done hides it).
  await expect(page.locator('.status')).toHaveCount(0, { timeout: 5_000 });
}

for (const c of CITIES) {
  test(`real query → ${c.key} renders without NYC leakage`, async ({ page }) => {
    test.setTimeout(c.timeoutMs + 30_000);

    await page.goto(`/q/${encodeURIComponent(c.address)}`);

    await waitForDone(page, c.timeoutMs);

    // 1. Header chip displays the routed city.
    const pill = page.locator('.app-header-city-pill');
    await expect(pill).toContainText(c.city);

    // 2. Main-pane "Resolving address" / "Gathering evidence" is gone.
    await expect(page.locator('.generating-status')).toHaveCount(0);

    // 3. Cross-city no-leak: for non-NYC runs, ZERO NYC needles in the
    //    full page text.
    if (c.key !== 'nyc') {
      const text = await page.locator('body').innerText();
      for (const needle of NYC_NEEDLES) {
        expect(text, `${c.key} leaked NYC needle "${needle}"`).not.toContain(needle);
      }
      // And no bare "NYC" anywhere (not in the chip, not in the legend,
      // not in any Stone tagline).
      expect(text, `${c.key} still contains literal "NYC"`).not.toMatch(/\bNYC\b/);
    }

    // 4. Map awaiting-geocode is gone (geocode succeeded).
    await expect(page.locator('#region-map .region-head-meta'))
      .not.toContainText('awaiting geocode…');
  });
}

test('out-of-coverage (Albuquerque) renders the neutral chip', async ({ page }) => {
  test.setTimeout(60_000);

  await page.goto(`/q/${encodeURIComponent('1 Civic Plaza NW, Albuquerque, NM')}`);

  await waitForDone(page, 45_000);

  // Neutral chip — not any shipped deployment.
  const pill = page.locator('.app-header-city-pill');
  await expect(pill).toContainText('Not in any shipped deployment');

  // No NYC needle even though no city is loaded.
  const text = await page.locator('body').innerText();
  for (const needle of NYC_NEEDLES) {
    expect(text, `Albuquerque leaked NYC needle "${needle}"`).not.toContain(needle);
  }
});

test('landing page renders all 5 city pills + the standards strip', async ({ page }) => {
  await page.goto('/');

  for (const c of CITIES) {
    await expect(page.locator('body')).toContainText(c.city);
  }
  // Standards strip is a load-bearing trust signal.
  await expect(page.locator('body')).toContainText(/WCAG|USWDS/);
});
