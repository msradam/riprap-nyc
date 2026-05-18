/**
 * Test fixtures — small, self-contained API-response shapes for the
 * cardAdapter unit tests. Kept hand-written (not generated from the
 * Python probe JSON) so the test is reproducible without a running
 * server, and so the shape we're asserting against is visibly pinned
 * here rather than buried in an opaque blob.
 *
 * If the backend pebble shapes drift, the corresponding fields here
 * need a deliberate update — that's the point.
 */

import type { PebbleManifest, PebbleStone } from '$lib/stores/pebbleManifest.svelte';

/** The five Stones in display order — identical across deployments. */
export const STONES: PebbleStone[] = [
  { id: 'cornerstone', name: 'Cornerstone', tagline: 'The Hazard Reader',
    description: '', order: 1 },
  { id: 'touchstone',  name: 'Touchstone',  tagline: 'The Live Observer',
    description: '', order: 2 },
  { id: 'keystone',    name: 'Keystone',    tagline: 'The Asset Register',
    description: '', order: 3 },
  { id: 'lodestone',   name: 'Lodestone',   tagline: 'The Projector',
    description: '', order: 4 },
  { id: 'capstone',    name: 'Capstone',    tagline: 'The Synthesiser',
    description: '', order: 5 },
];

/** Generic factory — keeps each fixture row tiny. */
function manifest(
  id: string,
  stone: PebbleManifest['stone'],
  opts: Partial<PebbleManifest> = {},
): PebbleManifest {
  return {
    id,
    type: 'live',
    title: opts.title ?? id,
    stone,
    tier: opts.tier ?? 'empirical',
    display: {
      order: opts.display?.order ?? null,
      kind: opts.display?.kind ?? 'text',
      variant: opts.display?.variant ?? null,
      map_layer: opts.display?.map_layer ?? false,
      icon: opts.display?.icon ?? null,
    },
    narration: { short: null, template: null, ...(opts.narration ?? {}) },
    provenance: {
      source_name: opts.provenance?.source_name ?? id,
      source_url: null, license: null,
      citation: null, doc_id: id, last_updated: null,
    },
    fallback: { on_offline: 'skip', message: null },
  };
}

/** NYC manifest — the 22 pebbles deployments/nyc ships. */
export const NYC_MANIFEST: PebbleManifest[] = [
  // Cornerstone
  manifest('sandy', 'cornerstone'),
  manifest('ida_hwm', 'cornerstone'),
  manifest('prithvi_water', 'cornerstone'),
  manifest('microtopo', 'cornerstone'),
  manifest('dep_extreme_2080', 'cornerstone'),
  manifest('dep_moderate_2050', 'cornerstone'),
  manifest('dep_moderate_current', 'cornerstone'),
  manifest('policy_corpus', 'cornerstone'),
  // Touchstone
  manifest('floodnet', 'touchstone'),
  manifest('nyc311', 'touchstone'),
  manifest('nws_obs', 'touchstone'),
  manifest('noaa_tides', 'touchstone'),
  manifest('prithvi_live', 'touchstone'),
  // Lodestone
  manifest('nws_alerts', 'lodestone'),
  manifest('ttm_forecast', 'lodestone'),
  manifest('ttm_battery_surge', 'lodestone'),
  manifest('ttm_311_forecast', 'lodestone'),
  manifest('floodnet_forecast', 'lodestone'),
  manifest('npcc4_slr', 'lodestone'),
  // Keystone
  manifest('mta_entrances', 'keystone'),
  manifest('nycha_developments', 'keystone'),
  manifest('doe_schools', 'keystone'),
  manifest('doh_hospitals', 'keystone'),
];

/** Boston manifest — what /api/pebbles SHOULD return for a Boston route. */
export const BOSTON_MANIFEST: PebbleManifest[] = [
  manifest('boston_311', 'touchstone'),
  manifest('water_level', 'touchstone'),
  manifest('nws_obs', 'touchstone'),
  manifest('nws_alerts', 'lodestone'),
];

/** Pebble-id sets we assert against — the bug-fix seal: a Boston
 *  render must contain only Boston ids and no NYC-only ids. */
export const NYC_ONLY_IDS = new Set([
  'sandy', 'ida_hwm', 'prithvi_water', 'prithvi_live',
  'microtopo', 'floodnet', 'nyc311', 'noaa_tides',
  'mta_entrances', 'nycha_developments', 'doe_schools', 'doh_hospitals',
  'ttm_forecast', 'ttm_311_forecast', 'ttm_battery_surge',
  'floodnet_forecast', 'npcc4_slr',
  'dep_extreme_2080', 'dep_moderate_2050', 'dep_moderate_current',
]);

/** A trimmed Boston `/api/agent` response — only the keys cardAdapter reads. */
export const BOSTON_FINAL = {
  intent: 'single_address',
  paragraph: '',
  geocode: {
    address: 'Boston City Hall, 1, Congress Street, Boston, Suffolk County, Massachusetts, 02201, United States',
    lat: 42.3603713, lon: -71.0579762, borough: 'Downtown',
  },
  lat: 42.3603713,
  lon: -71.0579762,
  deployment: 'boston',
  // Pebble fan-out values (what reduce wrote)
  boston_311:  { n_records: 396, radius_m: 500, sample: [], top_by_reason: {} },
  nws_obs:     { station_id: 'KBOS', precip_last_hour_mm: 0, distance_km: 0.3 },
  water_level: { station_id: '8443970', observed_ft_mllw: 5.2, distance_km: 1.8 },
  nws_alerts:  { n_active: 0, alerts: [] },
  citations: [],
  mellea: { passed: [], failed: [], attempts: 0 },
};

/** A trimmed NYC `/api/agent` response — Coney Island shape (sandy=true). */
export const NYC_FINAL = {
  intent: 'single_address',
  paragraph: '',
  geocode: {
    address: '1208 Surf Avenue, Brooklyn, NY, USA',
    lat: 40.5739, lon: -73.9819, borough: 'Brooklyn',
  },
  lat: 40.5739,
  lon: -73.9819,
  deployment: 'nyc',
  sandy: true,
  ida_hwm: { n_within_radius: 0, max_height_above_gnd_ft: null },
  dep_extreme_2080: { depth_label: 'shallow', depth_class: 1 },
  dep_moderate_2050: { depth_label: 'outside', depth_class: 0 },
  dep_moderate_current: { depth_label: 'outside', depth_class: 0 },
  microtopo: { aoi_max_m: 4.2, aoi_min_m: 0.1, basin_relief_m: 0.9 },
  prithvi_water: { inside_water_polygon: false, n_polygons_within_500m: 0 },
  floodnet: { n_sensors: 2, n_flood_events_3y: 7 },
  nyc311: { n: 12, by_descriptor: {} },
  nws_obs: { station_id: 'KJFK', precip_last_hour_mm: 0 },
  noaa_tides: { station_id: '8518750', observed_ft_mllw: 4.8 },
  nws_alerts: { n_active: 0, alerts: [] },
  mta_entrances: { n_ada_accessible: 1, entrances: [] },
  nycha_developments: { n_developments: 0, developments: [] },
  doe_schools: { n_schools: 0, schools: [] },
  doh_hospitals: { n_hospitals: 0, hospitals: [] },
  citations: [],
  mellea: { passed: [], failed: [], attempts: 0 },
};
