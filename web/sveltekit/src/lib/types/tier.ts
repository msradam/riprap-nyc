export type Tier = 'empirical' | 'modeled' | 'proxy' | 'synthetic';

export const TIER_META: Record<Tier, {
  label: string;
  short: string;
  desc: string;
  examples: string;
}> = {
  empirical: {
    label: 'Empirical',
    short: 'EMP',
    desc: 'Directly measured or observed',
    examples: 'USGS high-water marks · FloodNet sensors · Sandy Inundation Zone'
  },
  modeled: {
    label: 'Modeled',
    short: 'MOD',
    desc: 'Scenario-based prediction',
    examples: 'FEMA flood zones · DEP stormwater scenarios · NPCC4 SLR'
  },
  proxy: {
    label: 'Proxy',
    short: 'PRX',
    desc: 'Indirect indicator',
    examples: '311 flood complaints · NFIP claims · terrain indices'
  },
  synthetic: {
    label: 'Synthetic prior',
    short: 'SYN',
    desc: 'Generated, not observed',
    examples: 'TerraMind land-cover · synthetic SAR for occluded days'
  }
};

/**
 * Map a Riprap doc_id (e.g. "mta_entrance_56", "nycha_dev_239", "rag_mta",
 * "dep_extreme", "sandy", "syn_sar_20250914") to its epistemic tier.
 *
 * Empirical = direct measurement. Modeled = scenario predictions.
 * Proxy = indirect indicator. Synthetic = generated/not observed.
 */
export function tierForDocId(docId: string): Tier {
  const id = docId.toLowerCase();
  if (id.startsWith('syn') || id.startsWith('terramind') || id.includes('synthetic')) return 'synthetic';
  if (id.startsWith('sandy') || id.startsWith('floodnet') || id.startsWith('usgs') ||
      id.startsWith('mta_entrance') || id.startsWith('nycha_dev') ||
      id.startsWith('doe_school') || id.startsWith('doh_hospital') ||
      id.startsWith('ida_hwm') || id.startsWith('hwm') || id.startsWith('noaa') ||
      id.startsWith('nws_obs') || id.startsWith('prithvi_eo')) return 'empirical';
  if (id.startsWith('dep') || id.startsWith('fema_firm') || id.startsWith('npcc') ||
      id.startsWith('wrp') || id.includes('scenario') || id.includes('forecast') ||
      id.startsWith('prithvi') || id.startsWith('ttm') || id.startsWith('nws_alert')) return 'modeled';
  if (id.startsWith('nyc311') || id.startsWith('311') || id.startsWith('nfip') ||
      id.startsWith('rag') || id.startsWith('dob') || id.startsWith('hand') ||
      id.startsWith('twi') || id.startsWith('microtopo')) return 'proxy';
  return 'proxy';
}

/**
 * Map an FSM step name (`step_*` action without the prefix) to the tier
 * its output represents. Drives the trace-row tier badge and the run-trace
 * summary. Steps that produce no claims (geocode, fan_out, merge) return null.
 */
export function tierForStep(step: string): Tier | null {
  const s = step.toLowerCase();
  if (s === 'geocode' || s.startsWith('fan') || s.startsWith('merge') ||
      s === 'plan' || s === 'compose' || s === 'reconcile' || s === 'stream') return null;
  if (s === 'sandy' || s === 'sandy_inundation' || s === 'floodnet' ||
      s === 'ida_hwm' || s === 'noaa_tides' || s === 'nws_obs' ||
      s === 'prithvi_eo_v2' || s === 'prithvi_eo_live' ||
      s === 'mta_entrance_exposure' || s === 'mta_entrances' ||
      s === 'nycha_developments' || s === 'doe_school_exposure' ||
      s === 'doe_schools' || s === 'doh_hospital_exposure' || s === 'doh_hospitals') return 'empirical';
  if (s === 'dep' || s === 'dep_stormwater' || s === 'ttm_forecast' ||
      s === 'ttm_311_forecast' || s === 'floodnet_forecast' ||
      s === 'nws_alerts' || s === 'prithvi_water') return 'modeled';
  if (s === 'nyc311' || s === 'microtopo' || s === 'microtopo_lidar' ||
      s === 'rag' || s === 'rag_mta') return 'proxy';
  if (s === 'terramind' || s === 'terramind_synthesis') return 'synthetic';
  return null;
}
