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
  Card, CardVariant, FindingsData, StoneKey, StoneMember, StoneTrace
} from '$lib/types/card';
import type { TraceNode, TraceStatus } from '$lib/types/trace';
import type { FinalResult } from '$lib/client/agentStream';
import { pebbleManifest, type PebbleManifest } from '$lib/stores/pebbleManifest.svelte';

/** Reasonable defaults — when the FSM doesn't supply a vintage, fall
 *  back to the Riprap publication date. */
const RIPRAP_VINTAGE = '2026-05';

/** Map the FSM trace's TraceStatus into the v0.4.5 5-state SpecialistStatus.
 *  Crucial split: a specialist that "returned no data" is `silent_by_design`,
 *  not `errored`. The FSM marks both as `silent` in the trace; we
 *  conservatively classify any successful trace-`silent` as
 *  silent_by_design (the spec voice). Anything that raised in the FSM
 *  becomes `errored`. `fan`/`merge` are structural; the few callers
 *  that look at them treat them as fired.
 */
function mapStatus(s: TraceStatus): StoneMember['status'] {
  if (s === 'fan' || s === 'merge') return 'fired';
  if (s === 'silent') return 'silent_by_design';
  if (s === 'error') return 'errored';
  return 'fired';
}

function flattenTrace(node: TraceNode): TraceNode[] {
  return [node, ...(node.children ?? []).flatMap(flattenTrace)];
}

/** Group leaf specialist nodes by the Stone their pebble belongs to.
 *  Source of truth: pebbleManifest.byId — populated from /api/pebbles
 *  at app load, so every manifest in the active deployment is recognised
 *  by definition. A small alias map keeps legacy step names (the
 *  Capstone reconciler emits e.g. `reconcile_granite41`, not a
 *  manifest id) routing to the right Stone. */
const _LEGACY_STEP_TO_STONE: Record<string, StoneKey> = {
  // NTA / neighborhood-aggregate steps don't have their own manifests yet
  sandy_nta: 'cornerstone',
  dep_extreme_2080_nta: 'cornerstone',
  dep_moderate_2050_nta: 'cornerstone',
  dep_moderate_current_nta: 'cornerstone',
  microtopo_nta: 'cornerstone',
  nyc311_nta: 'touchstone',
  rag_nta: 'capstone',
  // Asset-exposure step names that pre-date the matching pebble ids
  mta_entrance_exposure: 'keystone',
  nycha_development_exposure: 'keystone',
  doe_school_exposure: 'keystone',
  doh_hospital_exposure: 'keystone',
  // Specialist clusters not yet ported to manifests
  terramind_synthesis: 'keystone',
  terramind_buildings: 'keystone',
  terramind_lulc: 'touchstone',
  eo_chip_fetch: 'keystone',
  prithvi_eo_v2: 'cornerstone',
  prithvi_eo_live: 'touchstone',
  // Capstone reconciler variants
  reconcile_granite41: 'capstone',
  reconcile_neighborhood: 'capstone',
  reconcile_development: 'capstone',
  reconcile_live_now: 'capstone',
  mellea_reconcile_address: 'capstone',
  mellea_grounding: 'capstone',
  rag_granite_embedding: 'capstone',
  gliner_extract: 'capstone',
};

function stoneForStep(name: string): StoneKey | null {
  const n = name.toLowerCase();
  // Manifest is the truth: any pebble id in the active deployment maps
  // to its stone by definition.
  const pebble = pebbleManifest.byId[n];
  if (pebble) return pebble.stone;
  return _LEGACY_STEP_TO_STONE[n] ?? null;
}

/** Project the live trace against the deployment's pebble roster.
 *
 *  v0.4.5 §3: every Stone's expander shows the full intended roster —
 *  present specialists keep their live status; absent ones land as
 *  `not_invoked` with their declared fallback message. The roster
 *  source is the active deployment's manifests (pebbleManifest.byStone),
 *  not a frontend-hardcoded list, so adding a city = no TS edits.
 */
function fillRosterFromManifests(
  stone: StoneKey,
  liveByName: Map<string, StoneMember>,
): StoneMember[] {
  const roster = pebbleManifest.byStone[stone] ?? [];
  const out: StoneMember[] = [];
  const used = new Set<string>();
  for (const p of roster) {
    const live = liveByName.get(p.id);
    if (live) {
      used.add(p.id);
      out.push({
        ...live,
        // Override id/name with the manifest's display strings so
        // provenance row chrome is consistent across deployments.
        id: p.id,
        name: p.title,
        tier: live.tier ?? p.tier ?? null,
      });
    } else {
      out.push({
        id: p.id,
        name: p.title,
        status: 'not_invoked',
        tier: p.tier ?? null,
        note: p.narration?.short ?? undefined,
      });
    }
  }
  // Any live members the manifest doesn't know about (legacy aliases
  // like `reconcile_granite41`) get appended so we never silently drop
  // a trace row.
  for (const [k, m] of liveByName) {
    if (!used.has(k)) out.push(m);
  }
  return out;
}

function buildStoneTraces(root: TraceNode | undefined | null): StoneTrace[] {
  const buckets: Record<StoneKey, Map<string, StoneMember>> = {
    cornerstone: new Map(), keystone: new Map(),
    touchstone: new Map(), lodestone: new Map(), capstone: new Map(),
  };
  if (root) {
    for (const node of flattenTrace(root)) {
      const stone = stoneForStep(node.name);
      if (!stone) continue;
      buckets[stone].set(node.name, {
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
    members: fillRosterFromManifests(key, buckets[key]),
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
  const sceneDate = str(p.item_datetime)?.slice(0, 10);
  return {
    id: 'fsm-prithvi-live',
    stone: 'touchstone', tier: 'modeled', variant: 'raster-pred',
    source: 'Prithvi-NYC-Pluvial', agency: 'NASA-IBM Prithvi v2 · NYC fine-tune',
    vintage: sceneDate ? `${sceneDate} · Sentinel-2` : 'Sentinel-2',
    title: 'Pluvial flood prediction · Prithvi-NYC-Pluvial',
    rasterKind: 'prithvi',
    headline: `${num(p.pct_water_within_500m) ?? 0}% flooded`,
    subhead: `water within 500 m · cloud ${num(p.cloud_cover) ?? '?'}%`,
    sub: 'Test flood IoU 0.5979 on held-out NYC chips. Model interpretation, not a measurement.',
    illustrative: true,
    docId: 'prithvi_live', citeId: 'prithvi_live', mapLayer: 'prithvi-pluvial',
  };
}

/** Conventional LULC palette — matches the design handoff's LULC card
 *  visual (urban / water / vegetation / barren / wetland). The colors
 *  are layer conventions, NOT new tier signals. */
const LULC_PALETTE: Record<string, string> = {
  urban: '#C66',
  water: '#5B7FB4',
  vegetation: '#5B8A4A',
  barren: '#A89A78',
  wetland: '#D9C75A',
};

function buildTerramindLulc(state: Final): Card | null {
  const t = obj(state.terramind_lulc);
  if (!t?.ok) return null;
  // Translate the FSM's class_fractions dict into the design-system's
  // expected ordered class-mix (urban / water / vegetation / barren /
  // wetland). Unknown class names land in barren as a catch-all.
  const fractions = (obj(t.class_fractions) ?? {}) as Record<string, number>;
  const buckets: Record<keyof typeof LULC_PALETTE, number> = {
    urban: 0, water: 0, vegetation: 0, barren: 0, wetland: 0,
  };
  for (const [k, v] of Object.entries(fractions)) {
    const lk = k.toLowerCase();
    if (lk.includes('urban') || lk.includes('built') || lk.includes('impervious')) buckets.urban += v;
    else if (lk.includes('water')) buckets.water += v;
    else if (lk.includes('tree') || lk.includes('vegetation') || lk.includes('crop') || lk.includes('grass')) buckets.vegetation += v;
    else if (lk.includes('bare') || lk.includes('barren') || lk.includes('soil')) buckets.barren += v;
    else if (lk.includes('wet') || lk.includes('marsh')) buckets.wetland += v;
    else buckets.barren += v;
  }
  const classMix = (Object.entries(buckets) as [keyof typeof LULC_PALETTE, number][])
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({ k, pct: Math.round(v), color: LULC_PALETTE[k] }));

  return {
    id: 'fsm-tm-lulc',
    stone: 'touchstone', tier: 'synthetic', variant: 'lulc',
    source: 'TerraMind v1.2', agency: 'IBM TerraMind v1.2 · Sentinel-2 inputs',
    vintage: 'Sentinel-2',
    title: 'Land use / land cover · TerraMind v1.2',
    rasterKind: 'lulc',
    classMix: classMix.length ? classMix : undefined,
    sub: 'Synthetic prior. LULC palette is a layer convention, not a tier signal.',
    illustrative: true,
    docId: 'tm_lulc', citeId: 'tm_lulc', mapLayer: 'terramind-lulc',
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
    source: 'Granite TTM r2 (zero-shot)', agency: 'IBM Granite-TimeSeries · regional',
    vintage: RIPRAP_VINTAGE,
    title: 'Storm surge nowcast at The Battery — 9.6 h horizon (regional)',
    timeseries: { hours: 96, peak: { x: 38, y: 47 }, peakLabel: `${peak} ft @ +${Math.round(ahead/60)}h` },
    headline: `${peak} ft`,
    subhead: 'peak surge residual · 9.6h horizon · 6-min cadence',
    sub: 'Regional disclosure. Distinct from the fine-tuned Battery surge nowcast.',
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
    stone: 'lodestone', tier: 'modeled', variant: 'timeseries-ft',
    source: 'msradam/Granite-TTM-r2-Battery-Surge',
    agency: 'Granite TTM r2 · NYC-specialized fine-tune',
    vintage: RIPRAP_VINTAGE,
    title: 'Storm surge nowcast at The Battery — 96 h horizon (NYC-specialized fine-tune)',
    timeseries: {
      hours: 96,
      peak: { x: ahead, y: Math.round(peak * 100) },
      peakLabel: `${(peak * 100).toFixed(0)} cm @ +${ahead}h`,
    },
    headline: `${(peak * 100).toFixed(0)} cm`,
    subhead: `peak surge · 96h horizon · hourly cadence`,
    sub: 'Fine-tuned on NYC tide-gauge history. Hourly cadence; applies city-wide via NOAA station 8518750.',
    spatialNote: 'regional · The Battery, not point-of-query',
    docId: 'ttm_battery', citeId: 'ttm_battery',
    // v0.4.5 §5 — fine-tuned-model footer chrome
    hfModelCard: 'huggingface.co/msradam/Granite-TTM-r2-Battery-Surge',
    rmse: '0.157 m',
    skillVsPersistence: '−35% vs persistence',
    hardwareBadge: 'MI300X',
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

// ── Neighborhood NTA card builders ────────────────────────────────────────────

function buildSandyNta(state: Final): Card | null {
  const s = obj(state.sandy_nta);
  if (!s) return null;
  const frac = num(s.fraction) ?? 0;
  const areaKm2 = num(s.polygon_area_m2) != null
    ? ((s.polygon_area_m2 as number) / 1e6).toFixed(2)
    : null;
  return {
    id: 'nta-sandy',
    stone: 'cornerstone', tier: 'empirical', variant: 'scalars',
    source: 'NYC OEM', agency: 'NYC OEM / FEMA · Sandy 2012 inundation zone',
    vintage: '2012-10-29',
    title: 'Hurricane Sandy 2012 inundation — NTA coverage',
    scalars: [
      { value: `${(frac * 100).toFixed(1)}%`, label: 'area inundated' },
      ...(areaKm2 ? [{ value: `${areaKm2} km²`, label: 'NTA area' }] : []),
    ],
    sub: frac > 0
      ? `${(frac * 100).toFixed(1)}% of this NTA was empirically inundated by Sandy (2012). Point data unavailable for neighborhood-mode queries.`
      : 'NTA boundary was outside the empirical 2012 Sandy inundation extent.',
    docId: 'sandy_nta', citeId: 'sandy_nta',
  };
}

function buildDepNta(state: Final): Card | null {
  const d = obj(state.dep_nta);
  if (!d) return null;
  const rows: (string | number)[][] = [];
  for (const [scen, info] of Object.entries(d)) {
    const i = obj(info as unknown);
    if (!i) continue;
    const frac = num(i.fraction_any) ?? 0;
    if (frac <= 0) continue;
    const label = str(i.label) ?? scen;
    rows.push([label.replace(/DEP (Extreme|Moderate) Stormwater \(.*?\)\s*/i, '$1').trim(),
               `${(frac * 100).toFixed(1)}%`, 'fraction flooded']);
  }
  if (!rows.length) return null;
  return {
    id: 'nta-dep',
    stone: 'cornerstone', tier: 'modeled', variant: 'tabular',
    source: 'NYC DEP', agency: 'NYC Department of Environmental Protection · Stormwater Flood Maps',
    vintage: '2021',
    title: 'DEP stormwater flood scenarios — NTA coverage',
    columns: ['scenario', '% NTA flooded', 'metric'],
    rows,
    sub: `${rows.length} scenario${rows.length === 1 ? '' : 's'} show modeled inundation across this NTA.`,
    docId: 'dep_stormwater', citeId: 'dep_nta',
  };
}

function buildNyc311Nta(state: Final): Card | null {
  const s = obj(state.nyc311_nta);
  if (!s) return null;
  const n = num(s.n) ?? 0;
  if (n <= 0) return null;
  const years = num(s.years) ?? 3;
  const desc = s.by_descriptor && typeof s.by_descriptor === 'object'
    ? Object.entries(s.by_descriptor as Record<string, unknown>)
        .map(([k, v]) => [k.replace(/ \(.*\)$/, ''), v as number, ''])
        .slice(0, 4)
    : [];
  return {
    id: 'nta-311',
    stone: 'touchstone', tier: 'proxy', variant: 'tabular',
    source: 'NYC 311', agency: 'NYC 311 Service Requests · flood-relevant descriptors',
    vintage: RIPRAP_VINTAGE,
    title: `NYC 311 flood complaints — ${n.toLocaleString()} in ${years} yr`,
    columns: ['complaint type', 'count', ''],
    rows: desc as (string | number)[][],
    sub: `${n.toLocaleString()} flood-related 311 service requests in this NTA over the past ${years} years.`,
    docId: 'nyc311_nta', citeId: 'nyc311_nta',
  };
}

function buildMicrotopoNta(state: Final): Card | null {
  const m = obj(state.microtopo_nta);
  if (!m) return null;
  const elev = num(m.elev_median_m);
  if (elev == null) return null;
  const scalars = [
    { value: `${elev.toFixed(1)} m`, label: 'median elevation' },
  ];
  if (num(m.hand_median_m) != null)
    scalars.push({ value: `${(m.hand_median_m as number).toFixed(1)} m`, label: 'median HAND' });
  if (num(m.twi_median) != null)
    scalars.push({ value: `${(m.twi_median as number).toFixed(1)}`, label: 'median TWI' });
  if (num(m.frac_hand_lt1) != null)
    scalars.push({ value: `${((m.frac_hand_lt1 as number) * 100).toFixed(0)}%`, label: 'cells HAND < 1 m' });
  return {
    id: 'nta-microtopo',
    stone: 'cornerstone', tier: 'proxy', variant: 'scalars',
    source: 'USGS 3DEP', agency: 'USGS 3DEP DEM (LiDAR-derived) · NTA polygon aggregate',
    vintage: '2018',
    title: 'Microtopography — NTA aggregate',
    scalars,
    sub: 'Aggregated over all DEM cells within the NTA boundary. HAND < 1 m = very close to drainage channel.',
    docId: 'microtopo_nta', citeId: 'microtopo_nta',
  };
}

function buildCapstoneMeta(final: FinalResult, wallSeconds?: number): Card {
  // v0.4.5 §2 — wire the four metrics to the reconciler's actual state.
  // The FSM emits `mellea` as `{ rerolls, n_attempts, requirements_passed,
  // requirements_failed, requirements_total }` (the mellea_validator
  // shape). Earlier UI types used `{ passed, failed, attempts }`; we
  // accept both so cards keep rendering across backend versions.
  const m = (final.mellea ?? {}) as Record<string, unknown>;
  // The templated reconciler (no-LLM tier) emits tier='templated' +
  // n_attempts=0 + empty requirements lists. Mellea grounding doesn't
  // run at all in that mode, so "0/4 passed grounding checks" reads
  // like a failure when it's actually "no LLM, no grounding loop".
  const isTemplated = (m.tier === 'templated');
  const passedArr = Array.isArray(m.requirements_passed)
    ? (m.requirements_passed as unknown[])
    : Array.isArray(m.passed) ? (m.passed as unknown[]) : [];
  const failedArr = Array.isArray(m.requirements_failed)
    ? (m.requirements_failed as unknown[])
    : Array.isArray(m.failed) ? (m.failed as unknown[]) : [];
  const passed = passedArr.length;
  const failed = failedArr.length;
  const totalChecks = (typeof m.requirements_total === 'number'
    ? (m.requirements_total as number)
    : (passed + failed)) || 4;
  const attempts = (typeof m.n_attempts === 'number'
    ? (m.n_attempts as number)
    : (typeof m.attempts === 'number' ? (m.attempts as number) : 0));
  const rerollsField = typeof m.rerolls === 'number' ? (m.rerolls as number) : null;
  const rerolls = rerollsField ?? Math.max(0, attempts - 1);
  // final.citations may be a Record<docId, citation> in templated tier
  // or an Array in LLM tier; length accordingly.
  const citesContainer = final.citations as unknown;
  const cites = Array.isArray(citesContainer)
    ? citesContainer.length
    : (citesContainer && typeof citesContainer === 'object'
        ? Object.keys(citesContainer as Record<string, unknown>).length : 0);
  return {
    id: 'fsm-capstone-meta',
    stone: 'capstone', tier: 'modeled', variant: 'meta',
    source: isTemplated ? 'Templated' : 'Mellea',
    agency: isTemplated
      ? 'Capstone synthesis · templated tier (no LLM, no grounding loop)'
      : 'Capstone synthesis · Granite 4.1 + Mellea grounding check',
    vintage: RIPRAP_VINTAGE,
    title: 'Briefing reconciliation',
    metaRows: [
      { k: isTemplated ? 'tier' : 'mellea reroll',
        v: isTemplated ? 'templated · deterministic'
                       : `${rerolls} reroll${rerolls === 1 ? '' : 's'}` },
      { k: 'grounding checks',
        v: isTemplated ? 'n/a — no LLM loop'
                       : `${passed}/${totalChecks} passed` },
      { k: 'citations resolved', v: `${cites}` },
      { k: 'wall-clock',         v: wallSeconds != null ? `${wallSeconds.toFixed(1)} s` : '—' },
    ],
    sub: 'Capstone produces prose, not cards. This meta-card is the integrity-narration UI for the entire pipeline.',
    docId: 'capstone',
  };
}

/* ── Templated card builder (BYOD path).
 *
 * For every pebble in `/api/pebbles` that doesn't have a special builder
 * above, we render a generic evidence card driven entirely by the
 * manifest + the pebble's value dict. This is what makes BYOD work:
 * declaring a new pebble in YAML produces a real card with zero
 * frontend code edits.
 *
 * Mapping from `display.kind` → CardVariant:
 *    text     → headline   (narration.short fills `headline`)
 *    stat     → scalars    (every numeric field becomes a scalar cell)
 *    list     → tabular    (features[] becomes rows)
 *    chart    → meta       (no canonical chart shape yet; falls back to meta)
 *    map_only → null       (no card body; data only appears on the map)
 *
 * Chrome (source / agency / title / docId / cites) comes from
 * `manifest.provenance` + `manifest.title`.
 */
const KIND_TO_VARIANT: Record<PebbleManifest['display']['kind'], CardVariant | null> = {
  text: 'headline',
  stat: 'scalars',
  list: 'tabular',
  chart: 'meta',
  map_only: null,
};

/** Set of pebble ids that already have a special builder above. The
 *  templated pass skips these; they appear via the curated path. */
const SPECIAL_BUILT_IDS = new Set<string>([
  // Cornerstone
  'sandy', 'dep_extreme_2080', 'dep_moderate_2050', 'dep_moderate_current',
  'ida_hwm', 'prithvi_water', 'microtopo',
  // Touchstone
  'floodnet', 'nyc311', 'nws_obs', 'noaa_tides', 'prithvi_live',
  // Lodestone
  'nws_alerts', 'ttm_forecast', 'ttm_battery_surge', 'ttm_311_forecast',
  'floodnet_forecast',
  // Keystone — the four asset-class registers are rendered together
  // by buildRegisters() as a single `register`-variant card, not four
  // separate cards. Listing them here keeps the templated pass from
  // emitting duplicates.
  'mta_entrances', 'nycha_developments', 'doe_schools', 'doh_hospitals',
]);

function buildTemplated(m: PebbleManifest, value: unknown): Card | null {
  const variant = KIND_TO_VARIANT[m.display.kind];
  if (variant === null) return null;
  const tier = m.type === 'model' ? 'modeled'
             : m.type === 'live'  ? 'empirical'
             : 'empirical';
  const source = m.provenance.source_name.split(/[—-]/)[0].trim();
  const vintage = m.provenance.last_updated ?? RIPRAP_VINTAGE;
  const base: Card = {
    id: `pebble-${m.id}`,
    stone: m.stone,
    tier,
    variant: variant ?? 'meta',
    source,
    agency: m.provenance.source_name,
    vintage,
    title: m.title,
    docId: m.provenance.doc_id ?? m.id,
    citeId: m.provenance.doc_id ?? m.id,
    mapLayer: m.display.map_layer ? m.id : null,
  };
  // Pebble offline / no value → render a "no data" headline card so the
  // pebble is still surfaced (with its provenance) instead of vanishing.
  if (value === null || value === undefined) {
    return { ...base, variant: 'headline',
             headline: m.fallback.message ?? 'No data',
             subhead: m.narration.short ?? undefined };
  }
  if (variant === 'headline') {
    return { ...base,
             headline: m.narration.short ?? m.title,
             body: (typeof value === 'string') ? value
                 : (m.narration.template ?? undefined) };
  }
  if (variant === 'scalars') {
    const scalars: NonNullable<Card['scalars']> = [];
    // Fields that are metadata, not user-facing measurements: drop
    // them from the scalar grid (they're noise — station_id is in
    // the card title, station_lat/lon are implied by station_name +
    // distance_km, version/cache fields don't help a reader). The
    // Chicago Lake Michigan card was rendering with only lat/lon
    // because the observed/predicted values came back null and the
    // junk fields took over.
    const SCALAR_IGNORE = new Set([
      'station_lat', 'station_lon', 'station_id',
      'aoi_radius_m', 'radius_m', 'cache_age_s',
      // Back-compat alias of observed_ft (the datum-aware key) the
      // noaa_tides adapter keeps for legacy LLM-citation paths; if
      // both are present (Boston, Chicago) the card would show the
      // same value twice.
      'observed_ft_mllw', 'predicted_ft_mllw',
    ]);
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
        if (SCALAR_IGNORE.has(k)) continue;
        if (typeof v === 'number' && Number.isFinite(v)) {
          scalars.push({ value: `${v}`, label: k });
        }
      }
    } else if (typeof value === 'number') {
      scalars.push({ value: `${value}`, label: m.title });
    } else if (typeof value === 'boolean') {
      scalars.push({ value: value ? 'yes' : 'no', label: m.title });
    }
    if (!scalars.length) {
      // No real measurement scalars. Look for an `error` string the
      // pebble may have surfaced and render that as the headline so
      // the user knows the source was unreachable — not silent.
      const errStr = (typeof value === 'object' && value !== null
        ? (value as Record<string, unknown>).error
        : null);
      return { ...base, variant: 'headline',
               headline: typeof errStr === 'string'
                 ? `Source unavailable — ${errStr.split('\n')[0].slice(0, 80)}`
                 : (m.fallback.message ?? 'No measurements'),
               subhead: m.narration.short ?? undefined };
    }
    return { ...base, scalars };
  }
  if (variant === 'tabular') {
    const v = value as {
      features?: { properties?: Record<string, unknown>; distance_m?: number }[];
      // socrata / ckan-records adapters: summary-shape with n_records +
      // a sample[] of plain row objects + top_by_*.
      // n_truncated=true means n_records hit the SQL LIMIT cap, so
      // the real count is >= n_records — render as "N+ records".
      sample?: Record<string, unknown>[];
      n_records?: number;
      n_truncated?: boolean;
      radius_m?: number;
    };
    // Path A — GeoJSON-style features
    const feats = Array.isArray(v?.features) ? v.features : [];
    if (feats.length) {
      const cols = Object.keys(feats[0]?.properties ?? {});
      const rows: (string | number)[][] = [];
      for (const f of feats.slice(0, 8)) {
        const row: (string | number)[] = [];
        for (const c of cols) {
          const val = f.properties?.[c];
          row.push(typeof val === 'number' || typeof val === 'string' ? val : '—');
        }
        rows.push(row);
      }
      return { ...base, columns: cols.length ? cols : ['feature'], rows,
               sub: `${feats.length} feature${feats.length === 1 ? '' : 's'} within range` };
    }
    // Path B — socrata / ckan-records summary shape (city_311 pebbles).
    // Boston / Chicago / SF emit { n_records, sample, top_by_reason }.
    // Without this branch the card silently returned null, so users
    // saw "Boston 311 received 283 records" in the briefing paragraph
    // but no card under the Touchstone Stone.
    const sample = Array.isArray(v?.sample) ? v.sample : [];
    if (sample.length) {
      const cols = Object.keys(sample[0]);
      const rows: (string | number)[][] = sample.slice(0, 8).map((row) =>
        cols.map((c) => {
          const val = row[c];
          return typeof val === 'number' || typeof val === 'string' ? val : '—';
        }),
      );
      // Humanize the column headers so the card reads "Case title"
      // instead of "case_title". The raw API field names are kept on
      // the underlying data; only the rendered header swaps.
      const HEADER_LABELS: Record<string, string> = {
        // Boston Analyze CKAN — 311
        case_title: 'Case', reason: 'Reason', type: 'Type',
        open_dt: 'Opened', neighborhood: 'Neighborhood',
        // Chicago Socrata — 311
        sr_type: 'Type', sr_short_code: 'Code',
        status: 'Status', created_date: 'Opened',
        // SF Socrata — 311
        service_name: 'Service', service_subtype: 'Subtype',
        status_description: 'Status',
        requested_datetime: 'Opened',
        analysis_neighborhood: 'Neighborhood',
      };
      const prettyCols = cols.map((c) => HEADER_LABELS[c] ?? c);
      const n = v?.n_records ?? sample.length;
      const nLabel = v?.n_truncated ? `${n}+` : String(n);
      const rad = v?.radius_m;
      return {
        ...base, columns: prettyCols, rows,
        sub: rad
          ? `${nLabel} record${n === 1 ? '' : 's'} within ${rad} m`
          : `${nLabel} record${n === 1 ? '' : 's'}`,
      };
    }
    // True empty — render a "no data" headline so the pebble is still
    // visible with its provenance, not silently missing.
    return { ...base, variant: 'headline',
             headline: m.fallback.message ?? 'No records within range',
             subhead: m.narration.short ?? undefined };
  }
  // meta fallback (chart pebbles without a special builder)
  const metaRows: { k: string; v: string }[] = [];
  if (typeof value === 'object' && value !== null) {
    for (const [k, v] of Object.entries(value as Record<string, unknown>).slice(0, 6)) {
      metaRows.push({ k, v: typeof v === 'object' ? JSON.stringify(v).slice(0, 40) : String(v) });
    }
  }
  return { ...base, variant: 'meta', metaRows,
           sub: m.narration.short ?? undefined };
}

/** Public adapter. Combines per-specialist card builders with the trace
 *  → StoneTrace mapper into a single FindingsData payload.
 *
 *  Accepts either a real FinalResult (at end-of-stream) or a partial
 *  one synthesized from in-flight step events (during streaming). Each
 *  builder returns null when its slice of state is missing — so cards
 *  pop into the rail as their specialist completes, without waiting
 *  for the full reconcile. */
export function adaptFinalToFindings(
  final: FinalResult | Partial<FinalResult> | null | undefined,
  trace: TraceNode | undefined | null,
  wallSeconds?: number,
  /** When true, the Capstone meta card renders even with a stub final
   *  (we always want the run-summary). When false (no final at all),
   *  the meta card is skipped — there's nothing to summarise yet. */
  hasFinal: boolean = true,
): FindingsData {
  const f = (final ?? {}) as Final;
  const geocode = obj(f.geocode);
  const isNeighborhood = str(f.intent) === 'neighborhood';
  const cards: (Card | null)[] = [
    // Cornerstone
    isNeighborhood ? buildSandyNta(f) : buildSandy(f, geocode),
    isNeighborhood ? buildDepNta(f) : buildDep(f),
    buildIdaHwm(f),
    buildPrithviWater(f),
    isNeighborhood ? buildMicrotopoNta(f) : buildMicrotopo(f),
    // Keystone
    buildRegisters(f),
    buildTerramindBuildings(f),
    // Touchstone
    buildFloodnet(f),
    isNeighborhood ? buildNyc311Nta(f) : buildNyc311(f),
    buildNwsObs(f),
    buildNoaaTides(f),
    buildPrithviLive(f),
    buildTerramindLulc(f),
    // Lodestone
    buildNwsAlerts(f),
    buildTtmForecast(f),
    buildTtmBatterySurge(f),
    // Capstone (only once we have something to summarise)
    hasFinal ? buildCapstoneMeta((final ?? { paragraph: '' }) as FinalResult, wallSeconds) : null,
  ];

  const curatedCards = cards.filter((c): c is Card => c != null);

  // Phase 2 — templated cards for every manifest pebble that didn't get a
  // curated special-builder card. New BYOD pebbles defined only in YAML
  // appear here automatically.
  const templatedCards: Card[] = [];
  for (const stone of pebbleManifest.stones) {
    for (const m of pebbleManifest.byStone[stone.id] ?? []) {
      if (SPECIAL_BUILT_IDS.has(m.id)) continue;
      const value = (f as Record<string, unknown>)[m.id];
      const card = buildTemplated(m, value);
      if (card) templatedCards.push(card);
    }
  }

  return {
    cards: [...curatedCards, ...templatedCards],
    stones: buildStoneTraces(trace),
    wallSeconds,
    emissions: (f as { emissions?: FindingsData['emissions'] }).emissions,
  };
}

/** Per-step-event live-state mapper. The FSM action `step_X` writes to
 *  state key `X` (sometimes munged — e.g. `step_311` writes `nyc311`,
 *  `step_terramind` writes `terramind`). The SSE `step.result` payload
 *  is a slim summary (not the full doc body); cards adapt to whichever
 *  fields are present.
 *
 *  Mutates `live` in place and returns the keys that changed so callers
 *  can decide whether to re-render. */
export function applyStepEventToLiveState(
  live: Record<string, unknown>,
  stepName: string,
  result: unknown,
  ok: boolean,
): string[] {
  const STEP_TO_STATE: Record<string, string> = {
    sandy_inundation: 'sandy',
    dep_stormwater: 'dep',
    floodnet: 'floodnet',
    nyc311: 'nyc311',
    noaa_tides: 'noaa_tides',
    nws_alerts: 'nws_alerts',
    nws_obs: 'nws_obs',
    ttm_forecast: 'ttm_forecast',
    ttm_311_forecast: 'ttm_311_forecast',
    ttm_battery_surge: 'ttm_battery_surge',
    floodnet_forecast: 'floodnet_forecast',
    ida_hwm_2021: 'ida_hwm',
    prithvi_eo_v2: 'prithvi_water',
    prithvi_eo_live: 'prithvi_live',
    microtopo_lidar: 'microtopo',
    mta_entrance_exposure: 'mta_entrances',
    nycha_development_exposure: 'nycha_developments',
    doe_school_exposure: 'doe_schools',
    doh_hospital_exposure: 'doh_hospitals',
    terramind_synthesis: 'terramind',
    terramind_lulc: 'terramind_lulc',
    terramind_buildings: 'terramind_buildings',
    eo_chip_fetch: 'eo_chip',
    geocode: 'geocode',
    // Neighborhood NTA chain
    sandy_nta: 'sandy_nta',
    dep_extreme_2080_nta: 'dep_nta',
    dep_moderate_2050_nta: 'dep_nta',
    dep_moderate_current_nta: 'dep_nta',
    nyc311_nta: 'nyc311_nta',
    microtopo_nta: 'microtopo_nta',
  };
  const key = STEP_TO_STATE[stepName];
  if (!key) return [];

  // Translate the slim summary shapes the FSM emits into the
  // doc-payload shapes the card builders expect. Mostly identity
  // (the summaries already nest the relevant fields), with a few
  // exceptions documented inline.
  if (stepName === 'sandy_inundation') {
    // FSM summary: { inside: bool }. Adapter expects state.sandy === true.
    const r = result as Record<string, unknown> | null;
    live[key] = ok && r?.inside === true ? true : (ok ? false : null);
  } else if (stepName === 'dep_stormwater') {
    // FSM summary: { dep_extreme_2080: 'label', dep_moderate_2050: 'label', ... }.
    // Adapter expects state.dep[scen] = { depth_class, depth_label }.
    // Reconstruct depth_class>0 from any non-empty label.
    const r = (result as Record<string, unknown>) ?? {};
    const dep: Record<string, unknown> = {};
    for (const [scen, label] of Object.entries(r)) {
      const lbl = typeof label === 'string' ? label : '';
      if (!lbl) continue;
      dep[scen] = { depth_class: 1, depth_label: lbl };
    }
    live[key] = Object.keys(dep).length ? dep : null;
  } else if (ok && result != null) {
    live[key] = result;
  } else {
    live[key] = null;
  }

  return [key];
}
