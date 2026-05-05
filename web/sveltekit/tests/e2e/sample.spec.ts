/**
 * Static demo route /q/sample.
 *
 * This is the prerendered worked example with hard-coded sample data —
 * it must render every design-system piece without an SSE connection or
 * a working LLM backend, so it's also the cheapest probe for design-
 * system regressions.
 */
import { test, expect } from '@playwright/test';

test.describe('/q/sample (prerendered demo)', () => {
  test('renders four-section briefing with claim glyphs + cite anchors', async ({ page }) => {
    await page.goto('/q/sample');

    // Header wordmark + region label
    await expect(page.locator('.riprap-wordmark')).toContainText('riprap');
    await expect(page.locator('h1.brief-h1')).toContainText('Flood-exposure briefing');

    // 4 canonical section heads
    const heads = page.locator('.briefing-section-head .briefing-section-num');
    await expect(heads).toHaveCount(4);
    await expect(heads.nth(0)).toHaveText('01');
    await expect(heads.nth(1)).toHaveText('02');
    await expect(heads.nth(2)).toHaveText('03');
    await expect(heads.nth(3)).toHaveText('04');

    // Tier glyphs in the prose gutter (one per claim)
    const claimGlyphs = page.locator('.claim-glyph svg[role="img"]');
    expect(await claimGlyphs.count()).toBeGreaterThan(5);

    // Inline citations link to drawer entries
    const cites = page.locator('a.inline-cite');
    expect(await cites.count()).toBeGreaterThan(5);
  });

  test('renders citation drawer with all 10 sample sources', async ({ page }) => {
    await page.goto('/q/sample');
    const items = page.locator('.citation-drawer .citation-item');
    await expect(items).toHaveCount(10);
    // Each item carries source label + tier glyph + doc id
    await expect(items.first().locator('.citation-source')).toBeVisible();
    await expect(items.first().locator('.citation-docid')).toBeVisible();
  });

  test('renders trace UI with all run steps', async ({ page }) => {
    await page.goto('/q/sample');
    await expect(page.locator('.trace-ui')).toBeVisible();
    // Trace head meta should show a non-zero total
    await expect(page.locator('.trace-head-meta')).toContainText('s total');
  });

  test('renders evidence grid with all 6 viz formats', async ({ page }) => {
    await page.goto('/q/sample');
    const cards = page.locator('.evidence-card');
    await expect(cards).toHaveCount(8);
    // Each tier is represented at least once
    for (const t of ['empirical', 'modeled', 'proxy', 'synthetic']) {
      expect(await page.locator(`.evidence-card-${t}`).count()).toBeGreaterThan(0);
    }
  });

  test('legend hides layers with zero features', async ({ page }) => {
    await page.goto('/q/sample');
    // /q/sample only ships a synthetic fixture (the others are 0).
    // Legend must show synthetic only — silence-over-confabulation
    // applied to the map (handoff hard rule #3).
    await expect(page.locator('.map-legend')).toBeVisible({ timeout: 10_000 });
    const items = page.locator('.map-legend-item');
    await expect(items).toHaveCount(1);
    await expect(items.first().locator('.map-legend-label'))
      .toContainText(/Synthetic SAR/);
    // Empty layers must not be present.
    await expect(page.locator('.map-legend-item', { hasText: 'Sandy' })).toHaveCount(0);
    await expect(page.locator('.map-legend-item', { hasText: '311' })).toHaveCount(0);
  });

  test('MapLibre map mounts and registers syn-stripe-45 pattern', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });
    await page.goto('/q/sample');

    // MapLibre canvas mounts
    const canvas = page.locator('.maplibregl-canvas');
    await expect(canvas).toBeVisible({ timeout: 15_000 });

    // Wait for `window.__riprapMap` to appear (RipMap.svelte sets it
    // on `map.on('load')`), then for the syn-stripe registration
    // promise to settle.
    await page.waitForFunction(
      () => Boolean((window as unknown as { __riprapMap?: unknown }).__riprapMap),
      undefined,
      { timeout: 15_000 }
    );
    // SVG → image decode happens asynchronously; give it a beat.
    await page.waitForFunction(
      () => {
        const m = (window as unknown as { __riprapMap?: { hasImage: (s: string) => boolean } })
          .__riprapMap;
        return Boolean(m && m.hasImage('syn-stripe-45'));
      },
      undefined,
      { timeout: 5_000 }
    );

    const mapState = await page.evaluate<{
      hasStripe: boolean;
      hasStripe2x: boolean;
      hasStripeLow: boolean;
      sources: string[];
      layers: string[];
    } | null>(() => {
      type MlMap = {
        loaded: () => boolean;
        hasImage: (id: string) => boolean;
        getStyle: () => { sources: Record<string, unknown>; layers: Array<{ id: string }> };
      };
      const map = (window as unknown as { __riprapMap?: MlMap }).__riprapMap;
      if (!map) return null;
      const style = map.getStyle();
      return {
        hasStripe: map.hasImage('syn-stripe-45'),
        hasStripe2x: map.hasImage('syn-stripe-45-2x'),
        hasStripeLow: map.hasImage('syn-stripe-45-low'),
        sources: Object.keys(style.sources),
        layers: style.layers.map((l) => l.id)
      };
    });

    expect(mapState, 'map instance should be reachable from the DOM').not.toBeNull();
    if (!mapState) return;

    // The sample route ships a synthetic-prior fixture polygon — verify
    // the syn-prior source has a non-empty FeatureCollection so the
    // syn-stripe-45 fill is actually visible (not just registered).
    const synFeatureCount = await page.evaluate<number>(() => {
      type Src = { _data?: { features?: unknown[] } } | undefined;
      type MlMap = { getSource: (id: string) => Src };
      const map = (window as unknown as { __riprapMap?: MlMap }).__riprapMap;
      const src = map?.getSource('syn-prior');
      const data = src?._data as { features?: unknown[] } | undefined;
      return data?.features?.length ?? 0;
    });
    expect(synFeatureCount,
      'syn-prior source should have at least one feature in the /q/sample fixture')
      .toBeGreaterThan(0);

    // The four tier sources are added by RipMap on style.load
    expect(mapState.sources).toContain('sandy-empirical');
    expect(mapState.sources).toContain('dep-modeled');
    expect(mapState.sources).toContain('syn-prior');
    expect(mapState.sources).toContain('proxy-311');
    expect(mapState.sources).toContain('queried-address');

    // Tier layers are added with the canonical ids from the spec
    expect(mapState.layers).toEqual(expect.arrayContaining([
      'tier-empirical-fill',
      'tier-empirical-line',
      'tier-modeled-fill',
      'tier-modeled-line',
      'tier-synthetic-fill',
      'tier-synthetic-line',
      'tier-proxy-dots',
      'queried-pin'
    ]));

    // v0.4.2 §14: syn-stripe pattern image must be registered. This is
    // the exact regression we're guarding against — synthetic SAR not
    // rendering because `fill-pattern: syn-stripe-45` resolves to a
    // missing image.
    expect(mapState.hasStripe, 'syn-stripe-45 image should be registered').toBe(true);
    expect(mapState.hasStripe2x, 'syn-stripe-45-2x image should be registered').toBe(true);
    expect(mapState.hasStripeLow, 'syn-stripe-45-low image should be registered').toBe(true);

    // No console errors during boot
    expect(consoleErrors.filter((e) => !e.includes('favicon')))
      .toEqual([]);
  });
});
