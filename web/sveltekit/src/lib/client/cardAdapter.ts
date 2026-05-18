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

/**
 * Format a pebble's `narration.template` against its value dict.
 * Mirrors the backend templated_reconciler's _format_template logic
 * — strict placeholder substitution, returns null when any required
 * field is missing or null so the caller can fall back to
 * narration.short rather than emit a "{field?}" literal.
 *
 * Numbers / booleans are coerced to string; objects raise "missing".
 * Empty / null fields raise "missing" too — without this, a sandy
 * card for an outside address would print "NYC's footprint  this
 * address" with a doubled space where {inside_phrasing} silently
 * resolved to "".
 */
function formatTemplate(template: string, value: unknown): string | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const v = value as Record<string, unknown>;
  let missing = false;
  const out = template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const x = v[key];
    if (x === undefined || x === null || x === '') {
      missing = true;
      return '';
    }
    return String(x);
  });
  return missing ? null : out.trim();
}

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

// buildSandy was a curated builder that hardcoded the NYC-specific
// "Hurricane Sandy 2012 inundation" phrasing in the UI. The
// architecture (location-agnostic pebbles → stones, location-
// specific content from each pebble's manifest) wants this in
// deployments/nyc/manifests/sandy.yaml's narration.template
// instead. The `boolean_zone` shaper wraps the bare bool so the
// template can phrase inside-vs-outside correctly. The templated
// path renders the card.

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

// ─── Type-keyed bespoke variant renderers ─────────────────────────
//
// The framework move (per the user's "type-specific, not city-specific"
// note): bespoke builders are kept for value shapes that earn rich
// rendering — forecasts, ML rasters, asset registers, lulc class
// breakdowns — but each builder is keyed by VALUE SHAPE / display
// variant, not by a hardcoded pebble id. Any pebble that emits the
// expected shape and declares the right `display.variant` gets the
// same bespoke card.
//
// Below: `buildTimeseriesForecast` unifies the previous
// buildTtmForecast + buildTtmBatterySurge. The pebble's value shape
// declares the unit and horizon ("ft" + minutes vs "cm" + hours,
// derived from which `forecast_peak_*` keys are present). The
// manifest's display.variant ('timeseries' | 'timeseries-ft') picks
// the chrome (fine-tune footer for `timeseries-ft`). Future TTM /
// forecast / surge pebbles use this same renderer — drop the
// curated id-keyed builders.

type ForecastValue = {
  available?: boolean;
  interesting?: boolean;
  accelerating?: boolean;
  // Surge — zero-shot (ft / minutes) and fine-tune (m / hours).
  forecast_peak_ft?: number;
  forecast_peak_minutes_ahead?: number;
  forecast_peak_m?: number;
  forecast_peak_hours_ahead?: number;
  // 311 weekly forecast — per-day peak, day offset.
  forecast_peak_day?: number;
  forecast_peak_day_offset?: number;
  forecast_weekly_equivalent?: number;
  // FloodNet sensor — per-day-value peak, day offset.
  forecast_peak_day_value?: number;
  forecast_28d_expected_events?: number;
  history_recent_28d_events?: number;
  // Fine-tune footer fields (only on timeseries-ft variant).
  rmse_m?: number;
  hf_model_card?: string;
  skill_vs_persistence?: string;
  hardware_badge?: string;
  spatial_note?: string;
};

function buildTimeseriesForecast(m: PebbleManifest, value: unknown): Card | null {
  const t = value as ForecastValue | null;
  if (!t || !t.available) return null;
  // `interesting` is the explicit-hide gate (surge floor); `accelerating`
  // is informational only. If neither is present, default to showing the
  // card — every available forecast should surface.
  if (t.interesting === false) return null;
  // Detect unit from which fields the adapter populated. Each branch is
  // its own pebble-family contract:
  //   ft + minutes_ahead       → surge (zero-shot)
  //   m + hours_ahead          → surge (fine-tune, cm display)
  //   peak_day + day_offset    → weekly cadence (311 forecasts)
  //   peak_day_value + offset  → daily cadence (FloodNet sensor)
  let peakLabel: string;
  let headline: string;
  let timeseries: NonNullable<Card['timeseries']>;
  let subhead: string;
  if (num(t.forecast_peak_ft) != null && num(t.forecast_peak_minutes_ahead) != null) {
    const peak = num(t.forecast_peak_ft)!;
    const ahead = num(t.forecast_peak_minutes_ahead)!;
    peakLabel = `${peak} ft @ +${Math.round(ahead / 60)}h`;
    headline = `${peak} ft`;
    timeseries = { hours: 96, peak: { x: 38, y: 47 }, peakLabel };
    subhead = m.narration.short ?? 'peak surge residual';
  } else if (num(t.forecast_peak_m) != null
             && num(t.forecast_peak_hours_ahead) != null) {
    const peak = num(t.forecast_peak_m)!;
    const ahead = num(t.forecast_peak_hours_ahead)!;
    peakLabel = `${(peak * 100).toFixed(0)} cm @ +${ahead}h`;
    headline = `${(peak * 100).toFixed(0)} cm`;
    timeseries = {
      hours: 96,
      peak: { x: ahead, y: Math.round(peak * 100) },
      peakLabel,
    };
    subhead = m.narration.short ?? 'peak surge';
  } else if (num(t.forecast_peak_day) != null
             && num(t.forecast_peak_day_offset) != null) {
    const peak = num(t.forecast_peak_day)!;
    const offset = num(t.forecast_peak_day_offset)!;
    const weekly = num(t.forecast_weekly_equivalent);
    peakLabel = `${peak.toFixed(2)}/day @ +${offset}d`;
    headline = weekly != null
      ? `${weekly.toFixed(1)}/wk`
      : `${peak.toFixed(2)}/day`;
    timeseries = { hours: 96, peak: { x: offset, y: peak }, peakLabel };
    subhead = m.narration.short ?? 'forecast peak';
  } else if (num(t.forecast_peak_day_value) != null
             && num(t.forecast_peak_day_offset) != null) {
    const peak = num(t.forecast_peak_day_value)!;
    const offset = num(t.forecast_peak_day_offset)!;
    const expected = num(t.forecast_28d_expected_events);
    peakLabel = `${peak.toFixed(2)}/day @ +${offset}d`;
    headline = expected != null
      ? `${expected.toFixed(1)} events`
      : `${peak.toFixed(2)}/day`;
    timeseries = { hours: 96, peak: { x: offset, y: peak }, peakLabel };
    subhead = m.narration.short ?? 'sensor forecast peak';
  } else {
    return null;
  }
  const variant: CardVariant =
    (m.display.variant === 'timeseries-ft' || m.display.variant === 'timeseries')
      ? m.display.variant
      : 'timeseries';
  const tier = (m.tier ?? 'modeled') as Card['tier'];
  const source = m.provenance.source_name.split(/[—-]/)[0].trim();
  return {
    id: `fsm-${m.id.replace(/_/g, '-')}`,
    stone: m.stone, tier, variant,
    source, agency: m.provenance.source_name,
    vintage: m.provenance.last_updated?.toString() ?? RIPRAP_VINTAGE,
    title: m.title,
    timeseries,
    headline,
    subhead,
    sub: m.narration.template ?? undefined,
    spatialNote: t.spatial_note,
    docId: m.provenance.doc_id ?? m.id,
    citeId: m.provenance.doc_id ?? m.id,
    // Fine-tune footer: only when the variant is timeseries-ft AND
    // the manifest's provenance carries an HF model card url. Each
    // fine-tuned pebble's adapter emits rmse_m / skill_vs_persistence
    // / hardware_badge alongside the forecast — same shape across
    // any future model-specialised forecast pebble.
    hfModelCard: variant === 'timeseries-ft' ? t.hf_model_card : undefined,
    rmse: variant === 'timeseries-ft' && num(t.rmse_m) != null
      ? `${num(t.rmse_m)!.toFixed(3)} m` : undefined,
    skillVsPersistence: variant === 'timeseries-ft' ? t.skill_vs_persistence : undefined,
    hardwareBadge: variant === 'timeseries-ft' ? t.hardware_badge : undefined,
  };
}

// ── Type-keyed composite register card renderer ─────────────────
//
// Multi-pebble dispatch: when several pebbles in the same stone
// declare `display.variant: register`, this renderer collects rows
// from ALL of them into a single card (vs one card per pebble).
//
// Per-pebble item-extraction heuristic: the adapter emits its rows
// under whichever field name fits the asset class (entrances /
// developments / schools / hospitals / items / features). The
// renderer scans known field names; an explicit `items` array
// always wins so future BYOD registers don't need a heuristic.
//
// `reg` label comes from the manifest icon or the first capitalized
// token of the title — no per-id hardcoding.
type RegisterItem = Record<string, unknown>;
type RegisterValue = {
  available?: boolean;
  items?: RegisterItem[];
  entrances?: RegisterItem[];
  developments?: RegisterItem[];
  schools?: RegisterItem[];
  hospitals?: RegisterItem[];
  features?: RegisterItem[];
};

function _itemsFromRegisterValue(v: RegisterValue): RegisterItem[] {
  if (Array.isArray(v.items)) return v.items;
  if (Array.isArray(v.entrances)) return v.entrances;
  if (Array.isArray(v.developments)) return v.developments;
  if (Array.isArray(v.schools)) return v.schools;
  if (Array.isArray(v.hospitals)) return v.hospitals;
  if (Array.isArray(v.features)) return v.features;
  return [];
}

function _regLabelFromManifest(m: PebbleManifest): string {
  // Prefer a short SOURCE acronym from the manifest's source_name
  // ("MTA — subway/rail entrances register" → "MTA"); else fall back
  // to first capitalized token of the title.
  const src = m.provenance.source_name;
  const dashIdx = Math.min(...['—', '-', ':'].map(c => {
    const i = src.indexOf(c);
    return i < 0 ? Number.MAX_SAFE_INTEGER : i;
  }));
  const head = (dashIdx < Number.MAX_SAFE_INTEGER ? src.slice(0, dashIdx) : src).trim();
  // If the head is short enough (≤6 chars) use it; else first word.
  if (head.length > 0 && head.length <= 6) return head.toUpperCase();
  return (head.split(/\s+/)[0] || m.id).toUpperCase().slice(0, 6);
}

function _itemRow(reg: string, item: RegisterItem): NonNullable<Card['registers']>[number] {
  const label = (str(item.station_name) ?? str(item.development)
                ?? str(item.loc_name) ?? str(item.facility_name)
                ?? str(item.label) ?? str(item.name) ?? 'item');
  const distance = num(item.distance_m);
  const detail_bits: string[] = [];
  if (distance != null) detail_bits.push(`${distance} m`);
  const borough = str(item.borough);
  const routes = str(item.daytime_routes);
  if (routes) detail_bits.push(routes);
  else if (borough) detail_bits.push(borough);
  const sourceId = (str(item.station_id) ?? str(item.tds_num)
                    ?? str(item.loc_code) ?? str(item.fac_id)
                    ?? str(item.source_id) ?? null);
  return {
    reg, tier: 'empirical',
    label, detail: detail_bits.join(' · ') || null,
    sourceId, note: null,
  };
}

function buildRegisterComposite(
  registerManifests: PebbleManifest[],
  state: Final,
): Card | null {
  if (!registerManifests.length) return null;
  const rows: NonNullable<Card['registers']> = [];
  const docIds: string[] = [];
  const agencies: string[] = [];
  // Per-pebble cap so one super-dense register doesn't dominate.
  const PER_PEBBLE_CAP = 4;
  for (const m of registerManifests) {
    const v = (state as Record<string, unknown>)[m.id] as RegisterValue | undefined;
    if (!v) continue;
    const reg = _regLabelFromManifest(m);
    const items = _itemsFromRegisterValue(v);
    if (v.available === false || items.length === 0) {
      rows.push({
        reg, tier: 'empirical',
        label: null, detail: null, sourceId: null,
        note: (m.fallback.message ?? `no ${reg} items in range (silent)`),
      });
      continue;
    }
    for (const it of items.slice(0, PER_PEBBLE_CAP)) {
      rows.push(_itemRow(reg, it));
    }
    const doc = m.provenance.doc_id ?? m.id;
    docIds.push(doc);
    agencies.push(m.provenance.source_name);
  }
  if (!rows.length) return null;
  const fired = rows.filter(r => r.label).length;
  return {
    id: 'fsm-registers',
    stone: 'keystone', tier: 'empirical', variant: 'register',
    source: 'Civic OpenData', agency: `${agencies.length} register${agencies.length === 1 ? '' : 's'} · multi-agency join`,
    vintage: RIPRAP_VINTAGE,
    title: 'Nearby exposed assets',
    registers: rows,
    sub: `${fired} of ${rows.length} register rows have items · joined within range`,
    docId: docIds[0] ?? 'registers',
    citeId: 'registers',
    mapLayer: 'registers',
  };
}

// ── Type-keyed histogram card renderer ──────────────────────────
//
// Pebbles that declare `display.variant: histogram` and emit a
// normalized value shape:
//   { n, histogram: number[], headline_value, subhead_text, narrative,
//     radius_m?, years? }
// nyc311 is the canonical case; future "count me over time" pebbles
// (e.g. boston 311 trended, sea-level rise count series) get the same
// bespoke chrome by declaring the variant + emitting the shape.
type HistogramValue = {
  n?: number;
  histogram?: number[];
  headline_value?: string;
  subhead_text?: string;
  narrative?: string;
  radius_m?: number;
  years?: number;
};

function buildHistogramCard(m: PebbleManifest, value: unknown): Card | null {
  const t = value as HistogramValue | null;
  if (!t) return null;
  const n = num(t.n) ?? 0;
  // Honest negative ("0 calls") still surfaces — same all-clear contract
  // as the NWS / ida_hwm cards. The narrative explains the zero.
  const hist = Array.isArray(t.histogram) ? t.histogram : [];
  const headline = t.headline_value ?? `${n} calls`;
  const radius = num(t.radius_m);
  const years = num(t.years);
  const sparkSub = (radius != null && years != null)
    ? `Within ${radius} m · ${years} y window. Filtered to flood-relevant descriptors.`
    : undefined;
  const tier = (m.tier ?? 'proxy') as Card['tier'];
  const source = m.provenance.source_name.split(/[—-]/)[0].trim();
  return {
    id: `fsm-${m.id.replace(/_/g, '-')}`,
    stone: m.stone, tier, variant: 'histogram',
    source, agency: m.provenance.source_name,
    vintage: m.provenance.last_updated?.toString() ?? RIPRAP_VINTAGE,
    title: m.title,
    headline,
    subhead: t.subhead_text,
    histogram: hist.length ? hist : Array.from({ length: 12 }, () => Math.round(n / 12)),
    sparkSub,
    sub: t.narrative,
    docId: m.provenance.doc_id ?? m.id,
    citeId: m.provenance.doc_id ?? m.id,
    mapLayer: m.display.map_layer ? m.id : null,
  };
}

// ── Type-keyed raster card renderer ─────────────────────────────
//
// Pebbles that declare `display.variant: raster` or `raster-pred`
// and emit a normalized value shape:
//   { headline_value, subhead_text, narrative, raster_kind, illustrative,
//     ok?: bool }
// All raster pebbles (prithvi_water, prithvi_live, future flood-mask
// models) flow through here — no per-pebble id check.
type RasterValue = {
  ok?: boolean;
  available?: boolean;
  headline_value?: string;
  subhead_text?: string;
  narrative?: string;
  raster_kind?: string;
  illustrative?: boolean;
  spatial_note?: string;
};

function buildRasterCard(m: PebbleManifest, value: unknown): Card | null {
  const t = value as RasterValue | null;
  if (!t) return null;
  // Both shapes used: raster-pred (model) sets `ok`; raster (baked)
  // doesn't gate. Drop only when an explicit ok=false is present
  // (the inference-offline case).
  if (t.ok === false || t.available === false) return null;
  const headline = t.headline_value;
  if (!headline) return null;  // adapter didn't emit the contract shape
  const variant: CardVariant =
    (m.display.variant === 'raster' || m.display.variant === 'raster-pred')
      ? m.display.variant
      : 'raster';
  const tier = (m.tier ?? 'modeled') as Card['tier'];
  const source = m.provenance.source_name.split(/[—-]/)[0].trim();
  return {
    id: `fsm-${m.id.replace(/_/g, '-')}`,
    stone: m.stone, tier, variant,
    source, agency: m.provenance.source_name,
    vintage: m.provenance.last_updated?.toString() ?? RIPRAP_VINTAGE,
    title: m.title,
    rasterKind: (t.raster_kind ?? 'prithvi') as 'prithvi' | 'buildings' | 'lulc',
    headline,
    subhead: t.subhead_text,
    sub: t.narrative,
    illustrative: t.illustrative ?? false,
    spatialNote: t.spatial_note,
    docId: m.provenance.doc_id ?? m.id,
    citeId: m.provenance.doc_id ?? m.id,
    mapLayer: m.display.map_layer ? m.id : null,
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
  // Migration in progress: each pebble drops out of this set as its
  // manifest gains a usable narration.template + (if needed) a
  // shaper. Migrated so far: sandy, noaa_tides, water_level,
  // lake_michigan_water_level, nws_obs, nws_alerts — all now flow
  // through the templated path using `{narrative}` placeholders
  // computed in each pebble's Python adapter.
  // microtopo migrated to templated scalars path
  // (manifest narration.template + adapter {narrative} field).
  // Touchstone
  // nyc311 dispatched via buildHistogramCard (display.variant: histogram).
  // Lodestone — all four forecast pebbles (ttm_forecast, ttm_battery_surge,
  // ttm_311_forecast, floodnet_forecast) now flow through the type-keyed
  // buildTimeseriesForecast renderer below (display.variant + value shape).
  // Keystone — the four register pebbles now dispatch via
  // buildRegisterComposite (multi-pebble, variant: register). Drop
  // from this set so they participate in the type-keyed dispatch.
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
    // Format manifest.narration.template against the pebble value
    // (the shaper's job is to ensure value carries the placeholders
    // — sandy's `boolean_zone` shaper emits inside_phrasing /
    // inside / outside_phrasing for the template to consume).
    // Mirrors the backend templated_reconciler's _format_template
    // — if a placeholder is missing, fall back to narration.short.
    const formatted = m.narration.template
      ? formatTemplate(m.narration.template, value)
      : null;
    return { ...base,
             headline: m.narration.short ?? m.title,
             body: formatted
                 ?? (typeof value === 'string' ? value
                     : (m.narration.template ?? undefined)) };
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
    // If the manifest carries a narration.template with the
    // pebble-adapter-built `{narrative}` (or any other placeholder
    // the value supplies), format it as the card's `sub` line so
    // the user reads both the scalar grid AND a sentence-level
    // summary the LLM-citation path also consumes.
    const narrative = m.narration.template
      ? formatTemplate(m.narration.template, value)
      : null;
    return { ...base, scalars, sub: narrative ?? undefined };
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
    // No features and no sample — fall back to the pebble's
    // narration.template formatted against the value (e.g. nws_alerts
    // returns {n_active: 0, alerts: [], narrative: "No active NWS..."};
    // the narrative is the human-readable card body). If the template
    // also can't format, render the manifest's fallback message.
    const tabularNarrative = m.narration.template
      ? formatTemplate(m.narration.template, value)
      : null;
    return { ...base, variant: 'headline',
             headline: tabularNarrative
               ?? m.fallback.message ?? 'No records within range',
             subhead: tabularNarrative ? undefined : (m.narration.short ?? undefined) };
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
    // sandy now flows through the templated path via its manifest's
    // narration.template + the `boolean_zone` shaper. Neighborhood
    // intent still uses a curated builder for now — that path
    // (app/intents/neighborhood.py) is NYC-specific by design.
    isNeighborhood ? buildSandyNta(f) : null,
    // DEP stormwater: address path goes through the templated loop
    // (3 manifests, each emits {narrative} via the dep_scenario
    // shaper); neighborhood path keeps the NYC-specific composite
    // builder.
    isNeighborhood ? buildDepNta(f) : null,
    // ida_hwm now flows through the templated headline path
    // (manifest narration.template + ida_hwm shaper's {narrative}).
    // prithvi_water + prithvi_live dispatch via buildRasterCard in the
    // templated loop below (display.variant: raster / raster-pred).
    // microtopo: address path now flows through templated scalars
    // (Microtopo dataclass emits {narrative}); NTA path stays curated.
    isNeighborhood ? buildMicrotopoNta(f) : null,
    // Keystone
    // registers (mta_entrances, nycha_developments, doe_schools,
    // doh_hospitals) dispatch via buildRegisterComposite in the
    // templated loop below (multi-pebble dispatch on variant: register).
    buildTerramindBuildings(f),
    // Touchstone
    // floodnet now flows through the templated scalars path
    // (n_sensors + n_flood_events_3y + {narrative} from the adapter).
    // nyc311 (address path) dispatches via buildHistogramCard in the
    // templated loop below (display.variant: histogram); NTA path
    // stays curated for now.
    isNeighborhood ? buildNyc311Nta(f) : null,
    // nws_obs, noaa_tides flow through the templated path now
    // (each pebble's adapter emits a {narrative} the manifest's
    // narration.template renders verbatim).
    buildTerramindLulc(f),
    // Lodestone — nws_alerts also migrated to templated path.
    // ttm_forecast + ttm_battery_surge dispatch via buildTimeseriesForecast
    // in the templated loop below (display.variant: timeseries[-ft]).
    // Capstone (only once we have something to summarise)
    hasFinal ? buildCapstoneMeta((final ?? { paragraph: '' }) as FinalResult, wallSeconds) : null,
  ];

  const curatedCards = cards.filter((c): c is Card => c != null);

  // Phase 2 — templated cards for every manifest pebble that didn't get a
  // curated special-builder card. New BYOD pebbles defined only in YAML
  // appear here automatically.
  const templatedCards: Card[] = [];
  const handledIds = new Set<string>();
  for (const stone of pebbleManifest.stones) {
    // Multi-pebble composite dispatch: collect all variant: register
    // pebbles in this stone, render once via buildRegisterComposite.
    // Each register pebble is marked handled so the per-pebble loop
    // below skips it.
    const registerMs = (pebbleManifest.byStone[stone.id] ?? [])
      .filter(m => m.display.variant === 'register'
                   && !SPECIAL_BUILT_IDS.has(m.id));
    if (registerMs.length) {
      const composite = buildRegisterComposite(registerMs, f);
      if (composite) templatedCards.push(composite);
      for (const m of registerMs) handledIds.add(m.id);
    }
    // Per-pebble loop — single-pebble bespoke variants + the generic
    // templated fallback. Type-keyed dispatch by display.variant.
    for (const m of pebbleManifest.byStone[stone.id] ?? []) {
      if (SPECIAL_BUILT_IDS.has(m.id) || handledIds.has(m.id)) continue;
      const value = (f as Record<string, unknown>)[m.id];
      let card: Card | null = null;
      if (m.display.variant === 'timeseries' || m.display.variant === 'timeseries-ft') {
        card = buildTimeseriesForecast(m, value);
      } else if (m.display.variant === 'raster' || m.display.variant === 'raster-pred') {
        card = buildRasterCard(m, value);
      } else if (m.display.variant === 'histogram') {
        card = buildHistogramCard(m, value);
      }
      if (!card) card = buildTemplated(m, value);
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
