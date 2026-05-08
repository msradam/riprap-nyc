/**
 * Map the FSM register specialists' `final` event payload into the
 * `RegisterData` shape consumed by `evidence/RegisterCard.svelte`
 * (v0.4.2 §15).
 *
 * Each register specialist (`mta_entrances`, `nycha_developments`,
 * `doe_schools`, `doh_hospitals`) returns a Python dict like:
 *   { available: true, n_<assets>: int, radius_m: int,
 *     entrances|developments|schools|hospitals: [
 *       { station_name|development|school_name|facility_name, ... }
 *     ] }
 *
 * The shapes diverge a bit per asset class (NYCHA polygons have
 * `pct_inside_sandy_2012` percentages; subway entrances have boolean
 * `inside_sandy_2012` per entrance). We normalise each one into a
 * common row shape that matches the spec page's `SUBWAY_REGISTER`
 * worked example so the table renders consistently across asset classes.
 */
import type { AssetKind, RegisterData, RegisterRow } from '$lib/types/states';

interface BaseFinding {
  [k: string]: unknown;
}

const SOURCE_LABEL: Record<AssetKind, string> = {
  subway: 'MTA · USGS · FEMA · NYC OEM · NYC DEP',
  nycha: 'NYC HA · USGS · NYC OEM · NYC DEP',
  school: 'NYC DOE · USGS · NYC OEM · NYC DEP',
  hospital: 'NYS DOH · USGS · NYC OEM · NYC DEP'
};

const TYPE_LABEL: Record<AssetKind, string> = {
  subway: 'subway entrances',
  nycha: 'NYCHA developments',
  school: 'public schools',
  hospital: 'hospitals'
};

function metersToLabel(m: number | undefined): string {
  if (!m || !Number.isFinite(m)) return '—';
  return `${Math.round(m)}m`;
}

function feetLabel(elev_m: number | null | undefined): string {
  if (elev_m == null || !Number.isFinite(elev_m)) return '—';
  return `${(elev_m * 3.28084).toFixed(1)} ft`;
}

function inundLabel(inside: boolean | undefined, pct?: number | null | undefined): string {
  if (typeof pct === 'number') {
    if (pct >= 0.5) return `Inundated 2012 (${Math.round(pct * 100)}%)`;
    if (pct > 0) return `Edge (${Math.round(pct * 100)}%)`;
    return '—';
  }
  return inside ? 'Inundated 2012' : '—';
}

function depLabel(label: string | null | undefined, classNum?: number | null | undefined,
                  pct?: number | null | undefined): string {
  if (typeof pct === 'number') {
    if (pct >= 0.5) return `≥${Math.round(pct * 100)}% in scenario`;
    if (pct > 0) return `${Math.round(pct * 100)}% edge`;
    return 'minimal';
  }
  if (label && label.length) return label;
  if (classNum && classNum > 0) return `class ${classNum}`;
  return 'minimal';
}

function adaFromEntranceType(t: string | undefined): boolean {
  if (!t) return false;
  // Same set as ADA_ACCESSIBLE_TYPES in app/registers/mta_entrances.py.
  return /elevator|easement|stair.*ramp/i.test(t);
}

/* ── per-asset adapters ───────────────────────────────────────────────── */

function adaptSubway(s: BaseFinding): RegisterData | null {
  if (!s.available) return null;
  const list = (s.entrances ?? []) as BaseFinding[];
  const rows: RegisterRow[] = list.map((e) => {
    const ada = adaFromEntranceType(e.entrance_type as string | undefined);
    return {
      name: `${e.station_name ?? '?'}${e.daytime_routes ? ` (${String(e.daytime_routes).split(/\s+/).slice(0, 3).join('/')})` : ''}`,
      elev: feetLabel(e.elev_m as number | null | undefined),
      ada,
      fema: 'Zone X',
      sandy: inundLabel(e.inside_sandy_2012 as boolean | undefined),
      dep: depLabel(
        e.dep_extreme_2080_label as string | null | undefined,
        e.dep_extreme_2080_class as number | null | undefined
      ),
      asset: 'subway',
      primaryTier: e.inside_sandy_2012 ? 'empirical' : 'modeled'
    };
  });
  return {
    type: TYPE_LABEL.subway,
    radius: metersToLabel(s.radius_m as number | undefined),
    count: (s.n_entrances as number | undefined) ?? rows.length,
    rows,
    sourceLabel: SOURCE_LABEL.subway
  };
}

function adaptNycha(s: BaseFinding): RegisterData | null {
  if (!s.available) return null;
  const list = (s.developments ?? []) as BaseFinding[];
  const rows: RegisterRow[] = list.map((d) => {
    const inSandy = d.inside_sandy_2012 as boolean | undefined;
    const depLbl = d.dep_extreme_2080_label as string | null | undefined;
    const depCls = d.dep_extreme_2080_class as number | null | undefined;
    return {
      name: `${d.development ?? '?'}${d.borough ? ` · ${d.borough}` : ''}`,
      elev: feetLabel(d.rep_elevation_m as number | null | undefined),
      ada: false, // NYCHA developments don't carry an ADA flag
      fema: '—',
      sandy: inundLabel(inSandy),
      dep: depLabel(depLbl, depCls),
      asset: 'nycha',
      primaryTier: inSandy ? 'empirical' : 'modeled'
    };
  });
  return {
    type: TYPE_LABEL.nycha,
    radius: metersToLabel(s.radius_m as number | undefined),
    count: (s.n_developments as number | undefined) ?? rows.length,
    rows,
    sourceLabel: SOURCE_LABEL.nycha
  };
}

function adaptSchools(s: BaseFinding): RegisterData | null {
  if (!s.available) return null;
  const list = (s.schools ?? []) as BaseFinding[];
  const rows: RegisterRow[] = list.map((sc) => ({
    name: `${sc.loc_name ?? sc.school_name ?? sc.name ?? '?'}${sc.borough ? ` · ${sc.borough}` : ''}`,
    elev: feetLabel((sc.elevation_m ?? sc.elev_m) as number | null | undefined),
    ada: false,
    fema: '—',
    sandy: inundLabel(sc.inside_sandy_2012 as boolean | undefined),
    dep: depLabel(
      sc.dep_extreme_2080_label as string | null | undefined,
      sc.dep_extreme_2080_class as number | null | undefined
    ),
    asset: 'school',
    primaryTier: sc.inside_sandy_2012 ? 'empirical' : 'modeled'
  }));
  return {
    type: TYPE_LABEL.school,
    radius: metersToLabel(s.radius_m as number | undefined),
    count: (s.n_schools as number | undefined) ?? rows.length,
    rows,
    sourceLabel: SOURCE_LABEL.school
  };
}

function adaptHospitals(s: BaseFinding): RegisterData | null {
  if (!s.available) return null;
  const list = (s.hospitals ?? []) as BaseFinding[];
  const rows: RegisterRow[] = list.map((h) => ({
    name: `${h.facility_name ?? h.name ?? '?'}${h.borough ? ` · ${h.borough}` : ''}`,
    elev: feetLabel((h.elevation_m ?? h.elev_m) as number | null | undefined),
    ada: true, // hospitals are ADA-required
    fema: '—',
    sandy: inundLabel(h.inside_sandy_2012 as boolean | undefined),
    dep: depLabel(
      h.dep_extreme_2080_label as string | null | undefined,
      h.dep_extreme_2080_class as number | null | undefined
    ),
    asset: 'hospital',
    primaryTier: h.inside_sandy_2012 ? 'empirical' : 'modeled'
  }));
  return {
    type: TYPE_LABEL.hospital,
    radius: metersToLabel(s.radius_m as number | undefined),
    count: (s.n_hospitals as number | undefined) ?? rows.length,
    rows,
    sourceLabel: SOURCE_LABEL.hospital
  };
}

/**
 * Pull every available register out of the FSM `final` payload.
 * Order matches the FSM specialist sequence so trace UI and register
 * cards line up.
 */
export function extractRegisters(final: Record<string, unknown> | null): RegisterData[] {
  if (!final) return [];
  const out: RegisterData[] = [];
  const mta = adaptSubway(final.mta_entrances as BaseFinding | null ?? {});
  if (mta && mta.rows.length) out.push(mta);
  const nycha = adaptNycha(final.nycha_developments as BaseFinding | null ?? {});
  if (nycha && nycha.rows.length) out.push(nycha);
  const schools = adaptSchools(final.doe_schools as BaseFinding | null ?? {});
  if (schools && schools.rows.length) out.push(schools);
  const hospitals = adaptHospitals(final.doh_hospitals as BaseFinding | null ?? {});
  if (hospitals && hospitals.rows.length) out.push(hospitals);
  return out;
}
