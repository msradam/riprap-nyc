/**
 * Cold-start `/` — sample queries, FloodHelpNY redirect, trust-signals
 * footer copy. Static; no backend required.
 */
import { test, expect } from '@playwright/test';

test.describe('/ cold start', () => {
  test('renders three sample queries + the resident redirect + footer copy', async ({ page }) => {
    await page.goto('/');

    await expect(page.locator('.cold-start-deck').first())
      .toContainText('citation-grounded flood-exposure briefing tool');

    // FloodHelpNY redirect must be present in resident-mode framing.
    // (One in the cold-start band, one in the footer — both required.)
    const floodHelpLinks = page.getByRole('link', { name: /FloodHelpNY/ });
    await expect(floodHelpLinks).toHaveCount(2);
    for (const link of await floodHelpLinks.all()) {
      await expect(link).toHaveAttribute('href', /floodhelpny\.org/);
    }

    const samples = page.locator('.cold-start-sample');
    await expect(samples).toHaveCount(3);

    // Footer trust-signals copy is non-negotiable per design spec.
    await expect(page.locator('.app-footer-build'))
      .toContainText('No commercial APIs contacted at runtime');
    await expect(page.locator('.app-footer-build'))
      .toContainText('v0.4.2');
  });

  test('clicking a sample query navigates to /q/<query>', async ({ page }) => {
    await page.goto('/');
    await page.locator('.cold-start-sample').first().click();
    await expect(page).toHaveURL(/\/q\/.+/);
  });
});
