/**
 * Fetch Riprap GeoJSON layers from FastAPI for a queried address.
 *
 * The legacy custom-element bundle (web/static/agent.js) wires the same
 * endpoints — keep these in sync. Failures are swallowed because the map
 * is supplementary; the briefing is the deliverable.
 */
import type { FeatureCollection } from 'geojson';

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] };

async function fetchFc(url: string): Promise<FeatureCollection> {
  try {
    const r = await fetch(url);
    if (!r.ok) return EMPTY;
    const j = (await r.json()) as FeatureCollection;
    if (!j || j.type !== 'FeatureCollection') return EMPTY;
    return j;
  } catch {
    return EMPTY;
  }
}

export async function fetchSandy(lat: number, lon: number, r = 1500): Promise<FeatureCollection> {
  return fetchFc(`/api/layers/sandy?lat=${lat}&lon=${lon}&r=${r}`);
}

export async function fetchDep(lat: number, lon: number, r = 1500): Promise<FeatureCollection> {
  return fetchFc(`/api/layers/dep_extreme_2080?lat=${lat}&lon=${lon}&r=${r}`);
}

/**
 * Prithvi water-mask polygons cover Hurricane Ida 2021 flood extents
 * across NYC. The polygons are *sparse* at street-block scale — most
 * single addresses fall in zero-feature neighborhoods. We use the same
 * 1.5 km radius as Sandy/DEP so the layer reflects what flooded *near*
 * the queried address. A wider radius pulled in features from across
 * the city (Manhattan polygons rendering on a Red Hook briefing) which
 * read as confabulation. If a neighborhood wasn't hit by Ida, silence
 * is the right answer — the legend drops the layer automatically.
 */
export async function fetchPrithviSynthetic(
  lat: number,
  lon: number,
  r = 1500
): Promise<FeatureCollection> {
  return fetchFc(`/api/layers/prithvi_water?lat=${lat}&lon=${lon}&r=${r}`);
}

/**
 * Neighborhood / development_check intents emit `nta_resolve` instead of
 * `geocode`. The matching layer endpoints clip to the NTA polygon's bbox
 * — same FeatureCollection contract as the address-mode endpoints.
 */
export async function fetchSandyNta(code: string): Promise<FeatureCollection> {
  return fetchFc(`/api/layers/sandy_clipped?code=${encodeURIComponent(code)}`);
}

export async function fetchDepNta(
  code: string,
  scenario: 'dep_extreme_2080' | 'dep_moderate_2050' | 'dep_moderate_current' = 'dep_extreme_2080'
): Promise<FeatureCollection> {
  return fetchFc(`/api/layers/dep_clipped?code=${encodeURIComponent(code)}&scenario=${scenario}`);
}

export async function fetchNtaPolygon(code: string): Promise<FeatureCollection> {
  return fetchFc(`/api/layers/nta?code=${encodeURIComponent(code)}`);
}

interface FloodNetSensor {
  type: 'Feature';
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: { n_events_3y?: number; peak_depth_mm?: number; deployment_id?: string; name?: string; [k: string]: unknown };
}

/**
 * USGS Hurricane Ida 2021 high-water marks within radius_m of the queried
 * address. Returns Points with site_description, elev_ft,
 * height_above_gnd_ft, hwm_quality, waterbody, distance_m properties.
 * Empirical tier — surveyed ground-truth water marks.
 */
export async function fetchIdaHwm(lat: number, lon: number, r = 1500): Promise<FeatureCollection> {
  return fetchFc(`/api/layers/ida_hwm?lat=${lat}&lon=${lon}&r=${r}`);
}

/**
 * FloodNet sensor points as a graduated-circle layer. The handoff puts 311
 * complaints on the proxy layer; we don't currently expose 311 as GeoJSON
 * from FastAPI, so floodnet sensor density (event count) drives the dot
 * radius for now. Swap to a real 311 endpoint when one lands.
 */
export async function fetchProxyDots(
  lat: number,
  lon: number,
  r = 1500
): Promise<FeatureCollection> {
  try {
    const res = await fetch(`/api/floodnet_near?lat=${lat}&lon=${lon}&r=${r}`);
    if (!res.ok) return EMPTY;
    const j = (await res.json()) as FeatureCollection;
    // Map n_events_3y → `count` so the proxy-dots radius interpolation hits.
    const features = j.features.map((f) => {
      const p = (f as FloodNetSensor).properties ?? {};
      return {
        ...f,
        properties: {
          ...p,
          count: typeof p.n_events_3y === 'number' ? p.n_events_3y : 1
        }
      };
    });
    return { type: 'FeatureCollection', features };
  } catch {
    return EMPTY;
  }
}
