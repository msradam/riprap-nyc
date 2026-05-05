/**
 * FSM-state → Findings Card[] adapter.
 *
 * The Findings region is rendered from a `FindingsData` shape:
 * `{ cards, stones, wallSeconds }`. The FSM produces a different
 * structure: a stream of step events plus a final payload with each
 * specialist's raw output keyed by state name (`sandy`, `dep`,
 * `nyc311`, `mta_entrances`, etc.).
 *
 * This module bridges the two. For each Stone we collect the relevant
 * state keys, render a card per non-silent specialist using the most
 * legible variant for the data shape, and build a per-Stone trace from
 * the TraceNode tree.
 *
 * Best-effort: a missing specialist drops out (silence over
 * confabulation); a specialist that fired with no usable shape becomes
 * a `meta` card listing whatever scalars it returned.
 */
import type {
  Card, FindingsData, StoneKey, StoneMember, StoneTrace
} from '$lib/types/card';
import type { TraceNode, TraceStatus } from '$lib/types/trace';
import type { FinalResult } from '$lib/client/agentStream';

/** Reasonable defaults — when the FSM doesn't supply a vintage, fall
 *  back to the Riprap publication date. */
const RIPRAP_VINTAGE = '2026-05';

/** Map an FSM step name to the trace status the Findings layer wants. */
function mapStatus(s: TraceStatus): StoneMember['status'] {
  if (s === 'fan' || s === 'merge') return 'ok'; // structural nodes
  if (s === 'silent') return 'silent';
  if (s === 'error') return 'error';
  return 'ok';
}

function flattenTrace(node: TraceNode): TraceNode[] {
  return [node, ...(node.children ?? []).flatMap(flattenTrace)];
}

/** Group leaf specialist nodes by the Stone their state-key belongs to.
 *  The trace's name often differs from the state key (e.g.
 *  `mta_entrance_exposure` vs state `mta_entrances`); we map both. */
function stoneForStep(name: string): StoneKey | null {
  const n = name.toLowerCase();
  // Single-address chain
  if (n === 'sandy_inundation' || n === 'sandy') return 'cornerstone';
  if (n === 'dep_stormwater' || n === 'dep') return 'cornerstone';
  if (n === 'ida_hwm_2021' || n === 'ida_hwm') return 'cornerstone';
  if (n === 'prithvi_eo_v2' || n === 'prithvi_water') return 'cornerstone';
  if (n === 'microtopo_lidar' || n === 'microtopo') return 'cornerstone';
  if (n === 'mta_entrance_exposure' || n === 'mta_entrances') return 'keystone';
  if (n === 'nycha_development_exposure' || n === 'nycha_developments') return 'keystone';
  if (n === 'doe_school_exposure' || n === 'doe_schools') return 'keystone';
  if (n === 'doh_hospital_exposure' || n === 'doh_hospitals') return 'keystone';
  if (n === 'terramind_synthesis' || n === 'terramind' || n === 'terramind_buildings' ||
      n === 'eo_chip_fetch') return 'keystone';
  if (n === 'floodnet') return 'touchstone';
  if (n === 'nyc311') return 'touchstone';
  if (n === 'nws_obs') return 'touchstone';
  if (n === 'noaa_tides') return 'touchstone';
  if (n === 'prithvi_eo_live' || n === 'prithvi_live' || n === 'terramind_lulc')
    return 'touchstone';
  if (n === 'nws_alerts') return 'lodestone';
  if (n === 'ttm_forecast' || n === 'ttm_311_forecast' || n === 'floodnet_forecast' ||
      n === 'ttm_battery_surge') return 'lodestone';
  if (n.startsWith('reconcile') || n.startsWith('mellea') ||
      n === 'rag_granite_embedding' || n === 'gliner_extract') return 'capstone';
  return null;
}

function buildStoneTraces(root: TraceNode | undefined | null): StoneTrace[] {
  const buckets: Record<StoneKey, StoneMember[]> = {
    cornerstone: [], keystone: [], touchstone: [], lodestone: [], capstone: [],
  };
  if (root) {
    for (const node of flattenTrace(root)) {
      const stone = stoneForStep(node.name);
      if (!stone) continue;
      buckets[stone].push({
        id: node.id || node.name,
        name: node.name,
        status: mapStatus(node.status),
        tier: node.tier,
        ms: node.ms,
        note: node.note ?? node.error ?? undefined,
      });
    }
  }
  return (Object.keys(buckets) as StoneKey[]).map((key) => ({
    key,
    members: buckets[key],
  }));
}

/* ── Per-specialist card builders. Each returns null if the specialist
   didn't fire, returned no usable data, or the shape doesn't exist. ── */

type Final = Record<string, unknown> & FinalResult;

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function str(v: unknown): string | null {
  return typeof v === 'string' ? v : null;
}

function obj(v: unknown): Record<string, unknown> | null {
  return v && typeof v === 'object' && !Array.isArray(v)
    ? (v as Record<string, unknown>) : null;
}

function buildSandy(state: Final, geocode: Record<string, unknown> | null): Card | null {
  if (state.sandy !== true) return null;
  const addr = geocode && str(geocode.address);
  return {
    id: 'fsm-sandy',
    stone: 'cornerstone', tier: 'empirical', variant: 'headline',
    source: 'NYC OEM', agency: 'NYC OpenData 5xsi-dfpx · Sandy 2012 inundation',
    vintage: '2012-10-29',
    title: 'Hurricane Sandy 2012 inundation',
    headline: 'Inside zone',
    subhead: addr ?? 'address inside the empirical 2012 extent',
    body: 'Address sits within the empirical Hurricane Sandy 2012 inundation extent. This is a historical fact, not a model prediction.',
    docId: 'sandy', citeId: 'sandy', mapLayer: 'sandy',
  };
}

function buildDep(state: Final): Card | null {
  const dep = obj(state.dep);
  if (!dep) return null;
  const rows: (string | number)[][] = [];
  for (const [scen, info] of Object.entries(dep)) {
    const i = obj(info);
    if (!i) continue;
    const cls = num(i.depth_class) ?? 0;
    if (cls <= 0) continue;
    rows.push([scen.replace('dep_', ''), str(i.depth_label) ?? '—', `class ${cls}`]);
  }
  if (!rows.length) return null;
  return {
    id: 'fsm-dep',
    stone: 'cornerstone', tier: 'modeled', variant: 'tabular',
    source: 'NYC DEP', agency: 'NYC Department of Environmental Protection · Stormwater Flood Maps',
    vintage: '2021',
    title: 'Stormwater flood scenarios at this address',
    columns: ['scenario', 'depth label', 'class'],
    rows,
    sub: `${rows.length} scenario${rows.length === 1 ? '' : 's'} place this lot in modeled flooding`,
    docId: 'dep_stormwater', citeId: 'dep', mapLayer: 'stormwater',
  };
}

function buildIdaHwm(state: Final): Card | null {
  const ida = obj(state.ida_hwm);
  if (!ida) return null;
  const n = num(ida.n_within_radius);
  if (!n || n <= 0) return null;
  const rows: (string | number)[][] = [];
  rows.push(['count', `${n}`, `${num(ida.radius_m) ?? 800} m radius`]);
  if (num(ida.max_height_above_gnd_ft) != null) {
    rows.push(['max above gnd', `${ida.max_height_above_gnd_ft} ft`, '—']);
  }
  if (num(ida.nearest_dist_m) != null) {
    rows.push(['nearest', str(ida.nearest_site) ?? 'HWM', `${ida.nearest_dist_m} m`]);
  }
  return {
    id: 'fsm-ida-hwm',
    stone: 'cornerstone', tier: 'empirical', variant: 'tabular',
    source: 'USGS', agency: 'USGS STN Hurricane Ida 2021 high-water marks (Event 312)',
    vintage: '2021-09',
    title: 'Hurricane Ida 2021 high-water marks nearby',
    columns: ['field', 'value', 'context'],
    rows,
    docId: 'ida_hwm', citeId: 'ida_hwm', mapLayer: 'hwm',
  };
}

function buildPrithviWater(state: Final): Card | null {
  const pw = obj(state.prithvi_water);
  if (!pw) return null;
  const dist = num(pw.nearest_distance_m);
  if (dist == null) return null;
  return {
    id: 'fsm-prithvi-water',
    stone: 'cornerstone', tier: 'modeled', variant: 'raster',
    source: 'Prithvi-EO 2.0', agency: 'IBM/NASA Prithvi-EO 2.0 · baked Hurricane Ida 2021 polygons',
    vintage: '2021-09-02',
    title: 'Hurricane Ida 2021 — satellite-attributable inundation',
    rasterKind: 'prithvi',
    headline: pw.inside_water_polygon ? 'Inside polygon' : `${dist} m away`,
    subhead: 'pre/post HLS Sentinel-2 segmentation',
    sub: `${num(pw.n_polygons_within_500m) ?? 0} distinct polygons within 500 m`,
    docId: 'prithvi_water', citeId: 'prithvi_water', mapLayer: 'prithvi',
  };
}

function buildMicrotopo(state: Final): Card | null {
  const mt = obj(state.microtopo);
  if (!mt) return null;
  const elev = num(mt.point_elev_m);
  if (elev == null) return null;
  const scalars = [
    { value: `${elev.toFixed(1)} m`, label: 'elevation' },
  ];
  if (num(mt.hand_m) != null) scalars.push({ value: `${(mt.hand_m as number).toFixed(1)} m`, label: 'HAND' });
  if (num(mt.twi) != null) scalars.push({ value: `${(mt.twi as number).toFixed(1)}`, label: 'TWI' });
  if (num(mt.rel_elev_pct_200m) != null) scalars.push({ value: `${mt.rel_elev_pct_200m}%`, label: 'pct lower 200m' });
  return {
    id: 'fsm-microtopo',
    stone: 'cornerstone', tier: 'proxy', variant: 'scalars',
    source: 'USGS 3DEP', agency: 'USGS 3DEP DEM (LiDAR-derived) + whitebox-workflows hydrology',
    vintage: '2018',
    title: 'Microtopography at this point',
    scalars,
    sub: 'Lower percentile = topographic low point; runoff routes here.',
    docId: 'microtopo', citeId: 'microtopo',
  };
}

/** Per-asset register. Each register-specialist's state has an `available`
 *  flag + a list of items; we render one card with N rows. */
function buildRegisters(state: Final): Card | null {
  const rows: NonNullable<Card['registers']> = [];
  const mta = obj(state.mta_entrances);
  if (mta?.available && Array.isArray(mta.entrances)) {
    for (const e of (mta.entrances as Record<string, unknown>[]).slice(0, 4)) {
      rows.push({
        reg: 'MTA', tier: 'empirical',
        label: str(e.station_name) ?? str(e.entrance_id) ?? 'entrance',
        detail: `${num(e.distance_m) ?? '—'} m · ${str(e.daytime_routes) ?? ''}`.trim(),
        sourceId: str(e.station_id) ?? 'MTA',
        note: null,
      });
    }
  } else if (mta && mta.available === false) {
    rows.push({
      reg: 'MTA', tier: 'empirical', label: null, detail: null, sourceId: null,
      note: 'no subway entrances within 1.0 mi (silent)',
    });
  }

  const nycha = obj(state.nycha_developments);
  if (nycha?.available && Array.isArray(nycha.developments)) {
    for (const d of (nycha.developments as Record<string, unknown>[]).slice(0, 3)) {
      rows.push({
        reg: 'NYCHA', tier: 'empirical',
        label: str(d.development) ?? 'development',
        detail: `${num(d.distance_m) ?? '—'} m · ${str(d.borough) ?? ''}`.trim(),
        sourceId: str(d.tds_num) ?? null,
        note: null,
      });
    }
  } else if (nycha && nycha.available === false) {
    rows.push({
      reg: 'NYCHA', tier: 'empirical', label: null, detail: null, sourceId: null,
      note: 'no NYCHA developments within 1.0 mi (silent)',
    });
  }

  const doe = obj(state.doe_schools);
  if (doe?.available && Array.isArray(doe.schools)) {
    for (const s of (doe.schools as Record<string, unknown>[]).slice(0, 3)) {
      rows.push({
        reg: 'DOE', tier: 'empirical',
        label: str(s.loc_name) ?? 'school',
        detail: `${num(s.distance_m) ?? '—'} m · ${str(s.borough) ?? ''}`.trim(),
        sourceId: str(s.loc_code) ?? null,
        note: null,
      });
    }
  } else if (doe && doe.available === false) {
    rows.push({
      reg: 'DOE', tier: 'empirical', label: null, detail: null, sourceId: null,
      note: 'no schools within 1.0 mi (silent)',
    });
  }

  const doh = obj(state.doh_hospitals);
  if (doh?.available && Array.isArray(doh.hospitals)) {
    for (const h of (doh.hospitals as Record<string, unknown>[]).slice(0, 3)) {
      rows.push({
        reg: 'DOH', tier: 'empirical',
        label: str(h.facility_name) ?? 'hospital',
        detail: `${num(h.distance_m) ?? '—'} m · ${str(h.borough) ?? ''}`.trim(),
        sourceId: str(h.fac_id) ?? null,
        note: null,
      });
    }
  } else if (doh && doh.available === false) {
    rows.push({
      reg: 'DOH', tier: 'empirical', label: null, detail: null, sourceId: null,
      note: 'no acute-care hospital within 1.0 mi (silent)',
    });
  }

  if (!rows.length) return null;
  return {
    id: 'fsm-registers',
    stone: 'keystone', tier: 'empirical', variant: 'register',
    source: 'NYC OpenData', agency: 'NYC OpenData · multi-agency join',
    vintage: RIPRAP_VINTAGE,
    title: 'Nearby exposed assets',
    registers: rows,
    sub: `${rows.filter((r) => r.label).length} of ${rows.length} registers fired · joined within 1.0 mi`,
    docId: 'registers', citeId: 'registers', mapLayer: 'registers',
  };
}

function buildTerramindBuildings(state: Final): Card | null {
  const tmb = obj(state.terramind_buildings);
  if (!tmb?.ok) return null;
  return {
    id: 'fsm-tm-buildings',
    stone: 'keystone', tier: 'modeled', variant: 'raster-pred',
    source: 'TerraMind-NYC', agency: 'msradam/TerraMind-NYC-Adapters · Buildings LoRA',
    vintage: '2026',
    title: 'NYC building footprints — TerraMind LoRA',
    rasterKind: 'buildings',
    headline: `${num(tmb.pct_buildings) ?? 0}%`,
    subhead: 'building-footprint coverage in chip',
    sub: `${num(tmb.n_building_components) ?? 0} distinct components · test mIoU 0.5511`,
    illustrative: true,
    docId: 'tm_buildings', citeId: 'tm_buildings', mapLayer: 'buildings',
  };
}

function buildFloodnet(state: Final): Card | null {
  const fn = obj(state.floodnet);
  if (!fn || (num(fn.n_sensors) ?? 0) <= 0) return null;
  const events = num(fn.n_flood_events_3y) ?? 0;
  return {
    id: 'fsm-floodnet',
    stone: 'touchstone', tier: 'empirical', variant: 'spark',
    source: 'FloodNet', agency: 'FloodNet NYC ultrasonic depth sensor network',
    vintage: '2026',
    title: 'FloodNet sensors near this address',
    headline: `${events} events`,
    subhead: `${num(fn.n_sensors) ?? 0} sensors · last 3 y`,
    spark: Array.from({ length: 24 }, (_, i) =>
      Math.max(0, Math.round((events / 24) * 1.4 * Math.exp(-Math.pow((i - 14) / 4, 2)) +
                              (events / 24)))
    ),
    sparkSub: 'Above-curb depth events ≥ 2 cm. Synthetic monthly distribution; raw deployment-id history is in the audit panel.',
    docId: 'floodnet', citeId: 'floodnet', mapLayer: 'floodnet',
  };
}

function buildNyc311(state: Final): Card | null {
  const n = obj(state.nyc311);
  if (!n) return null;
  const total = num(n.n) ?? 0;
  if (total <= 0) return null;
  // Synthesize a histogram that matches the seasonal pattern when by_year
  // / by_descriptor is present; otherwise distribute uniformly.
  const byYear = obj(n.by_year);
  const byDescriptor = obj(n.by_descriptor);
  const hist = byYear
    ? Object.values(byYear).map((v) => num(v) ?? 0)
    : Array.from({ length: 12 }, () => Math.round(total / 12));
  const top = byDescriptor
    ? Object.entries(byDescriptor).sort((a, b) => (num(b[1]) ?? 0) - (num(a[1]) ?? 0))[0]?.[0]
    : null;
  return {
    id: 'fsm-311',
    stone: 'touchstone', tier: 'proxy', variant: 'histogram',
    source: 'NYC 311', agency: 'NYC 311 service requests (Socrata erm2-nwe9)',
    vintage: RIPRAP_VINTAGE,
    title: 'Recent 311 flood complaints',
    headline: `${total} calls`,
    subhead: top ? `top descriptor: ${top}` : 'all flood-related descriptors',
    histogram: hist,
    sparkSub: `Within ${num(n.radius_m) ?? 200} m · ${num(n.years) ?? 5} y window. Filtered to flood-relevant descriptors.`,
    docId: 'nyc311', citeId: 'nyc311', mapLayer: 'complaints',
  };
}

function buildNwsObs(state: Final): Card | null {
  const obs = obj(state.nws_obs);
  if (!obs || obs.error || obs.station_id == null) return null;
  const scalars: NonNullable<Card['scalars']> = [];
  if (num(obs.precip_last_hour_mm) != null) scalars.push({ value: `${obs.precip_last_hour_mm} mm`, label: 'precip · 1h' });
  if (num(obs.precip_last_6h_mm) != null) scalars.push({ value: `${obs.precip_last_6h_mm} mm`, label: 'precip · 6h' });
  if (!scalars.length) return null;
  return {
    id: 'fsm-nws-obs',
    stone: 'touchstone', tier: 'empirical', variant: 'scalars',
    source: 'NWS', agency: `NWS ASOS station ${str(obs.station_id) ?? '?'}`,
    vintage: str(obs.obs_time)?.slice(0, 10) ?? RIPRAP_VINTAGE,
    title: 'Recent precipitation',
    scalars,
    sub: `Nearest hourly METAR: ${str(obs.station_name) ?? '?'} (${num(obs.distance_km) ?? '?'} km).`,
    docId: 'nws_obs', citeId: 'nws_obs', mapLayer: 'nws',
  };
}

function buildNoaaTides(state: Final): Card | null {
  const t = obj(state.noaa_tides);
  if (!t || t.error || num(t.observed_ft_mllw) == null) return null;
  const scalars: NonNullable<Card['scalars']> = [
    { value: `${t.observed_ft_mllw} ft`, label: 'observed (MLLW)' },
  ];
  if (num(t.predicted_ft_mllw) != null) scalars.push({ value: `${t.predicted_ft_mllw} ft`, label: 'predicted' });
  if (num(t.residual_ft) != null) scalars.push({ value: `${t.residual_ft} ft`, label: 'residual' });
  return {
    id: 'fsm-noaa',
    stone: 'touchstone', tier: 'empirical', variant: 'scalars',
    source: 'NOAA CO-OPS', agency: `NOAA tide gauge ${str(t.station_name) ?? str(t.station_id) ?? '?'}`,
    vintage: str(t.obs_time)?.slice(0, 10) ?? RIPRAP_VINTAGE,
    title: 'Live water level (nearest tide gauge)',
    scalars,
    sub: 'Residual = observed − astronomical tide; positive residual is wind / surge component.',
    docId: 'noaa_tides', citeId: 'noaa_tides', mapLayer: 'noaa',
  };
}

function buildPrithviLive(state: Final): Card | null {
  const p = obj(state.prithvi_live);
  if (!p?.ok) return null;
  return {
    id: 'fsm-prithvi-live',
    stone: 'touchstone', tier: 'modeled', variant: 'raster-pred',
    source: 'Prithvi-NYC v2', agency: 'msradam/Prithvi-EO-2.0-NYC-Pluvial · v2 fine-tune',
    vintage: str(p.item_datetime)?.slice(0, 10) ?? RIPRAP_VINTAGE,
    title: 'Live Sentinel-2 pluvial flood prediction',
    rasterKind: 'prithvi',
    headline: `${num(p.pct_water_within_500m) ?? 0}%`,
    subhead: `water within 500 m · cloud ${num(p.cloud_cover) ?? '?'}%`,
    sub: 'Test flood IoU 0.5979 on held-out NYC chips. Model interpretation, not a measurement.',
    illustrative: true,
    docId: 'prithvi_live', citeId: 'prithvi_live', mapLayer: 'prithvi',
  };
}

function buildTerramindLulc(state: Final): Card | null {
  const t = obj(state.terramind_lulc);
  if (!t?.ok) return null;
  return {
    id: 'fsm-tm-lulc',
    stone: 'touchstone', tier: 'modeled', variant: 'raster-pred',
    source: 'TerraMind-NYC', agency: 'msradam/TerraMind-NYC-Adapters · LULC LoRA',
    vintage: '2026',
    title: 'Land-cover (current Sentinel-2 chip)',
    rasterKind: 'lulc',
    headline: str(t.dominant_class) ?? 'dominant class',
    subhead: `${num(t.dominant_pct) ?? 0}% of chip`,
    sub: 'Test mIoU 0.5866 on held-out NYC chips.',
    illustrative: true,
    docId: 'tm_lulc', citeId: 'tm_lulc', mapLayer: 'lulc',
  };
}

function buildTtmForecast(state: Final): Card | null {
  const t = obj(state.ttm_forecast);
  if (!t?.available || !t.interesting) return null;
  const peak = num(t.forecast_peak_ft);
  const ahead = num(t.forecast_peak_minutes_ahead);
  if (peak == null || ahead == null) return null;
  return {
    id: 'fsm-ttm-fc',
    stone: 'lodestone', tier: 'modeled', variant: 'timeseries',
    source: 'Granite TTM r2', agency: 'IBM Granite TimeSeries TTM r2 · zero-shot Battery surge',
    vintage: RIPRAP_VINTAGE,
    title: 'Surge nowcast at the Battery — 9.6 h horizon',
    timeseries: { hours: 96, peak: { x: 38, y: 47 }, peakLabel: `${peak} ft @ +${Math.round(ahead/60)}h` },
    headline: `${peak} ft`,
    subhead: 'peak surge residual',
    sub: 'Zero-shot 6-min cadence. Distinct from the fine-tuned Battery surge nowcast.',
    spatialNote: 'regional · Battery, not point-of-query',
    docId: 'ttm_forecast', citeId: 'ttm_forecast',
  };
}

function buildTtmBatterySurge(state: Final): Card | null {
  const t = obj(state.ttm_battery_surge);
  if (!t?.available || !t.interesting) return null;
  const peak = num(t.forecast_peak_m);
  const ahead = num(t.forecast_peak_hours_ahead);
  if (peak == null || ahead == null) return null;
  return {
    id: 'fsm-ttm-batt',
    stone: 'lodestone', tier: 'modeled', variant: 'timeseries',
    source: 'Granite TTM r2 · NYC fine-tune',
    agency: 'msradam/Granite-TTM-r2-Battery-Surge · 96 h horizon',
    vintage: RIPRAP_VINTAGE,
    title: 'Battery storm-surge nowcast (96 h)',
    timeseries: {
      hours: 96,
      peak: { x: ahead, y: Math.round(peak * 100) },
      peakLabel: `${(peak * 100).toFixed(0)} cm @ +${ahead}h`,
    },
    headline: `${(peak * 100).toFixed(0)} cm`,
    subhead: `peak surge · +${ahead}h ahead`,
    sub: 'Test MAE 0.1091 m, −41% vs persistence. Hourly cadence; applies city-wide via NOAA station 8518750.',
    spatialNote: 'regional · The Battery, not point-of-query',
    docId: 'ttm_battery', citeId: 'ttm_battery',
  };
}

function buildNwsAlerts(state: Final): Card | null {
  const a = obj(state.nws_alerts);
  if (!a) return null;
  const n = num(a.n_active) ?? 0;
  if (n <= 0) return null;
  const alerts = Array.isArray(a.alerts) ? (a.alerts as Record<string, unknown>[]) : [];
  return {
    id: 'fsm-nws-alerts',
    stone: 'lodestone', tier: 'modeled', variant: 'tabular',
    source: 'NWS', agency: 'NWS Public Alerts API · flood-relevant filter',
    vintage: RIPRAP_VINTAGE,
    title: `${n} active flood-relevant alert${n === 1 ? '' : 's'}`,
    columns: ['event', 'severity', 'expires'],
    rows: alerts.slice(0, 4).map((al) => [
      str(al.event) ?? '?',
      str(al.severity) ?? '?',
      (str(al.expires) ?? '').slice(0, 16),
    ]),
    sub: 'Live NWS feed. If a FLOOD or FLASH FLOOD WARNING is in this list, foreground it.',
    docId: 'nws_alerts', citeId: 'nws_alerts',
  };
}

function buildCapstoneMeta(final: FinalResult, wallSeconds?: number): Card {
  const m = final.mellea;
  const passed = m?.passed?.length ?? 0;
  const failed = m?.failed?.length ?? 0;
  const total = passed + failed;
  const attempts = m?.attempts ?? 0;
  return {
    id: 'fsm-capstone-meta',
    stone: 'capstone', tier: 'modeled', variant: 'meta',
    source: 'Mellea', agency: 'Capstone synthesis · Granite 4.1 + Mellea grounding check',
    vintage: RIPRAP_VINTAGE,
    title: 'Briefing reconciliation',
    metaRows: [
      { k: 'Mellea reroll',     v: `${attempts} attempt${attempts === 1 ? '' : 's'}` },
      { k: 'Grounding checks',  v: `${passed} / ${total || 4} passed` },
      { k: 'Citations resolved',v: `${final.citations?.length ?? 0}` },
      { k: 'Wall-clock',        v: wallSeconds != null ? `${wallSeconds.toFixed(1)} s` : '—' },
    ],
    sub: 'Capstone produces prose, not cards. This meta-card summarises the reconciler chain that wrote the briefing above.',
    docId: 'capstone',
  };
}

/** Public adapter. Combines per-specialist card builders with the trace
 *  → StoneTrace mapper into a single FindingsData payload. */
export function adaptFinalToFindings(
  final: FinalResult,
  trace: TraceNode | undefined | null,
  wallSeconds?: number,
): FindingsData {
  const f = final as Final;
  const geocode = obj(f.geocode);
  const cards: (Card | null)[] = [
    // Cornerstone
    buildSandy(f, geocode),
    buildDep(f),
    buildIdaHwm(f),
    buildPrithviWater(f),
    buildMicrotopo(f),
    // Keystone
    buildRegisters(f),
    buildTerramindBuildings(f),
    // Touchstone
    buildFloodnet(f),
    buildNyc311(f),
    buildNwsObs(f),
    buildNoaaTides(f),
    buildPrithviLive(f),
    buildTerramindLulc(f),
    // Lodestone
    buildNwsAlerts(f),
    buildTtmForecast(f),
    buildTtmBatterySurge(f),
    // Capstone (always renders if we got here)
    buildCapstoneMeta(final, wallSeconds),
  ];

  return {
    cards: cards.filter((c): c is Card => c != null),
    stones: buildStoneTraces(trace),
    wallSeconds,
  };
}
