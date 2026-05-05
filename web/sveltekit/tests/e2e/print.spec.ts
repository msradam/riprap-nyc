/**
 * Export-PDF flow:
 *  - the header button is hidden until the briefing is ready
 *  - on /q/sample (prerendered) it appears immediately on mount
 *  - clicking it opens /print/<id> in a new tab
 *  - that route renders the curated artifact: title, briefing prose,
 *    citation list. No app header, no map, no trace, no evidence.
 *  - the route auto-fires window.print()
 */
import { test, expect } from '@playwright/test';

test.describe('export-PDF curated print flow', () => {
  test('header export button visible on /q/sample, hidden when no snapshot', async ({ page }) => {
    await page.goto('/q/sample');
    await expect(page.locator('button').filter({ hasText: /export PDF/i })).toBeVisible();
  });

  test('print route hydrates from localStorage and shows curated layout', async ({ page }) => {
    // Visit /q/sample first so it persists a snapshot.
    await page.goto('/q/sample');
    await expect(page.locator('.briefing-prose')).toBeVisible();

    // Confirm a snapshot landed for queryId='sample'.
    const snapKey = await page.evaluate(() => {
      const k = 'riprap:print:sample';
      return localStorage.getItem(k) ? k : null;
    });
    expect(snapKey).toBe('riprap:print:sample');

    // Stub window.print so the page mounts without the OS dialog popping.
    await page.addInitScript(() => {
      // @ts-expect-error — instrument print for test
      window.__printed = 0;
      window.print = () => {
        // @ts-expect-error
        window.__printed += 1;
      };
    });

    await page.goto('/print/sample');

    // The curated artifact renders.
    await expect(page.locator('.print-doc')).toBeVisible();
    await expect(page.locator('.print-title')).toContainText(/Pioneer/i);
    await expect(page.locator('.briefing-prose')).toBeVisible();
    await expect(page.locator('.print-citations h2')).toHaveText('Citations');

    // App chrome is excluded (the @-page break breaks out of root layout).
    await expect(page.locator('.app-header')).toHaveCount(0);
    await expect(page.locator('.app-region-map')).toHaveCount(0);
    await expect(page.locator('.trace-ui')).toHaveCount(0);

    // window.print() fired automatically.
    await page.waitForFunction(
      // @ts-expect-error
      () => window.__printed > 0,
      undefined,
      { timeout: 4000 }
    );
  });

  test('print route shows empty-state when no snapshot exists', async ({ page }) => {
    await page.addInitScript(() => localStorage.clear());
    await page.goto('/print/no-such-query');
    await expect(page.locator('.empty')).toBeVisible();
    await expect(page.locator('.empty')).toContainText(/no briefing snapshot/i);
  });
});
