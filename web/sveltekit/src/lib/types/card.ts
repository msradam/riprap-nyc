/**
 * Findings card schema — v0.4.4.
 *
 * The Findings region renders a stack of cards grouped by Stone. Each card
 * is one specialist's structured output, with explicit epistemic tiering
 * and a citation fan-out that ties back into the briefing prose.
 *
 * Schema mirrors `docs/design_handoff/design_files/findings.jsx` exactly.
 * Body fields are variant-specific — only the fields a given variant
 * needs are populated. The renderer dispatches on `variant`.
 */
import type { Tier } from './tier';

/** Stone keys, fixed order. Mirrors `app/stones/__init__.py`. */
export type StoneKey =
  | 'cornerstone'
  | 'keystone'
  | 'touchstone'
  | 'lodestone'
  | 'capstone';

export const STONE_ORDER: StoneKey[] = [
  'cornerstone', 'keystone', 'touchstone', 'lodestone', 'capstone',
];

export type StoneMeta = { name: string; role: string; tag: string };

export const STONE_META: Record<StoneKey, StoneMeta> = {
  cornerstone: { name: 'Cornerstone', role: 'the hazard reader',  tag: "what NYC's ground remembers" },
  keystone:    { name: 'Keystone',    role: 'the asset register', tag: "what's exposed" },
  touchstone:  { name: 'Touchstone',  role: 'the live observer',  tag: "what's happening now" },
  lodestone:   { name: 'Lodestone',   role: 'the projector',      tag: "what's coming" },
  capstone:    { name: 'Capstone',    role: 'the synthesizer',    tag: 'writes it all down with citations' },
};

/** 12 card body variants — one renderer per shape. */
export type CardVariant =
  | 'headline'
  | 'tabular'
  | 'scalars'
  | 'spark'
  | 'histogram'
  | 'timeseries'
  | 'forecast'
  | 'raster'
  | 'raster-pred'
  | 'register'
  | 'comparison'
  | 'meta';

export type Citation = { id: string; label: string; href?: string };

export type RegisterRow = {
  reg: string;        // "MTA" | "NYCHA" | "DOE" | "DOH" | "PLUTO" | ...
  tier: Tier;
  /** When `label` is null the row renders as a silent — register fired but
      had no hits. The note carries the silent reason. */
  label: string | null;
  detail: string | null;
  sourceId: string | null;
  vintage?: string | null;
  note?: string | null;
};

export type ScalarCell = { value: string; label: string; unit?: string };

export type ForecastBand = {
  year: number;
  low: number;
  mid: number;
  high: number;
};

export type ComparisonSide = {
  tier: Tier;
  label: string;
  value: string;
  aux?: string;
};

export type MetaRow = { k: string; v: string };

export type RasterKind =
  | 'stormwater'
  | 'stormwater-dry'
  | 'fema-ae'
  | 'hwm'
  | 'prithvi'
  | 'lulc'
  | 'buildings'
  | 'floodnet-density';

/** A single Findings card. Most fields are variant-specific. */
export type Card = {
  /** Stable id used as Svelte key + linkedKey target. */
  id: string;
  stone: StoneKey;
  tier: Tier;
  variant: CardVariant;

  /** Header chrome — always shown. */
  source: string;       // short label, e.g. "FEMA"
  agency: string;       // long form, e.g. "Federal Emergency Management Agency"
  vintage: string;      // e.g. "2024-09" or "2024-Q3"

  /** Title row. */
  title: string;

  /** Footer chrome — always shown. */
  docId: string;
  citeId?: string | null;
  cites?: Citation[];

  /** Map cross-link key. Hovering this card lights up the matching map
   *  layer; hovering the layer outlines this card. */
  mapLayer?: string | null;

  /** Marks the card visually as illustrative (dashed top-rule on synthetic
   *  / preview cards). Always implied true for tier=synthetic. */
  illustrative?: boolean;

  /** Optional spatial-index callout (e.g. "regional · The Battery, not
   *  point-of-query") rendered next to the body sub. */
  spatialNote?: string;

  /** Variant-specific body fields. Only the relevant ones are populated. */
  headline?: string;
  subhead?: string;
  body?: string;
  sub?: string;
  sparkSub?: string;

  // tabular
  columns?: string[];
  rows?: (string | number)[][];

  // scalars
  scalars?: ScalarCell[];

  // spark / histogram
  spark?: number[];
  histogram?: number[];

  // timeseries
  timeseries?: {
    hours: number;
    peak: { x: number; y: number };
    peakLabel: string;
  };

  // forecast
  forecast?: ForecastBand[];

  // raster / raster-pred
  rasterKind?: RasterKind;

  // register
  registers?: RegisterRow[];

  // comparison (always synthetic-tier)
  left?: ComparisonSide;
  right?: ComparisonSide;
  delta?: string;

  // meta
  metaRows?: MetaRow[];
};

/** Per-Stone provenance member (specialist) summary used by the trace. */
export type StoneMember = {
  id: string;
  name: string;
  status: 'ok' | 'warn' | 'error' | 'silent';
  tier?: Tier | null;
  ms?: number;
  note?: string;
  children?: StoneMember[];
};

/** A Stone's provenance + counts, fed by the FSM trace. */
export type StoneTrace = {
  key: StoneKey;
  members: StoneMember[];
};

/** What the page loader hands the FindingsRegion. */
export type FindingsData = {
  cards: Card[];
  stones: StoneTrace[];
  /** Wall-clock seconds for the run; surfaced in RunHealthStrip. */
  wallSeconds?: number;
  /** Optional cache-hit ratio, dev-mode surfaced. */
  cacheHit?: number;
};

/** Density toggle — affects card padding + register row height. */
export type Density = 'comfortable' | 'compact';

/** Provenance-trace expansion mode. Smart = collapsed if all-ok, expanded
 *  if any specialist warned / errored / went silent. */
export type ProvenanceMode = 'smart' | 'all-expanded' | 'all-collapsed';
