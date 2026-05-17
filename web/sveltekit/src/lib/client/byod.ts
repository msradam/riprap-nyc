/**
 * Browser-side BYOD file ingest + adapter detection.
 *
 * Privacy posture: files stay on the user's machine.
 * No server upload. PapaParse for CSV, native fetch's JSON parser
 * for .json / .geojson, js-yaml for .yaml / .yml. Adapter auto-detect
 * looks at filename extension first, then sniffs the first ~100 rows
 * (or top-level object shape for non-CSV) to confirm the choice.
 *
 * Once parsed and detected, we generate a pebble manifest equivalent
 * to what `examples/byod/fdny_firehouses.yaml` looks like, ready to
 * persist in IndexedDB and merge with the deployment registry at
 * briefing time (server-merge is a separate concern).
 */

import Papa from 'papaparse';
import * as YAML from 'js-yaml';

export type AdapterKind =
  | 'socrata_records'    // CSV / JSON records with lat+lon columns
  | 'geojson_polygons'   // GeoJSON FeatureCollection
  | 'csv_records'        // CSV without lat+lon (no spatial join)
  | 'yaml_manifest';     // user-supplied manifest yaml (passes through)

export interface ParsedFile {
  filename: string;
  size: number;
  /** Adapter our detector picked. User can override. */
  detected: AdapterKind;
  /** Confidence string explaining why. */
  reason: string;
  /** First ~5 rows for the preview table. Empty for yaml_manifest. */
  preview: Record<string, unknown>[];
  /** Detected lat / lon column names for socrata_records, or null. */
  latField?: string | null;
  lonField?: string | null;
  /** Approximate row / feature count. */
  rowCount: number;
  /** Raw parsed payload — preserved for manifest generation. */
  raw: unknown;
}

const LAT_PATTERNS = /^(lat|latitude|y|y_value)$/i;
const LON_PATTERNS = /^(lon|long|lng|longitude|x|x_value)$/i;

function pickLatLon(headers: string[]): { lat: string | null; lon: string | null } {
  return {
    lat: headers.find((h) => LAT_PATTERNS.test(h)) ?? null,
    lon: headers.find((h) => LON_PATTERNS.test(h)) ?? null,
  };
}

async function readText(file: File): Promise<string> {
  return await file.text();
}

async function parseCsv(file: File): Promise<ParsedFile> {
  const text = await readText(file);
  // PapaParse handles all the edge cases (quoted commas, BOM, blank
  // trailing rows, etc.). 100-row sniff cap keeps it cheap.
  const result = Papa.parse<Record<string, unknown>>(text, {
    header: true,
    dynamicTyping: false, // keep everything as strings; downstream coerces
    skipEmptyLines: true,
    preview: 100,
  });
  const headers = result.meta.fields ?? [];
  const rows = result.data;
  const { lat, lon } = pickLatLon(headers);

  // Re-parse the FULL file for the row count (preview capped at 100).
  const fullCount = text.split('\n').filter((l) => l.trim()).length - 1;

  let detected: AdapterKind;
  let reason: string;
  if (lat && lon) {
    detected = 'socrata_records';
    reason = `Detected lat (${lat}) + lon (${lon}) columns`;
  } else {
    detected = 'csv_records';
    reason = `No lat / lon columns detected — non-spatial CSV`;
  }
  return {
    filename: file.name,
    size: file.size,
    detected,
    reason,
    preview: rows.slice(0, 5),
    latField: lat,
    lonField: lon,
    rowCount: Math.max(fullCount, rows.length),
    raw: { headers, rows: rows.slice(0, 100) },
  };
}

async function parseGeoJsonOrJson(file: File): Promise<ParsedFile> {
  const text = await readText(file);
  const data = JSON.parse(text);

  if (data && typeof data === 'object' && data.type === 'FeatureCollection' &&
      Array.isArray(data.features)) {
    const features = data.features as Array<{ geometry?: { type?: string }; properties?: Record<string, unknown> }>;
    const sample = features.slice(0, 5).map((f) => f.properties ?? {});
    const polygonish = features.some((f) =>
      f.geometry && /Polygon/i.test(f.geometry.type ?? ''),
    );
    return {
      filename: file.name,
      size: file.size,
      detected: 'geojson_polygons',
      reason: polygonish
        ? `FeatureCollection with ${features.length} features, contains polygons`
        : `FeatureCollection with ${features.length} features`,
      preview: sample,
      rowCount: features.length,
      raw: data,
    };
  }

  // Plain JSON array-of-records — treat as a records list (Socrata-style)
  if (Array.isArray(data)) {
    const first = data[0] ?? {};
    const keys = Object.keys(first);
    const { lat, lon } = pickLatLon(keys);
    return {
      filename: file.name,
      size: file.size,
      detected: lat && lon ? 'socrata_records' : 'csv_records',
      reason: lat && lon
        ? `JSON records with lat (${lat}) + lon (${lon})`
        : `JSON records, no lat / lon detected`,
      preview: data.slice(0, 5),
      latField: lat,
      lonField: lon,
      rowCount: data.length,
      raw: { rows: data.slice(0, 100) },
    };
  }

  // Other JSON shapes — treat as yaml_manifest fallthrough (single object)
  return {
    filename: file.name,
    size: file.size,
    detected: 'yaml_manifest',
    reason: 'JSON object — treating as inline manifest',
    preview: [],
    rowCount: 0,
    raw: data,
  };
}

async function parseYaml(file: File): Promise<ParsedFile> {
  const text = await readText(file);
  const data = YAML.load(text);
  // If it looks like a Riprap pebble manifest (has id + adapter), it IS one
  const isManifest = data && typeof data === 'object'
    && 'id' in (data as object)
    && 'adapter' in (data as object);
  return {
    filename: file.name,
    size: file.size,
    detected: 'yaml_manifest',
    reason: isManifest
      ? `Looks like a Riprap pebble manifest (declares id + adapter)`
      : `YAML document — treated as user-supplied manifest`,
    preview: [],
    rowCount: 0,
    raw: data,
  };
}

/** Top-level dispatch — picks parser by file extension. */
export async function parseFile(file: File): Promise<ParsedFile> {
  const name = file.name.toLowerCase();
  if (name.endsWith('.csv')) return parseCsv(file);
  if (name.endsWith('.geojson') || name.endsWith('.json')) return parseGeoJsonOrJson(file);
  if (name.endsWith('.yaml') || name.endsWith('.yml')) return parseYaml(file);
  throw new Error(`Unsupported file type: ${file.name}. Use .csv, .json, .geojson, .yaml, or .yml.`);
}

// ---- manifest generation ----------------------------------------------------

export type StoneKey = 'cornerstone' | 'keystone' | 'touchstone' | 'lodestone' | 'capstone';
export type Tier = 'empirical' | 'modeled' | 'proxy' | 'synthetic';

export interface PebbleMapping {
  pebbleName: string;            // becomes the manifest's `id` (snake_case)
  title: string;                 // human-readable card title
  stone: StoneKey;
  tier: Tier;
  /** For socrata_records / csv_records — used as the within-circle radius. */
  radiusM?: number;
  /** For yaml_manifest — the user's manifest is the source of truth. */
  raw?: unknown;
}

/** Generate a Riprap-style pebble manifest object from parsed + mapped input. */
export function generateManifest(parsed: ParsedFile, mapping: PebbleMapping): Record<string, unknown> {
  if (parsed.detected === 'yaml_manifest') {
    // The user's manifest IS the manifest — pass through after asserting
    // basic shape.
    if (parsed.raw && typeof parsed.raw === 'object' && 'id' in (parsed.raw as object)) {
      return parsed.raw as Record<string, unknown>;
    }
    // Otherwise fall through to template-driven generation.
  }

  const base: Record<string, unknown> = {
    id: mapping.pebbleName,
    type: 'baked',
    title: mapping.title,
    stone: mapping.stone,
    tier: mapping.tier,
    spatial: { scope: 'point', crs: 'EPSG:4326' },
    provenance: {
      source_name: `User-supplied · ${parsed.filename}`,
      license: 'User-provided',
      doc_id: mapping.pebbleName,
      citation: `BYOD pebble: ${parsed.filename} (${parsed.rowCount.toLocaleString()} records)`,
    },
    narration: {
      short: `${mapping.title} (user-supplied via BYOD).`,
    },
    fallback: { on_offline: 'skip' },
    display: { variant: 'list', order: 100 },
  };

  if (parsed.detected === 'socrata_records') {
    base.adapter = 'csv_points';
    base.config = {
      path: parsed.filename, // resolves relative to .riprap/ when persisted
      lat_col: parsed.latField,
      lon_col: parsed.lonField,
      query: { type: 'radius_point', radius_m: mapping.radiusM ?? 800 },
      feature_cap: 25,
    };
  } else if (parsed.detected === 'geojson_polygons') {
    base.adapter = 'baked_vector';
    base.config = {
      path: parsed.filename,
      query: { type: 'point_in_polygon' },
    };
  } else {
    // csv_records — no spatial join possible; we still emit a manifest
    // but the spatial scope changes to 'global'.
    base.adapter = 'csv_points';
    base.spatial = { scope: 'point', crs: 'EPSG:4326' };
    base.config = {
      path: parsed.filename,
      query: { type: 'radius_point', radius_m: mapping.radiusM ?? 800 },
    };
  }

  return base;
}
