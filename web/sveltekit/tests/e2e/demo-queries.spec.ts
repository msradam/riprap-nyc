/**
 * End-to-end demo-query rigour. Exercises the live FastAPI SSE pipeline
 * (planner → FSM → Mellea reconcile) for the canonical demo addresses
 * and asserts the briefing renders all four design-system surfaces:
 *   1. plan event arrives
 *   2. specialists step events arrive
 *   3. reconciler emits tokens
 *   4. final event lands → briefing prose populates with claim glyphs
 *   5. citation drawer fills (per-query minimum)
 *   6. trace summary shows fired/silent/errors counts
 *   7. NO ErrorCard banner unless `expectError` is set
 *   8. screenshot saved for the deck
 *
 * Per-query knobs:
 *   - minCitations         lower bound; out-of-scope = 0, full briefing = 2-5
 *   - expectError          allow ErrorCard surfaced (e.g. all-silent for OOS)
 *   - expectRegisterCards  assert ≥1 RegisterCard renders (NYCHA / school /
 *                          hospital / subway). Requires
 *                          RIPRAP_HEAVY_SPECIALISTS=1; safely skipped when off.
 *   - expectLiveNow        live_now intent — no Mellea reconcile, faster path
 *
 * Run with `npm run test:demo`. Per-query budget 240 s.
 */
import { test, expect } from '@playwright/test';
import { mkdirSync } from 'node:fs';

interface DemoQuery {
  name: string;
  query: string;
  minCitations: number;
  expectError?: boolean;
  expectRegisterCards?: boolean;
  expectLiveNow?: boolean;
  notes?: string;
}

const DEMO_QUERIES: DemoQuery[] = [
  // ── Canonical pre-vetted set (already passing on local Ollama) ───────
  { name: 'red-hook',
    query: '80 Pioneer Street, Red Hook, Brooklyn',
    minCitations: 2,
    notes: 'single_address, 9 specialists. Sandy + DEP + FloodNet hits.' },
  { name: 'far-rockaway',
    query: 'Far Rockaway flood exposure briefing',
    minCitations: 2,
    notes: 'neighborhood, NTA-mode, sandy_clipped + dep_clipped polygons.' },
  { name: 'coney-island',
    query: 'Coney Island Brooklyn',
    minCitations: 2,
    notes: 'neighborhood, register-card territory.' },
  { name: 'hollis',
    query: 'Hollis',
    minCitations: 1,
    notes: 'Mellea reroll demo path (0.19% → 19% case per MONDAY.md).' },

  // ── Curatorial top-5 additions ───────────────────────────────────────
  { name: 'red-hook-houses-nycha',
    query: 'Red Hook Houses NYCHA',
    minCitations: 2,
    expectRegisterCards: true,
    notes: '2,878-unit NYCHA development with high Sandy-Inundation overlap. '
         + 'NYCHA register card showcase. Requires HEAVY=1 for register hit.' },
  { name: 'nyu-langone',
    query: 'NYU Langone Hospital, Manhattan',
    minCitations: 2,
    expectRegisterCards: true,
    notes: 'Hospitals register card; Sandy-2012 storm-tide memory; healthcare '
         + 'flood-resilience narrative.' },
  { name: 'battery-live-now',
    query: 'current conditions at the Battery, Manhattan',
    minCitations: 1,
    expectLiveNow: true,
    notes: 'live_now intent: NOAA Battery gauge + NWS active alerts + TTM '
         + 'surge nowcast. Streams in seconds, not minutes.' },
  { name: 'gowanus-superfund',
    query: 'Gowanus Canal Superfund flood exposure briefing',
    minCitations: 2,
    notes: 'Dense modeled + proxy tiers; Superfund + flood is the story.' },
  { name: 'sheepshead-bay',
    query: 'Sheepshead Bay flood exposure briefing',
    minCitations: 2,
    expectRegisterCards: true,
    notes: 'Canonical register-card showcase per spec §15 worked example: '
         + 'subway entrances + NYCHA + schools + hospitals all hit.' },

  // ── Honest-scope demo (out of NYC) ───────────────────────────────────
  { name: 'downing-street-london',
    query: '10 Downing Street, London',
    minCitations: 0,
    notes: 'Geocodes successfully then every NYC specialist falls silent. '
         + 'Tests silence-over-confabulation more vividly than any in-scope '
         + 'query. Allows ErrorCard (all-silent) OR honest "no grounded data" '
         + 'briefing — both are correct outcomes.',
    expectError: true /* may surface all-silent ErrorCard, that's correct */ }
];

const SCREENSHOT_DIR = 'test-results/demo-screenshots';
mkdirSync(SCREENSHOT_DIR, { recursive: true });

test.describe('@demo live SSE end-to-end', () => {
  test.describe.configure({ mode: 'serial', timeout: 360_000 });

  for (const d of DEMO_QUERIES) {
    test(d.name, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });

      const consoleErrors: string[] = [];
      page.on('console', (msg) => {
        if (msg.type() === 'error') consoleErrors.push(msg.text());
      });

      await page.goto(`/q/${encodeURIComponent(d.query)}`, { waitUntil: 'domcontentloaded' });

      // Wait for either the briefing prose to settle or an ErrorCard to
      // appear (out-of-scope path can land on the all-silent ErrorCard).
      // Live-now is briefer because there's no Mellea reconcile.
      const settleTimeout = d.expectLiveNow ? 60_000 : 320_000;
      await page.waitForFunction(
        () => {
          const errCard = document.querySelector('.error-card');
          const briefing = document.querySelector('.briefing-prose');
          const caret = document.querySelector('.streaming-caret');
          return Boolean(errCard) || (briefing != null && caret == null);
        },
        undefined,
        { timeout: settleTimeout }
      );

      // ── Asserts ────────────────────────────────────────────────────
      const errorCardCount = await page.locator('.error-card').count();
      if (!d.expectError) {
        expect(errorCardCount,
          `unexpected error card for "${d.query}"`).toBe(0);
      }
      let headCount = 0;
      let citeCount = 0;
      if (errorCardCount === 0) {
        // Briefing rendered — full asserts.
        const heads = page.locator('.briefing-section-head');
        headCount = await heads.count();
        expect(headCount,
          `at least one section head should render for "${d.query}"`).toBeGreaterThan(0);

        const claimGlyphs = page.locator('.claim-glyph svg[role="img"]');
        const claimCount = await claimGlyphs.count();
        if (d.minCitations > 0) {
          expect(claimCount,
            `at least one tier-glyph claim should render for "${d.query}"`
          ).toBeGreaterThan(0);
        }

        const cites = page.locator('.citation-drawer .citation-item');
        citeCount = await cites.count();
        expect(citeCount, `≥${d.minCitations} citations for "${d.query}"`)
          .toBeGreaterThanOrEqual(d.minCitations);
      }

      // Trace summary always shows counts.
      await expect(page.locator('.trace-head-meta')).toContainText('fired');

      // Map: only assert legend has features when the map mounted AND we
      // have any data at all (out-of-scope correctly has all-empty layers).
      let legendItems = 0;
      const mapMounted = await page.locator('.maplibregl-canvas').count();
      if (mapMounted > 0) {
        await page.waitForTimeout(1500);
        legendItems = await page.locator('.map-legend-item').count();
        // Don't enforce ≥1 for out-of-scope or live-now.
        if (!d.expectError && !d.expectLiveNow && d.minCitations > 0) {
          expect(legendItems,
            `at least one tier layer should have features for "${d.query}"`
          ).toBeGreaterThan(0);
        }
      }

      // Optional: register cards present (when HEAVY specialists active).
      let registerCardCount = 0;
      if (d.expectRegisterCards) {
        registerCardCount = await page.locator('.register-card').count();
        if (process.env.RIPRAP_HEAVY_SPECIALISTS === '1') {
          expect(registerCardCount,
            `≥1 RegisterCard for "${d.query}" with HEAVY=1`).toBeGreaterThan(0);
        }
        // With HEAVY off, register-card absence is expected; just log.
      }

      // No console errors during the run.
      const filteredErrors = consoleErrors.filter((e) =>
        !e.includes('favicon') && !e.includes('maplibre-gl')
      );
      expect(filteredErrors,
        `console errors during "${d.query}": ${filteredErrors.join(' | ')}`
      ).toEqual([]);

      await page.screenshot({
        path: `${SCREENSHOT_DIR}/${d.name}.png`,
        fullPage: true
      });

      // One-line demo log.
      const heading = await page.locator('.brief-h1-addr').textContent();
      const intentMeta = await page.locator('.region-head-meta').first().textContent();
      const tags: string[] = [];
      if (errorCardCount > 0) tags.push('ErrorCard');
      if (registerCardCount > 0) tags.push(`registers=${registerCardCount}`);
      if (d.expectLiveNow) tags.push('live_now');
      const tagStr = tags.length ? ` [${tags.join(' · ')}]` : '';
      console.log(`[${d.name}] ${heading?.trim()} · sections=${headCount} cites=${citeCount} legend=${legendItems}${tagStr} · ${intentMeta?.trim()}`);
    });
  }
});
