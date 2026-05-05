/**
 * Sticky-map vs trace overlap regression.
 *
 * Per handoff hard rule #12, the map sticks at top: 80px with a viewport
 * cap. The bug: with the original single-grid `.app-shell` layout, the
 * map's sticky containing block spanned the whole grid (including the
 * evidence and trace rows below) — so when the user scrolled to the
 * trace, the map kept sticking and visually overlapped the trace UI.
 *
 * Fix: split `.app-shell` into a sticky-parent top region (brief + map +
 * cites) and a non-sticky bottom region (evidence + trace). This test
 * scrolls to the trace and asserts the map's rect doesn't intersect.
 */
import { test, expect } from '@playwright/test';

test.describe('sticky map containment', () => {
  test('does not overlap the trace UI when scrolled to bottom', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/q/sample');

    // Wait for the map to mount so its bounding box is meaningful.
    await page.waitForFunction(
      () => Boolean((window as unknown as { __riprapMap?: unknown }).__riprapMap),
      undefined,
      { timeout: 15_000 }
    );

    // Scroll the trace into view and let layout settle.
    await page.locator('#region-trace').scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);

    const rects = await page.evaluate(() => {
      const m = document.getElementById('region-map')?.getBoundingClientRect();
      const t = document.getElementById('region-trace')?.getBoundingClientRect();
      const e = document.querySelector('[aria-label="Evidence"]')?.getBoundingClientRect();
      return { m, t, e };
    });

    expect(rects.m, 'map rect').toBeTruthy();
    expect(rects.t, 'trace rect').toBeTruthy();
    if (!rects.m || !rects.t) return;

    // Two boxes overlap iff X-axis ranges overlap AND Y-axis ranges overlap.
    const xOverlap = !(rects.m.right <= rects.t.left || rects.t.right <= rects.m.left);
    const yOverlap = !(rects.m.bottom <= rects.t.top || rects.t.bottom <= rects.m.top);
    const overlaps = xOverlap && yOverlap;

    expect(overlaps,
      `map should not visually overlap the trace UI when scrolled to it. ` +
      `Map rect: ${JSON.stringify(rects.m)}; Trace rect: ${JSON.stringify(rects.t)}.`
    ).toBe(false);

    // Belt + suspenders: map's bottom edge must be ABOVE the trace's top.
    expect(rects.m.bottom).toBeLessThanOrEqual(rects.t.top + 1);
  });

  test('side rail is position:sticky with citations stacked beneath the map (DOM order)', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/q/sample');

    await page.waitForFunction(
      () => Boolean((window as unknown as { __riprapMap?: unknown }).__riprapMap),
      undefined,
      { timeout: 15_000 }
    );

    // Note: we don't pin a specific viewport-top here. Sample is a
    // short page so the sticky range is small; live briefings (where
    // brief content is much longer) get a multi-screen sticky range
    // automatically because .app-shell-top stretches with brief height.
    // What we verify here is the structural contract: rail is sticky
    // at top:80, the map renders before citations in the rail, and the
    // rail itself can scroll internally.
    const facts = await page.evaluate(() => {
      const rail = document.querySelector('.app-region-side') as HTMLElement | null;
      if (!rail) return null;
      const cs = getComputedStyle(rail);
      const map = document.getElementById('region-map');
      const cites = document.querySelector('.citation-drawer');
      const order = map && cites &&
        (map.compareDocumentPosition(cites) & Node.DOCUMENT_POSITION_FOLLOWING) ? 'map-first' : 'wrong';
      return {
        position: cs.position,
        top: cs.top,
        overflowY: cs.overflowY,
        order
      };
    });
    expect(facts).toBeTruthy();
    if (!facts) return;
    expect(facts.position).toBe('sticky');
    expect(facts.top).toBe('80px');
    expect(facts.overflowY).toBe('auto');
    expect(facts.order).toBe('map-first');
  });

  test('citations are reachable from the side rail (not buried under sticky map)', async ({ page }) => {
    // Regression: at 100% browser zoom the map's max-height was nearly
    // full viewport, so the citation drawer ended up entirely behind
    // the sticky map after any scroll. Fix: wrap map + citations in a
    // single sticky overflow-y:auto rail so the user can always scroll
    // to the citations from any page-scroll position.
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/q/sample');

    await page.waitForFunction(
      () => Boolean((window as unknown as { __riprapMap?: unknown }).__riprapMap),
      undefined,
      { timeout: 15_000 }
    );

    await page.evaluate(() => window.scrollTo({ top: 400, behavior: 'instant' }));
    await page.waitForTimeout(250);

    // The side rail itself is sticky and overflow-y:auto — citations
    // are always inside it, reachable by scrolling within the rail.
    const inside = await page.evaluate(() => {
      const rail = document.querySelector('.app-region-side') as HTMLElement | null;
      const cites = document.querySelector('.citation-drawer') as HTMLElement | null;
      if (!rail || !cites) return null;
      const inside = rail.contains(cites);
      const railRect = rail.getBoundingClientRect();
      const railVisible = railRect.top < window.innerHeight && railRect.bottom > 0;
      const railScrollable = rail.scrollHeight > rail.clientHeight;
      // Map sits at the start of the flex column; citations come after
      // it in DOM order (so internal-scrolling reveals them).
      const map = document.getElementById('region-map');
      const mapBeforeCites =
        map &&
        map.compareDocumentPosition(cites) & Node.DOCUMENT_POSITION_FOLLOWING;
      return { inside, railVisible, railScrollable, mapBeforeCites: Boolean(mapBeforeCites) };
    });

    expect(inside, 'rail / cites geometry').toBeTruthy();
    if (!inside) return;
    expect(inside.inside, 'citations inside side rail').toBe(true);
    expect(inside.railVisible, 'side rail visible in viewport').toBe(true);
    expect(inside.mapBeforeCites, 'map renders before cites in DOM').toBe(true);
  });
});
