/**
 * Stone specialist registry — the auditability contract.
 *
 * Each Stone declares the **complete inventory** of specialists it
 * could fire on a query, along with the FSM step name (used to join
 * against the run trace) and a one-line skip reason for when a
 * specialist is absent from a particular run.
 *
 * v0.4.5 §3: every Stone's expander shows the full intended roster,
 * never a filtered subset. A reader who expands a Stone sees what
 * could have happened *and* what did. Specialists missing from the
 * run output render as `not_invoked` with their registered skip
 * reason.
 *
 * The display name and FSM step name often differ (the trace emits
 * `mta_entrance_exposure`, the FSM action is `step_mta_entrances`,
 * the Findings adapter writes state key `mta_entrances`). The
 * `stepNames` list maps the registry entry to all variants the
 * trace might emit so we don't double-count or miss matches.
 */
import type { StoneKey, StoneMember } from '$lib/types/card';

export type RegistryEntry = {
  /** Stable id used when projecting a not_invoked row into the trace. */
  id: string;
  /** Display name in the provenance row (italic-serif). */
  name: string;
  /** All FSM step names that count as a "fire" for this entry. */
  stepNames: string[];
  /** Default tier when known; not_invoked rows render this color. */
  tier?: StoneMember['tier'];
  /** One-line message rendered when the specialist is not_invoked.
   *  Engineering-honest voice (V0.4.5_SPEC.md §1) — describe the
   *  precondition that wasn't met, not "no data found". */
  skipReason?: string;
};

export const STONE_REGISTRY: Record<StoneKey, RegistryEntry[]> = {
  cornerstone: [
    {
      id: 'CORN-001',
      name: 'sandy_inundation.lookup',
      stepNames: ['sandy', 'sandy_inundation', 'sandy_nta'],
      tier: 'empirical',
      skipReason: 'Sandy 2012 inundation: query outside NYC bounds',
    },
    {
      id: 'CORN-002',
      name: 'dep_stormwater.lookup',
      stepNames: ['dep', 'dep_stormwater', 'dep_extreme_2080_nta', 'dep_moderate_2050_nta', 'dep_moderate_current_nta'],
      tier: 'modeled',
      skipReason: 'NYC DEP stormwater scenarios: query outside NYC bounds',
    },
    {
      id: 'CORN-003',
      name: 'usgs_hwm.spatial_join',
      stepNames: ['ida_hwm', 'ida_hwm_2021'],
      tier: 'empirical',
      skipReason: 'USGS Ida HWMs: no marks within 800 m of address',
    },
    {
      id: 'CORN-004',
      name: 'prithvi_water.lookup',
      stepNames: ['prithvi', 'prithvi_eo_v2'],
      tier: 'modeled',
      skipReason: 'Prithvi-EO Ida polygons: no polygons within 500 m',
    },
    {
      id: 'CORN-005',
      name: 'microtopo.dem_hand_twi',
      stepNames: ['microtopo', 'microtopo_lidar', 'microtopo_nta'],
      tier: 'proxy',
      skipReason: 'USGS 3DEP DEM: query outside NYC raster coverage',
    },
  ],
  keystone: [
    {
      id: 'KEY-001',
      name: 'mta_entrance_exposure',
      stepNames: ['mta_entrances', 'mta_entrance_exposure'],
      tier: 'empirical',
      skipReason: 'no entrances within radius',
    },
    {
      id: 'KEY-002',
      name: 'nycha.development_join',
      stepNames: ['nycha', 'nycha_development_exposure'],
      tier: 'empirical',
      skipReason: 'no NYCHA developments within 1.0 mi',
    },
    {
      id: 'KEY-003',
      name: 'doe.school_join',
      stepNames: ['doe_schools', 'doe_school_exposure'],
      tier: 'empirical',
      skipReason: 'no DOE schools within 1.0 mi',
    },
    {
      id: 'KEY-004',
      name: 'doh.facility_join',
      stepNames: ['doh_hospitals', 'doh_hospital_exposure'],
      tier: 'empirical',
      skipReason: 'no acute-care hospitals within 1.0 mi',
    },
    {
      id: 'KEY-005',
      name: 'pluto.lot_lookup',
      stepNames: ['pluto_lookup'],
      tier: 'empirical',
      skipReason: 'PLUTO join skipped: queried address not in NYC PLUTO dataset',
    },
    {
      id: 'KEY-006',
      name: 'terramind.buildings',
      stepNames: ['terramind_buildings', 'terramind_synthesis'],
      tier: 'modeled',
      skipReason: 'TerraMind Buildings: no eo_chip available for this address (recent <30% cloud Sentinel-2 missing) or no high-confidence prediction',
    },
  ],
  touchstone: [
    {
      id: 'TCH-001',
      name: 'floodnet.history',
      stepNames: ['floodnet'],
      tier: 'empirical',
      skipReason: 'FloodNet sensor: no deployments within 600 m',
    },
    {
      id: 'TCH-002',
      name: 'nyc311.flood_complaints',
      stepNames: ['nyc311', 'nyc311_nta'],
      tier: 'proxy',
      skipReason: 'NYC 311: no flood-relevant complaints within 200 m',
    },
    {
      id: 'TCH-003',
      name: 'nws_obs.metar',
      stepNames: ['nws_obs'],
      tier: 'empirical',
      skipReason: 'NWS hourly METAR: nearest ASOS reports no precipitation',
    },
    {
      id: 'TCH-004',
      name: 'noaa_coops.recent',
      stepNames: ['noaa_tides'],
      tier: 'empirical',
      skipReason: 'NOAA tide gauge: nearest station >25 km from address',
    },
    {
      id: 'TCH-005',
      name: 'prithvi_nyc_pluvial',
      stepNames: ['prithvi_live', 'prithvi_eo_live'],
      tier: 'modeled',
      skipReason: 'Prithvi-NYC-Pluvial: no <30% cloud Sentinel-2 chip available in the last 120 d for this address',
    },
    {
      id: 'TCH-006',
      name: 'terramind.lulc',
      stepNames: ['terramind_lulc'],
      tier: 'synthetic',
      skipReason: 'TerraMind LULC: eo_chip fetch returned no Sentinel-2 tile for this address',
    },
  ],
  lodestone: [
    {
      id: 'LOD-001',
      name: 'nws_alerts.flood_relevant',
      stepNames: ['nws_alerts'],
      tier: 'modeled',
      skipReason: 'NWS public alerts: no active flood-relevant alerts at this address',
    },
    {
      id: 'LOD-002',
      name: 'ttm_battery_surge.zero_shot',
      stepNames: ['ttm_forecast'],
      tier: 'modeled',
      skipReason: 'Granite TTM r2 zero-shot: forecast not interesting (peak |residual| < 0.3 ft)',
    },
    {
      id: 'LOD-003',
      name: 'ttm_battery_surge.fine_tune',
      stepNames: ['ttm_battery_surge'],
      tier: 'modeled',
      skipReason: 'Granite TTM Battery fine-tune: forecast not interesting (peak |residual| < 0.3 m)',
    },
    {
      id: 'LOD-004',
      name: 'ttm_311_forecast',
      stepNames: ['ttm_311_forecast'],
      tier: 'modeled',
      skipReason: 'NYC 311 weekly forecast: no per-address history to extrapolate',
    },
    {
      id: 'LOD-005',
      name: 'floodnet_forecast',
      stepNames: ['floodnet_forecast'],
      tier: 'modeled',
      skipReason: 'FloodNet sensor recurrence: sensor has < silent-floor historical events; forecast omitted',
    },
    {
      id: 'LOD-006',
      name: 'npcc4.slr_projection',
      stepNames: ['npcc4_projection'],
      tier: 'modeled',
      skipReason: 'NPCC4 SLR projection: harbor-wide static reference — see Battery tide gauge in Touchstone',
    },
  ],
  capstone: [
    {
      id: 'CAP-001',
      name: 'rag.granite_embedding',
      stepNames: ['rag_granite_embedding'],
      tier: 'proxy',
      skipReason: 'Granite Embedding RAG: no policy retrieval (out-of-NYC scope)',
    },
    {
      id: 'CAP-002',
      name: 'gliner.typed_extraction',
      stepNames: ['gliner_extract'],
      tier: 'proxy',
      skipReason: 'GLiNER typed extraction: no RAG hits to extract over',
    },
    {
      id: 'CAP-003',
      name: 'granite41.compose_briefing',
      stepNames: ['reconcile_granite41', 'mellea_reconcile_address', 'reconcile_neighborhood', 'reconcile_development', 'reconcile_live_now'],
      tier: 'modeled',
      skipReason: 'Reconciler did not run (no grounded data available)',
    },
    {
      id: 'CAP-004',
      name: 'mellea.grounding_check',
      stepNames: ['mellea_grounding'],
      tier: 'modeled',
      skipReason: 'Mellea grounding-check: rolled into reconcile step on this run',
    },
  ],
};

/** Project the registry against the run's actual specialist members.
 *  Emits a full-roster member list per Stone — present specialists keep
 *  their live status; absent ones land as `not_invoked` with their
 *  registered skip reason. */
export function fillRosterForStone(
  stone: StoneKey,
  liveMembers: StoneMember[],
): StoneMember[] {
  const registry = STONE_REGISTRY[stone] ?? [];
  // Index live members by every step name they could match.
  const liveByStep = new Map<string, StoneMember>();
  for (const m of liveMembers) {
    liveByStep.set(m.name, m);
  }

  const out: StoneMember[] = [];
  const used = new Set<string>();

  for (const entry of registry) {
    let live: StoneMember | undefined;
    for (const sn of entry.stepNames) {
      const hit = liveByStep.get(sn);
      if (hit) {
        live = hit;
        used.add(sn);
        break;
      }
    }
    if (live) {
      out.push({
        ...live,
        // Override id + name with the registry's display strings so the
        // provenance row reads consistently regardless of trace munging.
        id: entry.id,
        name: entry.name,
        tier: live.tier ?? entry.tier ?? null,
      });
    } else {
      out.push({
        id: entry.id,
        name: entry.name,
        status: 'not_invoked',
        tier: entry.tier ?? null,
        note: entry.skipReason,
      });
    }
  }

  // Append any live members that weren't in the registry — they were
  // emitted by the FSM but we don't know about them. Surface them
  // anyway so we don't silently drop trace rows.
  for (const m of liveMembers) {
    if (!used.has(m.name)) out.push(m);
  }

  return out;
}
