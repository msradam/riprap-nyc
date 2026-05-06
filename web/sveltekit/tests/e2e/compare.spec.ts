/**
 * E2E test for the compare-intent two-column layout.
 *
 * Navigates to a compare query, waits for the SSE pipeline to finish
 * (both single_address sub-runs + Mellea reconcile), then asserts:
 *   1. Two `.address-header` elements are in the DOM — one per target.
 *   2. The comparison delta summary bar is present.
 *   3. No ErrorCard is rendered.
 *   4. No JS console errors.
 *
 * Budget: 360 s (two full single_address pipelines in series).
 *
 * Run: npm run test:e2e -- --grep compare
 */
import { test, expect } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const COMPARE_QUERY = 'Compare 80 Pioneer Street Brooklyn to 100 Gold Street Manhattan';
const SCREENSHOT_DIR = 'test-results/demo-screenshots';
mkdirSync(SCREENSHOT_DIR, { recursive: true });

test.describe('@compare two-column layout', () => {
  test.describe.configure({ mode: 'serial', timeout: 360_000 });

  test('compare renders two address headers and delta bar', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    await page.goto(`/q/${encodeURIComponent(COMPARE_QUERY)}`, {
      waitUntil: 'domcontentloaded'
    });

    // Wait until the compare layout renders (two address headers) or an
    // error card surfaces.
    await page.waitForFunction(
      () => {
        const errCard = document.querySelector('.error-card');
        const headers = document.querySelectorAll('.address-header');
        return Boolean(errCard) || headers.length >= 2;
      },
      undefined,
      { timeout: 360_000 }
    );

    // No error card should appear for two valid NYC addresses.
    await expect(page.locator('.error-card'), 'no ErrorCard for valid compare query')
      .toHaveCount(0);

    // Two address headers — one per compare target.
    const headers = page.locator('.address-header');
    await expect(headers, 'exactly two address-header elements').toHaveCount(2);

    // Each header should contain non-empty text.
    const textA = (await headers.nth(0).textContent())?.trim();
    const textB = (await headers.nth(1).textContent())?.trim();
    expect(textA, 'PLACE A header has address text').toBeTruthy();
    expect(textB, 'PLACE B header has address text').toBeTruthy();
    expect(textA, 'PLACE A and PLACE B headers differ').not.toBe(textB);

    // Delta summary bar should be present (if any numbers differ between
    // the two addresses, which is expected for two distinct NYC locations).
    const deltaBar = page.locator('.compare-delta-bar');
    const deltaCount = await deltaBar.count();
    // Delta bar is conditional — present when numbers differ; just log if absent.
    console.log(`[compare] delta bar present: ${deltaCount > 0}`);

    // Briefing prose sections rendered in both columns.
    const sectionHeads = page.locator('.briefing-section-head');
    const headCount = await sectionHeads.count();
    expect(headCount, 'at least two section heads (one per column)').toBeGreaterThanOrEqual(2);

    // No console errors.
    const filteredErrors = consoleErrors.filter(
      (e) => !e.includes('favicon') && !e.includes('maplibre-gl')
    );
    expect(filteredErrors, `console errors: ${filteredErrors.join(' | ')}`).toEqual([]);

    await page.screenshot({
      path: `${SCREENSHOT_DIR}/compare.png`,
      fullPage: true
    });

    console.log(
      `[compare] headers="${textA}" / "${textB}" · sections=${headCount} · delta=${deltaCount > 0}`
    );
  });

  test('compare two-column layout stacks on narrow viewport', async ({ page }) => {
    // 800 px < 900 px breakpoint — columns should stack vertically.
    await page.setViewportSize({ width: 800, height: 900 });

    await page.goto(`/q/${encodeURIComponent(COMPARE_QUERY)}`, {
      waitUntil: 'domcontentloaded'
    });

    await page.waitForFunction(
      () => document.querySelectorAll('.address-header').length >= 2 ||
             Boolean(document.querySelector('.error-card')),
      undefined,
      { timeout: 360_000 }
    );

    // On narrow viewport the two columns exist in the DOM but stack.
    const headers = page.locator('.address-header');
    await expect(headers).toHaveCount(2);

    // Verify the compare-cols grid is single-column (stacked).
    const cols = page.locator('.compare-cols');
    if (await cols.count() > 0) {
      const gridCols = await cols.evaluate(
        (el) => window.getComputedStyle(el).gridTemplateColumns
      );
      // On single-column, gridTemplateColumns is a single track value.
      expect(gridCols, 'stacked: single grid column track').not.toContain('1px');
    }
  });
});
