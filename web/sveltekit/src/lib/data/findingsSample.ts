/**
 * Findings v0.4.4 sample data — Red Hook query.
 *
 * Mirrors the CARDS / CARDS_BY_QUERY tables in
 * docs/design_handoff/design_files/findings.jsx so the SvelteKit Findings
 * region can be rendered without a live FSM. Use as fixture for
 * `routes/q/sample/+page.svelte` and Playwright snapshots.
 *
 * Stone-trace member ids match the FSM step names where possible so the
 * adapter can replace this with live data without changing card copy.
 */
import type { FindingsData } from '$lib/types/card';

export const SAMPLE_FINDINGS: FindingsData = {
  wallSeconds: 14.0,
  cacheHit: 0.92,
  cards: [
    /* ── Cornerstone ── */
    {
      id: 'fc-fema',
      stone: 'cornerstone', tier: 'modeled', variant: 'headline',
      source: 'FEMA', agency: 'Federal Emergency Management Agency',
      vintage: '2024-09',
      title: 'Preliminary FIRM, panel 36047C0207G',
      headline: 'Zone AE',
      subhead: 'BFE 11 ft NAVD88 · freeboard +4.8 ft',
      body: 'Address sits within the regulatory 1% annual-chance floodplain. Base Flood Elevation 11.0 ft NAVD88; first floor must be at or above this datum for NFIP rating.',
      docId: 'FEMA-FIRM-36047C0207G', citeId: 'c4',
      mapLayer: 'fema-ae',
    },
    {
      id: 'fc-hwm',
      stone: 'cornerstone', tier: 'empirical', variant: 'tabular',
      source: 'USGS', agency: 'U.S. Geological Survey',
      vintage: '2013-05',
      title: 'Post-Sandy high-water marks within 500 ft',
      columns: ['id', 'elev.', 'dist.'],
      rows: [
        ['HWM-NY-3081', '7.4 ft NAVD88', '0.18 mi'],
        ['HWM-NY-3082', '8.1 ft NAVD88', '0.22 mi'],
        ['HWM-NY-3105', '6.8 ft NAVD88', '0.31 mi'],
      ],
      sub: '3 marks · max 8.1 ft · surveyed Nov 2012',
      docId: 'USGS-OFR-2013-1234', citeId: 'c1',
      mapLayer: 'hwm',
    },
    {
      id: 'fc-stormwater',
      stone: 'cornerstone', tier: 'modeled', variant: 'raster',
      source: 'NYC DEP', agency: 'NYC Dept. of Environmental Protection',
      vintage: '2024-06',
      title: 'Stormwater Flood Map · moderate scenario',
      rasterKind: 'stormwater',
      sub: '2.13 in/hr · ponding ≥4 in W half of lot · routed toward Imlay St',
      docId: 'NYCDEP-SWFM-2024', citeId: 'c5',
      mapLayer: 'stormwater',
    },

    /* ── Keystone ── */
    {
      id: 'fc-register-rh',
      stone: 'keystone', tier: 'empirical', variant: 'register',
      source: 'NYC OpenData', agency: 'NYC OpenData · multi-agency join',
      vintage: '2026-05',
      title: 'Nearby exposed assets',
      registers: [
        { reg: 'MTA',   tier: 'empirical', label: 'Smith–9 St subway entrance', detail: '0.34 mi · F · G',     sourceId: 'MTA-ENT-N048', vintage: '2025-11', note: null },
        { reg: 'NYCHA', tier: 'empirical', label: 'Red Hook East Houses',       detail: '0.41 mi · 2,878 res.', sourceId: 'NYCHA-RHE',    vintage: '2025-Q3', note: null },
        { reg: 'NYCHA', tier: 'empirical', label: 'Red Hook West Houses',       detail: '0.52 mi · 3,142 res.', sourceId: 'NYCHA-RHW',    vintage: '2025-Q3', note: null },
        { reg: 'DOE',   tier: 'empirical', label: 'PS 27 Agnes Y. Humphrey',    detail: '0.29 mi · 271 K-5',    sourceId: 'DOE-K027',     vintage: '2024-25', note: null },
        { reg: 'DOH',   tier: 'empirical', label: null,                          detail: null,                   sourceId: null,            vintage: null,       note: 'no acute-care hospital within 1.0 mi (silent)' },
        { reg: 'PLUTO', tier: 'empirical', label: 'Lot 36047 / 521 / 7',        detail: 'BIN 3018472 · MX-1',   sourceId: 'PLUTO-2024v2',  vintage: '2024-12', note: null },
      ],
      sub: '5 of 6 registers fired · 1 silent · joined within 1.0 mi',
      docId: 'RIPRAP-EXP-RH80', citeId: 'c-reg-rh',
      mapLayer: 'registers',
    },

    /* ── Touchstone ── */
    {
      id: 'fc-floodnet',
      stone: 'touchstone', tier: 'empirical', variant: 'spark',
      source: 'FloodNet', agency: 'FloodNet NYC sensor network',
      vintage: '2026-04',
      title: 'Sensor BK-RH-002, monthly above-curb events',
      headline: '7 events',
      subhead: 'Jun 2024 → Apr 2026 · peak 14.3 cm',
      spark: [0,0,1,0,2,1,0,0,3,0,1,0,0,0,2,1,0,0,1,0,2,4,1,1],
      sparkSub: 'Sensor located 0.21 mi N at Coffey & Van Brunt. Above-curb depth in cm; events ≥2 cm.',
      docId: 'FN-BK-RH-002', citeId: 'c3',
      mapLayer: 'floodnet',
    },
    {
      id: 'fc-311',
      stone: 'touchstone', tier: 'proxy', variant: 'histogram',
      source: 'NYC 311', agency: 'NYC 311 service requests',
      vintage: '2025-12',
      title: 'Recent 311 flood complaints, BK CB6',
      headline: '89 calls',
      subhead: '2019–2025 · seasonal cluster Aug–Oct',
      histogram: [3,2,1,0,1,4,7,12,18,11,5,3,4,2,1,0,2,3,8,9,4,2,1,0],
      sparkSub: 'Filtered to complaint types: Sewer (Backup), Street Flooding, Catch Basin Clogged. Within 200 m of address.',
      docId: 'NYC311-FLD-CB6', citeId: 'c7',
      mapLayer: 'complaints',
    },
    {
      id: 'fc-prithvi',
      stone: 'touchstone', tier: 'modeled', variant: 'raster-pred',
      source: 'Prithvi-NYC', agency: 'Prithvi-NYC-Pluvial v2 · IBM/NASA × Riprap',
      vintage: '2026-05-02',
      title: 'Pluvial flood prediction, current Sentinel-2 chip',
      rasterKind: 'prithvi',
      headline: '0.3% flooded',
      subhead: 'no flooding apparent · scene 2026-05-02',
      sub: 'Model interpretation of imagery, not real-time observation. Confidence-mean 0.84 across non-flooded pixels.',
      docId: 'PRITHVI-NYC-PLUV-V2-20260502', citeId: 'c-prithvi',
      illustrative: true,
      mapLayer: 'prithvi',
    },
    {
      id: 'fc-nws',
      stone: 'touchstone', tier: 'empirical', variant: 'scalars',
      source: 'NWS KNYC', agency: 'NOAA · National Weather Service',
      vintage: '2026-05-05',
      title: 'Current weather, station KNYC',
      scalars: [
        { value: '0.02 in', label: 'precip · last 24h' },
        { value: '67°F',    label: 'temp · current' },
        { value: 'PC',      label: 'conditions' },
      ],
      sub: 'Observation timestamp 2026-05-05 14:18 ET. Central Park station; not point-of-query.',
      docId: 'NWS-KNYC', citeId: 'c-nws',
      mapLayer: 'nws',
    },

    /* ── Lodestone ── */
    {
      id: 'fc-ttm-surge',
      stone: 'lodestone', tier: 'modeled', variant: 'timeseries',
      source: 'Granite TTM r2', agency: 'IBM Granite-TimeSeries · Riprap fine-tune',
      vintage: '2026-05-05 12:00 ET',
      title: 'Storm surge nowcast at The Battery, 96-hour horizon',
      timeseries: { hours: 96, peak: { x: 38, y: 47 }, peakLabel: '+47 cm @ +38h' },
      headline: '+47 cm',
      subhead: 'peak surge residual · Wed 04:00 ET',
      sub: 'Nowcast applies city-wide via NOAA station 8518750. Not localized to query address. Residual above harmonic tide.',
      spatialNote: 'regional · The Battery, not point-of-query',
      docId: 'ttm_battery_surge_v2', citeId: 'c-ttm',
      mapLayer: null,
    },
    {
      id: 'fc-npcc4',
      stone: 'lodestone', tier: 'modeled', variant: 'forecast',
      source: 'NPCC4', agency: 'NYC Panel on Climate Change, 4th Assessment',
      vintage: '2024-03',
      title: 'Sea-level rise projections, Lower NY Harbor',
      forecast: [
        { year: 2030, low: 4,  mid: 6,  high: 9   },
        { year: 2050, low: 13, mid: 22, high: 30  },
        { year: 2080, low: 28, mid: 49, high: 75  },
        { year: 2100, low: 38, mid: 71, high: 114 },
      ],
      sub: 'inches MSL · 17th–83rd %ile range, median line. Battery tide-gauge baseline.',
      docId: 'NPCC4-Ch3-Tbl3.2', citeId: 'c6',
      mapLayer: null,
    },

    /* ── Capstone ── */
    {
      id: 'fc-mellea-meta',
      stone: 'capstone', tier: 'modeled', variant: 'meta',
      source: 'Mellea', agency: 'Capstone synthesis · grounding check',
      vintage: '2026-05-05 14:22 ET',
      title: 'Briefing reconciliation',
      metaRows: [
        { k: 'Mellea reroll',     v: '1 attempt' },
        { k: 'Grounding checks',  v: '4 / 4 passed' },
        { k: 'Citations resolved',v: '11 / 11' },
        { k: 'RAG → GLiNER',      v: '9 entities · 0 unresolved' },
      ],
      sub: 'Capstone produces prose, not cards. This meta-card summarizes the reconciler chain that wrote the four-section briefing above.',
      docId: 'RIPRAP-CAP-RH80', citeId: null,
      mapLayer: null,
    },
  ],

  stones: [
    {
      key: 'cornerstone',
      members: [
        { id: 'CORN-001', name: 'pull FEMA NFHL panel 36047C0207G', status: 'ok',     tier: 'modeled',   ms: 412 },
        { id: 'CORN-002', name: 'parse panel index for AE / VE bands', status: 'ok',  tier: 'modeled',   ms: 88 },
        { id: 'CORN-003', name: 'USGS STN: post-Sandy HWM survey within 500 ft', status: 'ok', tier: 'empirical', ms: 612 },
        { id: 'CORN-004', name: 'NYC DEP stormwater flood map 2024', status: 'ok',    tier: 'modeled',   ms: 980 },
        { id: 'CORN-005', name: 'microtopo: 3DEP DEM + HAND + TWI', status: 'ok',     tier: 'proxy',     ms: 1240 },
      ],
    },
    {
      key: 'keystone',
      members: [
        { id: 'KEY-001', name: 'MTA subway entrance proximity', status: 'ok',         tier: 'empirical', ms: 220 },
        { id: 'KEY-002', name: 'NYCHA developments in 1 mi',   status: 'ok',         tier: 'empirical', ms: 410 },
        { id: 'KEY-003', name: 'DOE schools in 1 mi',           status: 'ok',         tier: 'empirical', ms: 360 },
        { id: 'KEY-004', name: 'NYS DOH hospitals in 1 mi',    status: 'silent', tier: 'empirical', ms: 95, note: 'no acute-care within 1 mi' },
        { id: 'KEY-005', name: 'PLUTO BBL fetch',               status: 'ok',         tier: 'empirical', ms: 130 },
      ],
    },
    {
      key: 'touchstone',
      members: [
        { id: 'TCH-001', name: 'FloodNet sensor lookup',        status: 'ok',         tier: 'empirical', ms: 285 },
        { id: 'TCH-002', name: 'NYC 311 flood complaints',      status: 'ok',         tier: 'proxy',     ms: 410 },
        { id: 'TCH-003', name: 'NWS station KNYC observation',  status: 'ok',         tier: 'empirical', ms: 240 },
        { id: 'TCH-004', name: 'NOAA tide gauge water level',   status: 'ok',         tier: 'empirical', ms: 196 },
        { id: 'TCH-005', name: 'Prithvi-EO 2.0 NYC-Pluvial v2', status: 'ok',         tier: 'modeled',   ms: 4920 },
      ],
    },
    {
      key: 'lodestone',
      members: [
        { id: 'LOD-001', name: 'Granite TTM r2 surge fine-tune', status: 'ok',         tier: 'modeled',   ms: 1820 },
        { id: 'LOD-002', name: 'NPCC4 SLR projection table',     status: 'ok',         tier: 'modeled',   ms: 38 },
        { id: 'LOD-003', name: 'NWS active flood alerts',        status: 'silent', tier: 'modeled',   ms: 110 },
      ],
    },
    {
      key: 'capstone',
      members: [
        { id: 'CAP-001', name: 'Granite Embedding RAG retrieval', status: 'ok',         tier: 'proxy',     ms: 410 },
        { id: 'CAP-002', name: 'GLiNER typed extraction',         status: 'ok',         tier: 'proxy',     ms: 280 },
        { id: 'CAP-003', name: 'Granite 4.1 reconcile (Mellea)',  status: 'ok',         tier: 'modeled',   ms: 6240 },
      ],
    },
  ],
};
