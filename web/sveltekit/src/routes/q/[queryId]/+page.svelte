<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import Briefing from '$lib/components/briefing/Briefing.svelte';
  import CompareBriefing from '$lib/components/briefing/CompareBriefing.svelte';
  import CitationDrawer from '$lib/components/briefing/CitationDrawer.svelte';
  import TraceUI from '$lib/components/trace/TraceUI.svelte';
  import RipMap from '$lib/components/map/RipMap.svelte';
  import MapLegend from '$lib/components/map/MapLegend.svelte';
  import SkeletonBriefing from '$lib/components/states/SkeletonBriefing.svelte';
  import RerollBanner from '$lib/components/states/RerollBanner.svelte';
  import ErrorCard from '$lib/components/states/ErrorCard.svelte';
  import FindingsRegion from '$lib/components/findings/FindingsRegion.svelte';
  import { adaptFinalToFindings, applyStepEventToLiveState } from '$lib/client/cardAdapter';
  import type { Density, ProvenanceMode, FindingsData } from '$lib/types/card';
  import type { ErrorKey, RegisterData } from '$lib/types/states';
  import { extractRegisters } from '$lib/client/registerAdapter';
  // Mellea rejection sampling is Riprap's sole grounding mechanism.
  // Refusal classification (Granite Guardian, then a planner shim) was
  // evaluated and dropped — see experiments/06_granite_guardian/.
  import type { BriefingBlock, Citation } from '$lib/types/claim';
  import type { TraceNode } from '$lib/types/trace';
  import { tierForStep } from '$lib/types/tier';
  import { briefingState, persistSnapshot } from '$lib/stores/briefingState.svelte';
  import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';
  import { deployment } from '$lib/stores/deployment.svelte';
  import { openAgentStream, type PlanInfo, type FinalResult } from '$lib/client/agentStream';
  import { parseBriefing, citationFromMeta } from '$lib/client/parseBriefing';
  import {
    fetchSandy, fetchDep, fetchPrithviSynthetic, fetchProxyDots,
    fetchIdaHwm, fetchSandyNta, fetchDepNta
  } from '$lib/client/mapLayers';
  import type { FeatureCollection } from 'geojson';

  let queryId = $derived(page.params.queryId ?? '');
  let queryText = $derived(() => {
    try { return decodeURIComponent(queryId); } catch { return queryId; }
  });

  let plan = $state<PlanInfo | null>(null);
  let planTokens = $state('');
  let markdown = $state('');
  let finalResult = $state<FinalResult | null>(null);
  let streamDone = $state(false);

  let attempt = $state<number>(0);
  let attemptMax = $state<number>(2);
  let firstTokenSeen = $state(false);
  let geocodeSucceeded = $state(false);
  // True once the SSE handshake has emitted its `deployment` event,
  // i.e. pebbleManifest and `deployment` store now reflect the
  // routed-to city. False = the page is still on the server's boot
  // (NYC) scaffold; an error in this state must clear the scaffold
  // rather than leave NYC ghost rows visible.
  let deploymentResolved = $state(false);
  /** Last attempt's draft, dimmed below the reroll banner per v0.4.2 §11. */
  let priorDraft = $state<string>('');
  let errorState = $state<ErrorKey | null>(null);
  let registers = $state<RegisterData[]>([]);

  let traceRoot = $state<TraceNode>({
    id: 'root', name: 'briefing.run', status: 'ok', ms: 0, tier: null, children: []
  });

  /** Findings region state — lifted to the page so the briefing's map
   *  can read the linked card's mapLayer on hover. */
  let linkedKey = $state<string | null>(null);
  let density = $state<Density>('comfortable');
  let provenanceMode = $state<ProvenanceMode>('smart');
  // ?grammar=1 surfaces the dev-only card-grammar catalog. Read only on
  // the client — adapter-static forbids url.searchParams at prerender time.
  let showGrammar = $state(false);
  $effect(() => {
    if (typeof window !== 'undefined') {
      showGrammar = new URL(window.location.href).searchParams.get('grammar') === '1';
    }
  });
  let runStartedAt = $state<number | null>(null);
  let runWallSeconds = $state<number | undefined>(undefined);

  /** Live per-specialist results, keyed by FSM state name (sandy / dep
   *  / floodnet / ...). Updated incrementally on every `step` event so
   *  cards stream into the rail as their specialists complete; the
   *  full final payload merges in once the reconcile event fires. */
  let liveResults = $state<Record<string, unknown>>({});
  /** Bumped on every step event so the $derived below recomputes even
   *  though Svelte doesn't deep-track plain objects. */
  let liveTick = $state(0);

  /** Compose the FindingsData payload. During streaming we feed the
   *  adapter from `liveResults` (slim per-step summaries). When `final`
   *  arrives, its richer payload supersedes — same key shape, just
   *  more fields populated. */
  let findingsData = $derived.by<FindingsData>(() => {
    void liveTick;
    if (finalResult) {
      const merged = { ...liveResults, ...finalResult } as Partial<typeof finalResult>;
      return adaptFinalToFindings(merged, traceRoot, runWallSeconds, true);
    }
    return adaptFinalToFindings(liveResults, traceRoot, runWallSeconds, false);
  });

  function handleFindingsLink(key: string | null) { linkedKey = key; }
  function handleFindingsCite(citeId: string) {
    const el = document.getElementById('region-cites');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    void citeId;
  }

  /** Steps that share the Granite TTM r2 foundation model — grouped
   *  under a synthetic parent in the trace UI so the architectural
   *  story ("one foundation model, multiple data streams") is legible
   *  without requiring the reader to spot the model field on each
   *  child individually. */
  const TTM_STEPS = new Set(['ttm_forecast', 'ttm_311_forecast', 'floodnet_forecast']);
  const TTM_PARENT_ID = 'group-ttm-r2';

  /** Headline-fact preview for the collapsed trace row. Specialist
   *  output is the full structured payload (revealed on click); this
   *  is just the one-line summary that fits on the row alongside the
   *  action name. Designed for auditability legibility — a reader
   *  scanning the trace gets the gist without expanding every row. */
  function summarizeStepNote(
    step: string,
    result: unknown,
    err: string | null | undefined,
    status: TraceNode['status']
  ): string | undefined {
    if (status === 'error') return err ?? undefined;
    if (status === 'silent') return err ?? 'no data';
    if (result == null || typeof result !== 'object') return undefined;
    const r = result as Record<string, unknown>;
    // Per-specialist key fields. Ordering: most-headline-y first.
    const keys: Record<string, string[]> = {
      sandy_inundation: ['inside'],
      dep_stormwater: ['dep_extreme_2080', 'dep_moderate_2050'],
      floodnet: ['n_sensors', 'n_events_3y'],
      nyc311: ['n'],
      noaa_tides: ['observed_ft_mllw', 'residual_ft', 'station'],
      nws_alerts: ['n_active'],
      nws_obs: ['p1h_mm', 'p6h_mm', 'station'],
      ttm_forecast: ['forecast_peak_ft', 'forecast_peak_min_ahead'],
      ttm_311_forecast: ['forecast_mean', 'forecast_peak', 'accelerating'],
      ida_hwm_2021: ['n_within_800m', 'max_height_above_gnd_ft'],
      prithvi_eo_v2: ['inside_water_polygon', 'nearest_distance_m'],
      prithvi_eo_live: ['scene_date', 'pct_water_500m'],
      microtopo_lidar: ['elev_m', 'pct_200m', 'relief_m'],
      mta_entrance_exposure: ['n_entrances', 'n_inside_sandy_2012', 'n_in_dep_extreme_2080'],
      nycha_development_exposure: ['n_developments', 'n_inside_sandy_2012', 'n_in_dep_extreme_2080'],
      doe_school_exposure: ['n_schools', 'n_inside_sandy_2012'],
      doh_hospital_exposure: ['n_hospitals', 'n_inside_sandy_2012'],
      floodnet_forecast: ['sensor_id', 'distance_m', 'forecast_28d', 'accelerating'],
      terramind_synthesis: ['tim_chain', 'dem_mean_m'],
      rag_granite_embedding: ['hits'],
      gliner_extract: ['sources']
    };
    const fieldOrder = keys[step];
    const pairs: string[] = [];
    if (fieldOrder) {
      for (const k of fieldOrder) {
        if (r[k] !== undefined) pairs.push(fmtKV(k, r[k]));
        if (pairs.length >= 3) break;
      }
    } else {
      // Fallback: first 2 scalar fields.
      for (const [k, v] of Object.entries(r)) {
        if (v !== null && (typeof v !== 'object')) {
          pairs.push(fmtKV(k, v));
          if (pairs.length >= 2) break;
        }
      }
    }
    return pairs.join(' · ') || undefined;
  }

  /** Build the register-points FeatureCollection from the FSM final
   *  state. Subway entrances, schools, and hospitals each contribute
   *  Point features with the auditability properties (name, doc_id,
   *  kind, inside_sandy_2012) the map click popup surfaces. */
  function buildRegisterPointsFc(fr: Record<string, unknown>): FeatureCollection {
    const features: GeoJSON.Feature[] = [];
    const mta = fr['mta_entrances'] as Record<string, unknown> | null | undefined;
    if (mta && Array.isArray(mta['entrances'])) {
      for (const e of mta['entrances'] as Record<string, unknown>[]) {
        const lat = Number(e['entrance_lat']); const lon = Number(e['entrance_lon']);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
        features.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [lon, lat] },
          properties: {
            kind: 'subway',
            name: `${e['station_name'] ?? '?'} (${e['daytime_routes'] ?? '?'})`,
            doc_id: `mta_entrance_${e['station_id'] ?? ''}`,
            inside_sandy_2012: e['inside_sandy_2012'] === true
          }
        });
      }
    }
    const sch = fr['doe_schools'] as Record<string, unknown> | null | undefined;
    if (sch && Array.isArray(sch['schools'])) {
      for (const s of sch['schools'] as Record<string, unknown>[]) {
        const lat = Number(s['school_lat']); const lon = Number(s['school_lon']);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
        features.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [lon, lat] },
          properties: {
            kind: 'school',
            name: String(s['loc_name'] ?? s['school_name'] ?? '?'),
            doc_id: `doe_school_${s['loc_code'] ?? ''}`,
            inside_sandy_2012: s['inside_sandy_2012'] === true
          }
        });
      }
    }
    const ny = fr['nycha_developments'] as Record<string, unknown> | null | undefined;
    if (ny && Array.isArray(ny['developments'])) {
      // NYCHA findings carry centroid_lat/lon; the development polygon
      // is not serialized in the SSE payload. Render as larger filled
      // circles colored by Sandy-zone membership (binary, from the
      // pre-built catalog at data/registers/nycha.json).
      for (const d of ny['developments'] as Record<string, unknown>[]) {
        const lat = Number(d['centroid_lat']); const lon = Number(d['centroid_lon']);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
        const inSandy = Boolean(d['inside_sandy_2012']);
        features.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [lon, lat] },
          properties: {
            kind: 'nycha',
            name: String(d['development'] ?? '?'),
            doc_id: `nycha_dev_${d['tds_num'] ?? ''}`,
            inside_sandy_2012: inSandy
          }
        });
      }
    }
    const hos = fr['doh_hospitals'] as Record<string, unknown> | null | undefined;
    if (hos && Array.isArray(hos['hospitals'])) {
      for (const h of hos['hospitals'] as Record<string, unknown>[]) {
        const lat = Number(h['hospital_lat']); const lon = Number(h['hospital_lon']);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
        features.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [lon, lat] },
          properties: {
            kind: 'hospital',
            name: String(h['facility_name'] ?? '?'),
            doc_id: `nyc_hospital_${h['fac_id'] ?? ''}`,
            inside_sandy_2012: h['inside_sandy_2012'] === true
          }
        });
      }
    }
    return { type: 'FeatureCollection', features };
  }

  /** NYCHA development polygons. Currently a no-op: the dataclass
   *  serialized through SSE doesn't include geometry. Rendered as
   *  circle features in buildRegisterPointsFc instead until the
   *  backend serializes geometry_geojson. */
  function buildRegisterPolygonsFc(_fr: Record<string, unknown>): FeatureCollection {
    return { type: 'FeatureCollection', features: [] };
  }

  /** Total count of TraceNode descendants (incl. nested children) —
   *  used to mint stable IDs on each new step regardless of whether
   *  it lands at the root or under the TTM grouping parent. */
  function countAllNodes(n: TraceNode): number {
    const kids = n.children ?? [];
    return 1 + kids.reduce((s, c) => s + countAllNodes(c), 0);
  }

  function fmtKV(k: string, v: unknown): string {
    if (typeof v === 'number') {
      const s = Number.isInteger(v) ? `${v}` : v.toFixed(2);
      return `${k}=${s}`;
    }
    if (typeof v === 'boolean') return `${k}=${v}`;
    if (typeof v === 'string') {
      const truncated = v.length > 24 ? v.slice(0, 22) + '…' : v;
      return `${k}=${truncated}`;
    }
    return k;
  }

  let active = $state({ empirical: true, modeled: true, synthetic: true, proxy: true });

  type AddressSource = 'geocode' | 'nta';
  let address = $state<{ label: string; lat: number; lon: number; source: AddressSource } | null>(null);
  let ntaCode = $state<string | null>(null);
  let registerPointsFc = $state<FeatureCollection | undefined>(undefined);
  let registerPolygonsFc = $state<FeatureCollection | undefined>(undefined);
  let sandyFc = $state<FeatureCollection | undefined>(undefined);
  let depFc = $state<FeatureCollection | undefined>(undefined);
  let synFc = $state<FeatureCollection | undefined>(undefined);
  let proxyFc = $state<FeatureCollection | undefined>(undefined);
  let terramindLulcFc = $state<FeatureCollection | undefined>(undefined);
  // Live EO polygon layers — populated from the specialist outputs in
  // FSM `final` state when the remote inference path returns a
  // polygonised raster. None of these go through a /api/layers fetch;
  // they ride the SSE stream alongside the specialist results.
  let prithviLiveFc = $state<FeatureCollection | undefined>(undefined);
  let terramindBuildingsFc = $state<FeatureCollection | undefined>(undefined);
  let idaHwmFc = $state<FeatureCollection | undefined>(undefined);

  // Compare-intent: independent geocoded addresses per place.
  // Populated from geocode step events tagged with target_label.
  let compareAddressA = $state<{ label: string; lat: number; lon: number; source: AddressSource } | null>(null);
  let compareAddressB = $state<{ label: string; lat: number; lon: number; source: AddressSource } | null>(null);
  // Per-place step result payloads for the structured diff strip.
  let compareStepsA = $state<Record<string, unknown>>({});
  let compareStepsB = $state<Record<string, unknown>>({});
  // Per-place map layers for compare intent.
  let sandyFcA = $state<FeatureCollection | undefined>(undefined);
  let depFcA = $state<FeatureCollection | undefined>(undefined);
  let synFcA = $state<FeatureCollection | undefined>(undefined);
  let proxyFcA = $state<FeatureCollection | undefined>(undefined);
  let idaHwmFcA = $state<FeatureCollection | undefined>(undefined);
  let sandyFcB = $state<FeatureCollection | undefined>(undefined);
  let depFcB = $state<FeatureCollection | undefined>(undefined);
  let synFcB = $state<FeatureCollection | undefined>(undefined);
  let proxyFcB = $state<FeatureCollection | undefined>(undefined);
  let idaHwmFcB = $state<FeatureCollection | undefined>(undefined);

  // Per-tier feature counts for the map legend. Layers with 0 are
  // dropped from the legend display per the silence-over-confabulation
  // rule (handoff hard rule #3).
  let mapFeatureCounts = $derived({
    empirical: (sandyFc?.features.length ?? 0) + (idaHwmFc?.features.length ?? 0),
    modeled: depFc?.features.length ?? 0,
    synthetic: (synFc?.features.length ?? 0) + (terramindLulcFc?.features.length ?? 0),
    proxy: proxyFc?.features.length ?? 0
  });

  let blocks = $state<BriefingBlock[]>([]);
  let citations = $state<Record<string, Citation>>({});
  let citationOrder: string[] = [];

  function rebuildBriefing() {
    if (!markdown) {
      blocks = [];
      citations = {};
      citationOrder = [];
      return;
    }
    const seed: Record<string, Citation> = {};
    if (finalResult?.citations) {
      // Tolerate both citation shapes the reconciler may emit:
      //   - LLM tier:        Array<{ doc_id, source, ... }>
      //   - Templated tier:  Record<docId, citation>   (keyed by id)
      // Without this guard the templated path threw
      // `citations.forEach is not a function` on every no-LLM render.
      const citationsList: typeof finalResult.citations = Array.isArray(finalResult.citations)
        ? finalResult.citations
        : (Object.values(finalResult.citations) as typeof finalResult.citations);
      citationsList.forEach((c, i) => {
        const docId = c.doc_id ?? (c as unknown as { id?: string }).id ?? `c${i + 1}`;
        seed[docId] = citationFromMeta(i + 1, docId, {
          source: c.source,
          title: c.title,
          url: c.url,
          vintage: c.vintage
        });
      });
    }
    const r = parseBriefing(markdown, seed);
    // Renumber citations in their order of appearance, prefixed by any
    // pre-seeded ones so n stays stable across streaming chunks.
    const ordered: Record<string, Citation> = {};
    let n = 1;
    for (const id of citationOrder) {
      const c = r.citations[id];
      if (c) {
        ordered[id] = { ...c, n: n++ };
      }
    }
    for (const [id, c] of Object.entries(r.citations)) {
      if (!ordered[id]) {
        ordered[id] = { ...c, n: n++ };
        citationOrder.push(id);
      }
    }
    blocks = r.blocks;
    citations = ordered;
  }

  $effect(() => {
    void markdown;
    void finalResult;
    rebuildBriefing();
  });

  // When the geocode / nta_resolve step lands, populate the map.
  $effect(() => {
    if (!address) return;
    const { lat, lon, source } = address;
    if (source === 'nta' && ntaCode) {
      fetchSandyNta(ntaCode).then((fc) => (sandyFc = fc));
      fetchDepNta(ntaCode).then((fc) => (depFc = fc));
      // No NTA-scope synthetic / proxy endpoint yet — fall back to a
      // bbox-radius query around the centroid so the layers still
      // populate. Wide enough radius to cover most NTAs.
      // Tight radius for synthetic (Ida polygons): we don't want
      // Manhattan polygons rendering for a Brooklyn neighborhood. Proxy
      // dots (FloodNet) are sparser, so a wider radius is still local-
      // looking.
      fetchPrithviSynthetic(lat, lon, 2500).then((fc) => (synFc = fc));
      fetchProxyDots(lat, lon, 3000).then((fc) => (proxyFc = fc));
      fetchIdaHwm(lat, lon, 3000).then((fc) => (idaHwmFc = fc));
    } else {
      fetchSandy(lat, lon).then((fc) => (sandyFc = fc));
      fetchDep(lat, lon).then((fc) => (depFc = fc));
      fetchPrithviSynthetic(lat, lon).then((fc) => (synFc = fc));
      fetchProxyDots(lat, lon).then((fc) => (proxyFc = fc));
      fetchIdaHwm(lat, lon).then((fc) => (idaHwmFc = fc));
    }
  });

  // Compare-intent: load map layers independently for each place.
  $effect(() => {
    if (!compareAddressA) return;
    const { lat, lon } = compareAddressA;
    fetchSandy(lat, lon).then((fc) => (sandyFcA = fc));
    fetchDep(lat, lon).then((fc) => (depFcA = fc));
    fetchPrithviSynthetic(lat, lon).then((fc) => (synFcA = fc));
    fetchProxyDots(lat, lon).then((fc) => (proxyFcA = fc));
    fetchIdaHwm(lat, lon).then((fc) => (idaHwmFcA = fc));
  });
  $effect(() => {
    if (!compareAddressB) return;
    const { lat, lon } = compareAddressB;
    fetchSandy(lat, lon).then((fc) => (sandyFcB = fc));
    fetchDep(lat, lon).then((fc) => (depFcB = fc));
    fetchPrithviSynthetic(lat, lon).then((fc) => (synFcB = fc));
    fetchProxyDots(lat, lon).then((fc) => (proxyFcB = fc));
    fetchIdaHwm(lat, lon).then((fc) => (idaHwmFcB = fc));
  });

  onMount(() => {
    briefingState.reset();
    // Manifest fetch is idempotent (no-op after first call). cardAdapter
    // reads the store to render BYOD pebbles via the templated path.
    void pebbleManifest.load();
    if (!queryText()) return;
    runStartedAt = Date.now();
    // v0.4.5 — drive the AppHeader status pill from SSE events. The
    // store resets to phase=idle in briefingState.reset() above; we
    // flip phases here as the pipeline advances.
    briefingState.phase = 'planning';
    const stream = openAgentStream(queryText(), {
      onPlanToken: (d) => (planTokens += d),
      onPlan: (p) => {
        plan = p;
        briefingState.phase = 'specialists';
        briefingState.totalSpecialists = p.specialists?.length ?? 0;
      },
      onDeployment: async (d) => {
        // Per-query routing handshake — the backend has resolved the
        // deployment for this query. Pivot the header chip + reload
        // the pebble scaffold so the findings rail renders the
        // routed-to city's pebbles, not the server's boot deployment.
        // Sentinel '__none__' is presented to the UI as out-of-coverage.
        const name = d.name && d.name !== '__none__' ? d.name : null;
        await Promise.all([
          deployment.setForQuery(name),
          pebbleManifest.loadForDeployment(name),
        ]);
        deploymentResolved = true;
      },
      onStep: (s) => {
        // Drive the header status pill — show the current step name and
        // increment the fired count for any specialist that returned
        // (any non-error). Reconciler steps roll up under the
        // "reconciling" phase set by onAttemptStart / onToken below.
        const reconcileNames = new Set([
          'reconcile_granite41', 'mellea_reconcile_address',
          'reconcile_neighborhood', 'reconcile_development',
          'reconcile_live_now',
        ]);
        if (!reconcileNames.has(s.step)) {
          briefingState.activeStep = s.step;
          if (s.ok) briefingState.firedCount = briefingState.firedCount + 1;
        }

        // Mirror the step's slim result into liveResults so Findings cards
        // can stream in as specialists complete. The card adapter is
        // tolerant of partial summaries — at the end of the stream the
        // richer `final` payload merges over the top.
        applyStepEventToLiveState(liveResults, s.step, s.result, s.ok);
        liveTick = liveTick + 1;

        // address from the geocode step (single_address / live_now / compare).
        // Compare emits two geocode steps tagged target_label: "PLACE A" / "PLACE B".
        if (s.step === 'geocode') {
          if (s.ok && s.result && typeof s.result === 'object') {
            const r = s.result as Record<string, unknown>;
            if (typeof r.lat === 'number' && typeof r.lon === 'number') {
              const label = (typeof r.address === 'string' ? r.address : queryText()) as string;
              if (s.target_label === 'PLACE A') {
                compareAddressA = { label, lat: r.lat, lon: r.lon, source: 'geocode' };
              } else if (s.target_label === 'PLACE B') {
                compareAddressB = { label, lat: r.lat, lon: r.lon, source: 'geocode' };
              } else {
                address = { label, lat: r.lat, lon: r.lon, source: 'geocode' };
              }
              geocodeSucceeded = true;
            }
          } else {
            // v0.4.2 §12 — geocoder error state
            errorState = 'geocoder';
          }
        }
        // Accumulate per-place step results for the compare structured diff strip.
        if (s.target_label === 'PLACE A') {
          compareStepsA = { ...compareStepsA, [s.step]: s.result };
        } else if (s.target_label === 'PLACE B') {
          compareStepsB = { ...compareStepsB, [s.step]: s.result };
        }

        // address from the nta_resolve step (neighborhood / development_check)
        if (s.step === 'nta_resolve' && s.ok && s.result && typeof s.result === 'object') {
          const r = s.result as Record<string, unknown>;
          const bbox = Array.isArray(r.bbox) ? (r.bbox as number[]) : null;
          const code = typeof r.nta_code === 'string' ? r.nta_code : null;
          if (bbox && bbox.length === 4 && code) {
            ntaCode = code;
            const lon = (bbox[0] + bbox[2]) / 2;
            const lat = (bbox[1] + bbox[3]) / 2;
            const label = (typeof r.nta_name === 'string' ? r.nta_name : queryText()) as string;
            address = { label, lat, lon, source: 'nta' };
          }
        }

        const tier = tierForStep(s.step);
        const status: TraceNode['status'] = !s.ok ? 'error' : (s.result == null && s.err == null ? 'silent' : 'ok');
        const elapsedMs = Math.round((s.elapsed_s ?? 0) * 1000);

        // Preserve the raw structured payload — the trace UI renders it
        // on click as the auditable evidence surface. Don't truncate; the
        // panel handles overflow with max-height + scroll.
        const rawOutput: string | object | null =
          s.result != null ? s.result : (s.err ?? null);
        const note = summarizeStepNote(s.step, s.result, s.err, status);

        const nodeBase: TraceNode = {
          id: `step-${countAllNodes(traceRoot)}`,
          name: s.step,
          status,
          ms: elapsedMs,
          tier,
          note,
          output: rawOutput,
          error: status === 'error' ? (s.err ?? 'unknown error') : undefined,
          model: TTM_STEPS.has(s.step) ? 'granite-timeseries-ttm-r2' : undefined
        };

        const updatedRoot = { ...traceRoot, ms: (traceRoot.ms ?? 0) + elapsedMs };
        if (TTM_STEPS.has(s.step)) {
          // Group all TTM specialists under one synthetic parent node.
          const children = [...(updatedRoot.children ?? [])];
          let parent = children.find((n) => n.id === TTM_PARENT_ID);
          if (!parent) {
            parent = {
              id: TTM_PARENT_ID,
              name: 'forecasting.granite-timeseries-ttm-r2',
              status: 'fan',  // auto-expand + excluded from leaf counts
              ms: 0,
              tier: 'modeled',
              note: '1 instance',
              model: 'granite-timeseries-ttm-r2',
              children: []
            };
            children.push(parent);
          }
          const newParentChildren = [...(parent.children ?? []), nodeBase];
          const newParent: TraceNode = {
            ...parent,
            ms: (parent.ms ?? 0) + elapsedMs,
            note: `${newParentChildren.length} instance${newParentChildren.length === 1 ? '' : 's'}`,
            children: newParentChildren
          };
          traceRoot = {
            ...updatedRoot,
            children: children.map((c) => (c.id === TTM_PARENT_ID ? newParent : c))
          };
        } else {
          traceRoot = {
            ...updatedRoot,
            children: [...(updatedRoot.children ?? []), nodeBase]
          };
        }
      },
      onAttemptStart: (n) => {
        attempt = n;
        briefingState.phase = 'reconciling';
        briefingState.attempt = n;
        briefingState.activeStep = 'granite4.1 + mellea';
        if (n > 1) {
          // v0.4.2 §11 reroll: keep the prior draft to render dimmed
          // beneath the banner; reset the live buffer for the new attempt.
          priorDraft = markdown;
          markdown = '';
          citationOrder = [];
        }
      },
      onToken: (delta) => {
        if (!firstTokenSeen) {
          firstTokenSeen = true;
          if (attempt === 0) attempt = 1;
          // First reconcile token landed — flip phase from "reconciling"
          // (waiting on the LLM to start) to "streaming" (paragraph is
          // materialising). Lets the header swap "reconciling..." for
          // "writing briefing..." with a visible token-count or progress.
          briefingState.phase = 'streaming';
          briefingState.attempt = Math.max(1, briefingState.attempt);
        }
        markdown += delta;
      },
      onMelleaAttempt: (m) => {
        if (m.attempt > 0) {
          attempt = m.attempt;
          briefingState.attempt = m.attempt;
        }
      },
      onFinal: (f) => {
        finalResult = f;
        if (f.paragraph) markdown = f.paragraph;
        // v0.4.2 §15: extract per-asset register data from the four
        // register specialists and render as RegisterCards under the
        // citation drawer.
        registers = extractRegisters(f as unknown as Record<string, unknown>);
        // Build register-asset GeoJSON for the map. Subway entrances /
        // schools / hospitals as Points; NYCHA developments as Polygons.
        // Each feature carries the auditability properties (name,
        // doc_id, inside_sandy_2012) the click popup surfaces.
        const fr = f as unknown as Record<string, unknown>;
        registerPointsFc = buildRegisterPointsFc(fr);
        registerPolygonsFc = buildRegisterPolygonsFc(fr);
        // EO map layers — every specialist that returns a polygon
        // collection plumbs onto the map. terramind synthesis +
        // terramind LULC LoRA both contribute to the synthetic-LULC
        // overlay; LULC LoRA wins when both fire (it's the
        // fine-tuned, Sentinel-2-driven signal). Buildings LoRA gets
        // its own layer. Prithvi NYC Pluvial water mask is the
        // marquee live-EO overlay.
        const tmSyn = fr.terramind as Record<string, unknown> | null | undefined;
        const tmLulc = fr.terramind_lulc as Record<string, unknown> | null | undefined;
        const tmBld = fr.terramind_buildings as Record<string, unknown> | null | undefined;
        const pl = fr.prithvi_live as Record<string, unknown> | null | undefined;
        const lulcCandidate =
          (tmLulc?.ok && tmLulc?.polygons_geojson)
            ? (tmLulc.polygons_geojson as FeatureCollection)
            : (tmSyn?.ok && tmSyn?.polygons_geojson)
            ? (tmSyn.polygons_geojson as FeatureCollection)
            : undefined;
        if (lulcCandidate?.type === 'FeatureCollection'
            && (lulcCandidate.features?.length ?? 0) > 0) {
          terramindLulcFc = lulcCandidate;
        }
        if (tmBld?.ok && tmBld?.polygons_geojson) {
          const pg = tmBld.polygons_geojson as FeatureCollection;
          if (pg?.type === 'FeatureCollection' && (pg.features?.length ?? 0) > 0) {
            terramindBuildingsFc = pg;
          }
        }
        if (pl?.ok && pl?.polygons_geojson) {
          const pg = pl.polygons_geojson as FeatureCollection;
          if (pg?.type === 'FeatureCollection' && (pg.features?.length ?? 0) > 0) {
            prithviLiveFc = pg;
          }
        }
        // v0.4.2 §12 grounding failure: budget exhausted with failed checks.
        const mres = f.mellea;
        if (mres && mres.failed && mres.failed.length > 0
            && mres.attempts && mres.attempts >= attemptMax) {
          errorState = 'grounding';
        }
      },
      onError: (err) => {
        // Distinguish backend-down from other errors via the message text.
        const lower = err.toLowerCase();
        if (lower.includes('connection') || lower.includes('502') || lower.includes('503') ||
            lower.includes('timeout') || lower.includes('routing')) {
          errorState = 'backend';
        }
        briefingState.markError(err);
        // If the SSE failed BEFORE the `deployment` event ever fired,
        // the page is still holding the server's boot-time pebble
        // scaffold (NYC default) — which renders as "□ not invoked"
        // ghost rows for every NYC pebble under a query that may
        // not be in NYC at all. Clear the scaffold + neutralize the
        // chip so the user sees the error card without the
        // misleading NYC pebble roster underneath it.
        if (!deploymentResolved) {
          void pebbleManifest.loadForDeployment(null);
          void deployment.setForQuery(null);
        }
      },
      onDone: () => {
        streamDone = true;
        if (runStartedAt != null) {
          runWallSeconds = (Date.now() - runStartedAt) / 1000;
        }
        // v0.4.2 §12 all-silent: stream finished but no briefing emerged.
        // `!firstTokenSeen` alone over-fires in no-LLM templated mode —
        // the templated reconciler doesn't stream tokens but DOES
        // produce a paragraph in the `final` event. Treat the run as
        // successful when EITHER tokens streamed OR a non-empty
        // paragraph arrived; only "neither" is genuinely all-silent.
        const haveParagraph = !!finalResult?.paragraph?.trim();
        if (!firstTokenSeen && !haveParagraph && !errorState && geocodeSucceeded) {
          errorState = 'all-silent';
        }
        // Gate the export-PDF action: only enable when we have a real
        // briefing (≥1 block, no error). Persist a snapshot for the
        // dedicated /print/<queryId> route to hydrate from.
        if (!errorState && blocks.length > 0) {
          persistSnapshot({
            queryId,
            queryText: queryText(),
            intent: plan?.intent ?? null,
            specialists: plan?.specialists?.length ?? 0,
            blocks,
            citations,
            generatedAt: new Date().toISOString(),
            attempts: finalResult?.mellea?.n_attempts ?? attempt
          });
        }
        // Always settle the live status indicator when the stream
        // closes without an error — even in no-LLM templated mode
        // where `blocks` stays empty (no streamed tokens, paragraph
        // comes whole via FinalResult). Without this, the main pane
        // would stay stuck on "Gathering evidence (9/10)…" forever
        // after the briefing visibly says "✓ done".
        if (!errorState) {
          briefingState.markReady();
        }
      }
    });
    return () => stream.close();
  });
</script>

<section class="hero-band">
  <div class="hero-band-inner">
    <div class="app-shell-top is-desktop">
      <main id="region-briefing" class="app-region app-region-brief" aria-labelledby="brief-h1">
        <header class="region-head">
          <span class="section-label">Briefing</span>
          {#if plan}
            <span class="region-head-meta">
              intent: {plan.intent} · {plan.specialists?.length ?? 0} specialists · attempt {attempt}
              {#if streamDone} · ✓ done{/if}
            </span>
          {:else}
            <span class="region-head-meta">planning…</span>
          {/if}
        </header>
        <h1 id="brief-h1" class="brief-h1">
          Flood-exposure briefing
          <span class="brief-h1-addr">{queryText()}</span>
        </h1>

        {#if errorState}
          <!-- v0.4.2 §12 — geocoder / all-silent / grounding / backend.
               Grounding integrity is enforced by Mellea rejection
               sampling; refusal classification was considered and
               dropped. -->
          <ErrorCard state={errorState} />
        {:else}
          {#if attempt > 1}
            <RerollBanner {attempt} max={attemptMax} />
            {#if priorDraft}
              <div class="reroll-prev" aria-hidden="true">
                <p class="reroll-prev-line">{priorDraft.slice(0, 360)}…</p>
              </div>
            {/if}
          {/if}

          {#if plan?.intent === 'compare' && finalResult?.targets?.length === 2}
            <!-- Compare intent: two-column layout with delta summary row.
                 Shown only after the final event lands so the streaming path
                 (which renders PLACE A then PLACE B sequentially) stays intact. -->
            <CompareBriefing
              paragraph={finalResult.paragraph}
              {citations}
              targets={finalResult.targets}
              structuredA={compareStepsA}
              structuredB={compareStepsB}
            />
          {:else if blocks.length}
            <Briefing {blocks} {citations} streaming={false} />
            {#if !streamDone}
              <span class="streaming-caret" aria-hidden="true">▍</span>
            {/if}
          {:else if geocodeSucceeded && !firstTokenSeen}
            <!-- v0.4.2 §11 skeleton — geocode complete, awaiting tokens -->
            <SkeletonBriefing />
          {:else if !plan}
            <div class="generating-status" aria-live="polite">
              <span class="pulse"></span> Planning intent…
              {#if planTokens}
                <details class="plan-details">
                  <summary>Planner streaming ({planTokens.length} chars)</summary>
                  <pre class="plan-stream">{planTokens}</pre>
                </details>
              {/if}
            </div>
          {:else}
            <!-- Mirror StatusPill's phase logic so this stays in sync
                 with the top-right progress indicator. Without this the
                 static "Resolving address…" would persist while the
                 header already shows "gathering evidence · floodnet · 8/11". -->
            <div class="generating-status" aria-live="polite">
              <span class="pulse"></span>
              {#if briefingState.phase === 'specialists'}
                Gathering evidence{#if briefingState.totalSpecialists}
                  ({briefingState.firedCount}/{briefingState.totalSpecialists}){/if}…
              {:else if briefingState.phase === 'reconciling'}
                Reconciling…
              {:else if briefingState.phase === 'streaming'}
                Writing briefing{#if briefingState.attempt > 1}
                  (reroll {briefingState.attempt - 1}){/if}…
              {:else if briefingState.phase === 'error'}
                Error{#if briefingState.errorMessage}: {briefingState.errorMessage}{/if}
              {:else}
                Resolving address…
              {/if}
            </div>
          {/if}
        {/if}
      </main>

      <div class="app-region-side" style="grid-area: side;">
        <aside id="region-map" class="app-region app-region-map" aria-label="Map region">
          <header class="region-head">
            <span class="section-label">Map</span>
            {#if plan?.intent === 'compare'}
              <span class="region-head-meta">
                {#if compareAddressA || compareAddressB}Carto Positron · z15 · 2 locations{:else}awaiting geocode…{/if}
              </span>
            {:else if address}
              <span class="region-head-meta">
                Carto Positron · z15 · {address.lat.toFixed(4)}°N {Math.abs(address.lon).toFixed(4)}°W
              </span>
            {:else}
              <span class="region-head-meta">awaiting geocode…</span>
            {/if}
          </header>
          {#if plan?.intent === 'compare'}
            <div class="compare-map-stack">
              {#if compareAddressA}
                <div class="compare-map-place">
                  <div class="compare-map-label">A · {compareAddressA.label}</div>
                  <div style="position: relative;">
                    <RipMap
                      address={compareAddressA}
                      activeLayers={active}
                      sandyEmpirical={sandyFcA}
                      depModeled={depFcA}
                      syntheticPrior={synFcA}
                      proxy311={proxyFcA}
                      idaHwm={idaHwmFcA}
                    />
                  </div>
                </div>
              {/if}
              {#if compareAddressB}
                <div class="compare-map-place">
                  <div class="compare-map-label">B · {compareAddressB.label}</div>
                  <div style="position: relative;">
                    <RipMap
                      address={compareAddressB}
                      activeLayers={active}
                      sandyEmpirical={sandyFcB}
                      depModeled={depFcB}
                      syntheticPrior={synFcB}
                      proxy311={proxyFcB}
                      idaHwm={idaHwmFcB}
                    />
                  </div>
                </div>
              {/if}
            </div>
          {:else if address}
            <div style="position: relative; flex: 1; min-height: 0;">
              <RipMap
                {address}
                activeLayers={active}
                sandyEmpirical={sandyFc}
                depModeled={depFc}
                syntheticPrior={synFc}
                proxy311={proxyFc}
                idaHwm={idaHwmFc}
                registerPoints={registerPointsFc}
                registerPolygons={registerPolygonsFc}
                terramindLulc={terramindLulcFc}
                terramindBuildings={terramindBuildingsFc}
                prithviLive={prithviLiveFc}
                {linkedKey}
              />
              <MapLegend
                {active}
                featureCounts={mapFeatureCounts}
                onToggle={(k) => (active = { ...active, [k]: !active[k] })}
              />
            </div>
          {/if}
        </aside>

        <aside id="region-cites" class="app-region app-region-cites" aria-label="Citations">
          <CitationDrawer {citations} />
        </aside>
      </div>
    </div>

    <div class="app-shell-bottom">
      <section class="app-region app-region-findings" aria-label="Findings">
        <FindingsRegion
          data={findingsData}
          {density}
          {provenanceMode}
          {showGrammar}
          {linkedKey}
          onLink={handleFindingsLink}
          onCite={handleFindingsCite}
        />
      </section>
    </div>
  </div>
</section>

<style>
  .compare-map-stack {
    display: flex;
    flex-direction: column;
    gap: var(--s-3, 8px);
    padding-top: 4px;
  }
  .compare-map-place {
    display: flex;
    flex-direction: column;
  }
  .compare-map-label {
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ink-secondary);
    padding: 2px 0 4px;
    border-bottom: 1px solid var(--rule-soft);
    margin-bottom: 4px;
  }
  .plan-details {
    border: 1px solid var(--rule-soft);
    background: var(--paper-deep);
    margin-bottom: 16px;
  }
  .plan-details summary {
    padding: 10px 14px;
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--ink-secondary);
  }
  .plan-stream {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    white-space: pre-wrap;
    padding: 0 14px 12px;
    margin: 0;
    max-height: 240px;
    overflow: auto;
  }
  .generating-status {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 0;
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--ink-secondary);
    flex-wrap: wrap;
  }
  .pulse {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent-graphical);
    animation: pulse 1.4s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 0.3; transform: scale(0.85); }
    50% { opacity: 1; transform: scale(1.1); }
  }
  @media (prefers-reduced-motion: reduce) {
    .pulse { animation: none; opacity: 0.7; }
  }
</style>
