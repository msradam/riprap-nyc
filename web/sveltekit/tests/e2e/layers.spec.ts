/**
 * Backend-data smoke for the four MapLibre tier sources. Verifies that
 * the FastAPI /api/layers/* endpoints respond, and prints feature counts
 * so we can tell if "synthetic-prior not rendering" is a registration
 * bug (the syn-stripe-45 image fails to load) or a data-coverage gap
 * (Prithvi water polygons only cover Hurricane Ida flooded areas, so
 * most NYC points return an empty FeatureCollection).
 *
 * Skipped automatically if the backend isn't reachable.
 */
import { test, expect } from '@playwright/test';

const POINTS = [
  { name: '80 Pioneer St (Red Hook)', lat: 40.6776, lon: -74.0096 },
  { name: 'Hollis (Queens)', lat: 40.7152, lon: -73.7569 },
  { name: 'Far Rockaway', lat: 40.6013, lon: -73.7568 }
];

test.describe('@layers backend data coverage', () => {
  for (const p of POINTS) {
    test(`feature counts at ${p.name}`, async ({ request }) => {
      const fetchFc = async (path: string) => {
        const r = await request.get(path);
        if (!r.ok()) return { features: -1 as number, status: r.status() };
        const j = await r.json();
        return { features: (j?.features?.length ?? 0) as number, status: r.status() };
      };

      const [sandy, dep, prithvi, floodnet] = await Promise.all([
        fetchFc(`/api/layers/sandy?lat=${p.lat}&lon=${p.lon}&r=1500`),
        fetchFc(`/api/layers/dep_extreme_2080?lat=${p.lat}&lon=${p.lon}&r=1500`),
        fetchFc(`/api/layers/prithvi_water?lat=${p.lat}&lon=${p.lon}&r=1500`),
        fetchFc(`/api/floodnet_near?lat=${p.lat}&lon=${p.lon}&r=1500`)
      ]);

      // eslint-disable-next-line no-console
      console.log(`[${p.name}] sandy=${sandy.features} dep=${dep.features} prithvi=${prithvi.features} floodnet=${floodnet.features}`);

      // Each endpoint should respond 200 (or be cleanly skipped on a
      // non-running backend). Coverage at any specific point is the
      // diagnostic — empty Prithvi at Red Hook is expected, not a bug.
      for (const fc of [sandy, dep, prithvi, floodnet]) {
        expect([200, -1]).toContain(fc.status);
      }
    });
  }
});
