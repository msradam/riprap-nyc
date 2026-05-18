/**
 * Per-city test fixtures — captures the shape /api/pebbles +
 * /api/deployment + /api/agent return for each shipped deployment.
 *
 * Fixtures are HAND-MAINTAINED, not generated. The reason: tests using
 * them assert exact strings ("Boston", "Reads what Boston remembers
 * about flooding…") and we want a deliberate edit when those strings
 * drift, not silent regeneration from a live server. If a backend
 * change makes a fixture stale, the test FAILS — that's the contract.
 *
 * Coverage: NYC, Boston, Chicago, Seattle, SF, plus an out-of-coverage
 * "elsewhere" fixture for Albuquerque to assert the neutral chip path.
 */
import type {
  PebbleManifest, PebbleManifestResponse, PebbleStone,
} from '$lib/stores/pebbleManifest.svelte';
import type { Deployment } from '$lib/stores/deployment.svelte';
import type { FinalResult } from '$lib/client/agentStream';

export type CityFixture = {
  /** Short directory name — matches deployments/<key>/ on disk. */
  key: string;
  /** /api/deployment response. */
  deployment: Deployment;
  /** /api/pebbles response. */
  manifest: PebbleManifestResponse;
  /** /api/agent response (trimmed to the fields the UI consumes). */
  agent: Partial<FinalResult> & Record<string, unknown>;
  /** Expected geocode result for the city's anchor address. */
  geocode: { address: string; lat: number; lon: number };
};

const STONES: PebbleStone[] = [
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

function pebble(
  id: string, stone: PebbleManifest['stone'],
  opts: Partial<PebbleManifest> & { map_layer?: boolean; title?: string } = {},
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
      map_layer: opts.map_layer ?? opts.display?.map_layer ?? false,
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

function deploymentStones(cityDescriptions: Record<PebbleManifest['stone'], string>): PebbleStone[] {
  return STONES.map((s) => ({ ...s, description: cityDescriptions[s.id] }));
}

// ─────────────────────────────────────────────────────────── NYC
export const NYC: CityFixture = {
  key: 'nyc',
  deployment: { name: 'nyc', city: 'NYC', hazard: 'Flood-exposure briefing' },
  geocode: { address: '189 ATLANTIC AVENUE, Brooklyn, NY, USA',
             lat: 40.690135, lon: -73.993242 },
  manifest: {
    stones: deploymentStones({
      cornerstone: "Reads what NYC's ground remembers about flooding.",
      touchstone:  "Watches the current state of the city's flood signals and EO.",
      keystone:    "Counts the public assets and built fabric exposed to the hazards.",
      lodestone:   "Projects what's coming — alerts, surge, and recurrence forecasts.",
      capstone:    "Writes the cited briefing — Granite 4.1 + Mellea rejection sampling.",
    }),
    pebbles: [
      pebble('sandy',                'cornerstone', { map_layer: true,  title: 'NYC Sandy Inundation Zone (2012 empirical extent)' }),
      pebble('ida_hwm',              'cornerstone', { map_layer: true,  title: 'Hurricane Ida 2021 — USGS high-water marks' }),
      pebble('prithvi_water',        'cornerstone', { map_layer: true,  tier: 'modeled' }),
      pebble('microtopo',            'cornerstone', { tier: 'proxy' }),
      pebble('dep_extreme_2080',     'cornerstone', { map_layer: true,  tier: 'modeled' }),
      pebble('dep_moderate_2050',    'cornerstone', { map_layer: true,  tier: 'modeled' }),
      pebble('dep_moderate_current', 'cornerstone', { map_layer: true,  tier: 'modeled' }),
      pebble('policy_corpus',        'cornerstone'),
      pebble('floodnet',             'touchstone',  { map_layer: true,  tier: 'proxy' }),
      pebble('nyc311',               'touchstone',  { map_layer: true,  tier: 'proxy' }),
      pebble('nws_obs',              'touchstone'),
      pebble('noaa_tides',           'touchstone'),
      pebble('prithvi_live',         'touchstone',  { map_layer: true,  tier: 'modeled' }),
      pebble('nws_alerts',           'lodestone',   { tier: 'modeled' }),
      pebble('ttm_forecast',         'lodestone',   { tier: 'modeled' }),
      pebble('ttm_battery_surge',    'lodestone',   { tier: 'modeled' }),
      pebble('ttm_311_forecast',     'lodestone',   { tier: 'modeled' }),
      pebble('floodnet_forecast',    'lodestone',   { tier: 'modeled' }),
      pebble('npcc4_slr',            'lodestone',   { tier: 'modeled' }),
      pebble('mta_entrances',        'keystone',    { map_layer: true,  title: 'MTA subway entrances exposed nearby' }),
      pebble('nycha_developments',   'keystone',    { map_layer: true,  title: 'NYCHA developments exposed nearby' }),
      pebble('doe_schools',          'keystone',    { map_layer: true,  title: 'NYC DOE schools exposed nearby' }),
      pebble('doh_hospitals',        'keystone',    { map_layer: true,  title: 'NYC DOH hospitals exposed nearby' }),
    ],
  },
  agent: {
    intent: 'single_address',
    paragraph: 'Templated reconciliation paragraph for NYC.',
    geocode: { address: '189 ATLANTIC AVENUE, Brooklyn, NY, USA',
               lat: 40.690135, lon: -73.993242, borough: 'Brooklyn' },
    lat: 40.690135,
    lon: -73.993242,
    deployment: 'nyc',
    sandy: false,
    ida_hwm: { n_within_radius: 0 },
    dep_extreme_2080: { depth_label: 'outside', depth_class: 0 },
    dep_moderate_2050: { depth_label: 'outside', depth_class: 0 },
    dep_moderate_current: { depth_label: 'outside', depth_class: 0 },
    microtopo: { aoi_max_m: 4.2, basin_relief_m: 0.9 },
    prithvi_water: { inside_water_polygon: false },
    floodnet: { n_sensors: 2, n_flood_events_3y: 7 },
    nyc311: { n: 29 },
    nws_obs: { station_id: 'KJFK', precip_last_hour_mm: 0 },
    noaa_tides: { station_id: '8518750', station_name: 'The Battery, NY',
                  observed_ft_mllw: 4.5, distance_km: 0.8 },
    prithvi_live: { ok: true, skipped: false },
    nws_alerts: { n_active: 0, alerts: [] },
    ttm_forecast: { available: true, forecast_peak_ft: 5.1 },
    ttm_battery_surge: { available: true },
    ttm_311_forecast: { accelerating: false, available: true },
    floodnet_forecast: { available: true },
    npcc4_slr: { '2050': 12, '2100': 24, available: true },
    mta_entrances: { n_ada_accessible: 1 },
    nycha_developments: { n_developments: 0 },
    doe_schools: { n_schools: 0 },
    doh_hospitals: { n_hospitals: 0 },
    citations: [],
    mellea: { passed: [], failed: [], attempts: 0 },
  },
};

// ─────────────────────────────────────────────────────────── Boston
export const BOSTON: CityFixture = {
  key: 'boston',
  deployment: { name: 'boston', city: 'Boston', hazard: 'Flood-exposure briefing' },
  geocode: {
    address: 'Boston City Hall, 1, Congress Street, Government Center/Faneuil Hall, Downtown, Boston, Suffolk County, Massachusetts, 02201, United States',
    lat: 42.3603713, lon: -71.0579762,
  },
  manifest: {
    stones: deploymentStones({
      cornerstone: "Reads what Boston remembers about flooding — Back Bay landfill, Boston Harbor surge exposure, nor'easter shoreline impact.",
      touchstone:  "Watches current flood signals — Boston 311 cases, NWS Boston/Norton, Boston Harbor tide observations.",
      keystone:    "Counts public assets exposed — BPS schools, City of Boston facilities, hospitals.",
      lodestone:   "Projects what's coming — NWS Boston/Norton forecasts, NOAA SLR Viewer for Boston Harbor.",
      capstone:    "Writes the cited briefing — Granite 4.1 + Mellea grounding check.",
    }),
    pebbles: [
      pebble('boston_311',  'touchstone', { map_layer: true,  tier: 'proxy',
        title: 'Boston 311 service requests near this address' }),
      pebble('water_level', 'touchstone', { tier: 'empirical',
        title: 'Local water level — NOAA Boston, MA (station 8443970)' }),
      pebble('nws_obs',     'touchstone'),
      pebble('nws_alerts',  'lodestone',  { tier: 'modeled' }),
    ],
  },
  agent: {
    intent: 'single_address',
    paragraph: 'Templated reconciliation paragraph for Boston.',
    geocode: { address: 'Boston City Hall, 1, Congress Street, Boston, MA',
               lat: 42.3603713, lon: -71.0579762, borough: 'Downtown' },
    lat: 42.3603713,
    lon: -71.0579762,
    deployment: 'boston',
    boston_311:  { n_records: 396, radius_m: 500, sample: [] },
    nws_obs:     { station_id: 'KBOS', precip_last_hour_mm: 0, distance_km: 0.3 },
    water_level: { station_id: '8443970', station_name: 'Boston, MA',
                   observed_ft_mllw: 2.17, predicted_ft_mllw: 1.06,
                   residual_ft: 1.11, distance_km: 0.7 },
    nws_alerts:  { n_active: 0, alerts: [] },
    citations: [],
    mellea: { passed: [], failed: [], attempts: 0 },
  },
};

// ─────────────────────────────────────────────────────────── Chicago
export const CHICAGO: CityFixture = {
  key: 'chicago',
  deployment: { name: 'chicago', city: 'Chicago', hazard: 'Flood-exposure briefing' },
  geocode: { address: 'Willis Tower, 233, South Wacker Drive, Chicago, IL',
             lat: 41.878738, lon: -87.6359612 },
  manifest: {
    stones: deploymentStones({
      cornerstone: "Reads what Chicago's ground remembers about flooding — FEMA floodplains, lake-level baselines, stormwater modeling.",
      touchstone:  "Watches the current state of the city's flood signals — Chicago 311 flood complaints, Lake Michigan tide gauge, NWS observations.",
      keystone:    "Counts public assets exposed — CHA developments, CPS schools, hospitals — and their accessibility from this address.",
      lodestone:   "Projects what's coming — NWS forecasts, Great Lakes water-level projections, FEMA scenario maps.",
      capstone:    "Writes the cited flood-exposure briefing — Granite 4.1 + Mellea grounding check.",
    }),
    pebbles: [
      pebble('chicago_311',               'touchstone', { map_layer: true, tier: 'proxy',
        title: 'Chicago 311 service requests near this address' }),
      pebble('lake_michigan_water_level', 'touchstone', { tier: 'empirical',
        title: 'Lake Michigan water level — NOAA Calumet Harbor' }),
      pebble('nws_obs',                   'touchstone'),
      pebble('nws_alerts',                'lodestone',  { tier: 'modeled' }),
    ],
  },
  agent: {
    intent: 'single_address',
    paragraph: 'Templated reconciliation paragraph for Chicago.',
    geocode: { address: 'Willis Tower, Chicago, IL',
               lat: 41.878738, lon: -87.6359612, borough: 'Loop' },
    lat: 41.878738,
    lon: -87.6359612,
    deployment: 'chicago',
    chicago_311:               { n_records: 200, radius_m: 500 },
    nws_obs:                   { station_id: 'KORD', distance_km: 22.0 },
    lake_michigan_water_level: { station_id: '9087044', distance_km: 18.1 },
    nws_alerts:                { n_active: 0 },
    citations: [],
    mellea: { passed: [], failed: [], attempts: 0 },
  },
};

// ─────────────────────────────────────────────────────────── Seattle
export const SEATTLE: CityFixture = {
  key: 'seattle',
  deployment: { name: 'seattle', city: 'Seattle', hazard: 'Flood-exposure briefing' },
  geocode: { address: 'Seattle City Hall, 600, 4th Avenue, Seattle, WA',
             lat: 47.6038904, lon: -122.3300986 },
  manifest: {
    stones: deploymentStones({
      cornerstone: "Reads what Seattle remembers about flooding — Puget Sound shoreline, salmon-corridor streams, and Pacific Northwest precipitation.",
      touchstone:  "Watches current flood signals — Seattle CSR (Find It Fix It), NWS Seattle, Puget Sound water levels.",
      keystone:    "Counts public assets exposed — Seattle Public Schools, King County libraries, hospitals.",
      lodestone:   "Projects what's coming — NWS Pacific Northwest forecasts, NOAA Puget Sound projections.",
      capstone:    "Writes the cited briefing — Granite 4.1 + Mellea grounding check.",
    }),
    pebbles: [
      pebble('water_level', 'touchstone', { tier: 'empirical',
        title: 'Local water level — NOAA Seattle, WA (station 9447130)' }),
      pebble('nws_obs',     'touchstone'),
      pebble('nws_alerts',  'lodestone',  { tier: 'modeled' }),
    ],
  },
  agent: {
    intent: 'single_address',
    paragraph: 'Templated reconciliation paragraph for Seattle.',
    geocode: { address: 'Seattle City Hall, Seattle, WA',
               lat: 47.6038904, lon: -122.3300986, borough: 'First Hill' },
    lat: 47.6038904,
    lon: -122.3300986,
    deployment: 'seattle',
    water_level: { station_id: '9447130', distance_km: 0.8 },
    nws_obs:     { station_id: 'KBFI', distance_km: 4.5 },
    nws_alerts:  { n_active: 0 },
    citations: [],
    mellea: { passed: [], failed: [], attempts: 0 },
  },
};

// ─────────────────────────────────────────────────────────── SF
export const SF: CityFixture = {
  key: 'sf',
  deployment: { name: 'sf', city: 'San Francisco', hazard: 'Flood-exposure briefing' },
  geocode: { address: 'San Francisco City Hall, 1, Dr. Carlton B. Goodlett Place, San Francisco, CA',
             lat: 37.7792929, lon: -122.4192601 },
  manifest: {
    stones: deploymentStones({
      cornerstone: "Reads what SF remembers about flooding — Bay shoreline, fog-prone microclimates, fault-adjacent fills, and Pacific storm exposure.",
      touchstone:  "Watches current flood signals — SF311 cases, NWS Bay Area, SF Bay tide observations.",
      keystone:    "Counts public assets exposed — SFUSD schools, City and County of SF public assets, hospitals.",
      lodestone:   "Projects what's coming — NWS Bay Area forecasts, NOAA SLR Viewer for SF Bay.",
      capstone:    "Writes the cited briefing — Granite 4.1 + Mellea grounding check.",
    }),
    pebbles: [
      pebble('sf_311',     'touchstone', { map_layer: true, tier: 'proxy',
        title: 'SF 311 service requests near this address' }),
      pebble('water_level','touchstone', { tier: 'empirical',
        title: 'Local water level — NOAA San Francisco (station 9414290)' }),
      pebble('nws_obs',    'touchstone'),
      pebble('nws_alerts', 'lodestone',  { tier: 'modeled' }),
    ],
  },
  agent: {
    intent: 'single_address',
    paragraph: 'Templated reconciliation paragraph for SF.',
    geocode: { address: 'San Francisco City Hall, San Francisco, CA',
               lat: 37.7792929, lon: -122.4192601, borough: 'Civic Center' },
    lat: 37.7792929,
    lon: -122.4192601,
    deployment: 'sf',
    sf_311:      { n_records: 200 },
    nws_obs:     { station_id: 'KSFO', distance_km: 12.1 },
    water_level: { station_id: '9414290', distance_km: 5.1 },
    nws_alerts:  { n_active: 0 },
    citations: [],
    mellea: { passed: [], failed: [], attempts: 0 },
  },
};

// ─────────────────────────────────────────────────────────── Out-of-coverage
export const ELSEWHERE: CityFixture = {
  key: 'elsewhere',
  deployment: { name: 'unknown', city: 'Not in any shipped deployment',
                hazard: 'Climate-exposure briefing' },
  geocode: { address: '1 Civic Plaza NW, Albuquerque, NM',
             lat: 35.0844, lon: -106.6504 },
  manifest: { stones: deploymentStones({
    cornerstone: '', touchstone: '', keystone: '', lodestone: '', capstone: '',
  }), pebbles: [] },
  agent: {
    intent: 'single_address',
    paragraph: 'No shipped deployment covers this point.',
    geocode: { address: '1 Civic Plaza NW, Albuquerque, NM',
               lat: 35.0844, lon: -106.6504 },
    lat: 35.0844,
    lon: -106.6504,
    deployment: null,
    citations: [],
    mellea: { passed: [], failed: [], attempts: 0 },
  },
};

export const ALL_CITIES: readonly CityFixture[] = [NYC, BOSTON, CHICAGO, SEATTLE, SF, ELSEWHERE] as const;

/** Strings that, if seen in a non-NYC render, indicate NYC content leakage.
 *  These are the substrings the user has actually screenshotted appearing
 *  in Boston / Chicago / SF renders. */
export const NYC_LEAK_NEEDLES: readonly string[] = [
  // Stone-tagline leak (StoneRegion's `tag` from STONE_META)
  "what NYC's ground remembers",
  // Map-layer-panel leaks (MapLegend's hardcoded NYC layer rows)
  'Sandy Inundation Zone',
  'Ida HWM',
  'MTA subway entrances',
  'NYCHA developments',
  'DOE schools',
  'DOH hospitals',
  'FloodNet sensors',
  'TerraMind',
  'Prithvi-NYC',
  // Trust-signal / footer leaks
  'FloodHelpNY',
  'FloodNet NYC',
] as const;
