/**
 * Pebble manifest store — fetches /api/pebbles once on app load and
 * caches the result for the rest of the session.
 *
 * The manifest is the single source of truth for:
 *   - stone mapping (pebble.stone)
 *   - card header chrome (provenance.source_name → source pill,
 *     provenance.last_updated → vintage, manifest.title → title,
 *     provenance.doc_id → doc-id chip, provenance.citation → cites)
 *   - map-layer hint (display.map_layer)
 *   - templated card variant for BYOD pebbles (display.kind)
 *
 * Everything in cardAdapter.ts that used to be hardcoded reads from this
 * store. Backend-defined manifests (`deployments/nyc/manifests/*.yaml`)
 * propagate to the UI with no TS edits.
 */
import type { StoneKey, CardVariant, Citation } from '$lib/types/card';

/** One stone descriptor from /api/pebbles. */
export interface PebbleStone {
  id: StoneKey;
  name: string;
  tagline: string;
  description: string;
  order: number;
}

/** One pebble descriptor from /api/pebbles. */
export interface PebbleManifest {
  id: string;
  type: 'live' | 'baked' | 'model';
  title: string;
  stone: StoneKey;
  /** Epistemic tier — drives the EMP/MOD/PRX/SYN chip on the card. */
  tier: 'empirical' | 'modeled' | 'proxy' | 'synthetic' | null;
  display: {
    order: number | null;
    kind: 'text' | 'stat' | 'list' | 'chart' | 'map_only';
    /** Finer-grained component hint within kind — cardAdapter uses this
     *  to pick which evidence-card component to render. Optional;
     *  unset falls back to a kind-derived default. */
    variant: string | null;
    map_layer: boolean;
    icon: string | null;
  };
  narration: {
    short: string | null;
    template: string | null;
  };
  provenance: {
    source_name: string;
    source_url: string | null;
    license: string | null;
    citation: string | null;
    doc_id: string | null;
    last_updated: string | null;
  };
  fallback: {
    on_offline: 'skip' | 'stub' | 'error';
    message: string | null;
  };
}

export interface PebbleManifestResponse {
  stones: PebbleStone[];
  pebbles: PebbleManifest[];
}

class PebbleManifestStore {
  /** Map keyed by pebble id, for O(1) lookup from cardAdapter. */
  byId = $state<Record<string, PebbleManifest>>({});
  /** Stones in display order — used by FindingsRegion to order rows. */
  stones = $state<PebbleStone[]>([]);
  /** Pebbles grouped by stone id, ordered by display.order. */
  byStone = $state<Record<string, PebbleManifest[]>>({});
  /** Loaded once per session. Subsequent calls are no-ops. */
  loaded = $state(false);
  /** Last fetch error — exposed for any debug surface that wants it. */
  error = $state<string | null>(null);

  /** Which deployment is currently loaded — `null` means the server's
   *  boot-time deployment (back-compat). Set by loadForDeployment().
   *  Used to short-circuit re-fetch when re-navigating to a query in
   *  the same city. */
  loadedFor = $state<string | null>(null);
  /** True once loadForDeployment() has been called for this query.
   *  Prevents a slow boot-time load() from overwriting the per-query
   *  manifest if the two fetches race. */
  private lockedForQuery = false;

  async load(): Promise<void> {
    if (this.loaded || this.lockedForQuery) return;
    await this._fetchInto(null);
  }

  /** Re-fetch the manifest scoped to the deployment that was actually
   *  routed-to for the current query (boston, chicago, …) instead of
   *  the server's boot-time deployment. Called from /q/[queryId] when
   *  the SSE stream emits the `deployment` event. No-op when the same
   *  deployment is already loaded.
   *
   *  When `name` is null (out-of-coverage) we explicitly CLEAR the
   *  scaffold instead of falling through to the boot manifest — a
   *  null name signals "no shipped deployment covers this query",
   *  and rendering NYC's scaffold under that chip is the very leak
   *  this routing was supposed to fix. */
  async loadForDeployment(name: string | null): Promise<void> {
    this.lockedForQuery = true;  // claim ownership against load() races
    if (name === null) {
      // Out-of-coverage: clear EVERYTHING, including stones[]. Keeping
      // stale stones[] left behind the previous deployment's Stone
      // descriptions ("Reads what NYC's ground remembers about
      // flooding") under an Albuquerque chip — caught by the
      // pages.spec.ts no-leak assertion. Cleared scaffold = MapLegend /
      // StoneRegion fall back to the city-agnostic STONE_META.tag.
      this.byId = {};
      this.stones = [];
      this.byStone = {};
      this.loaded = true;
      this.loadedFor = null;
      this.error = null;
      return;
    }
    if (this.loadedFor === name && this.loaded) return;
    await this._fetchInto(name);
  }

  /** Internal: fetch /api/pebbles with optional ?deployment=<name> and
   *  overwrite the store. Keeps load semantics in one place.
   *
   *  Re-checks `lockedForQuery` after the await so a boot-time fetch
   *  that was in flight when loadForDeployment() landed can't clobber
   *  the per-query manifest with the boot one. The race is real and
   *  the page integration test would otherwise see NYC ghost pebbles
   *  rendered for a Boston query. */
  private async _fetchInto(name: string | null): Promise<void> {
    // Snapshot whether this is the per-query call vs the boot call.
    // If lockedForQuery is true and name is null, this is the racing
    // boot call from load() that fired before the lock was set — skip.
    if (name === null && this.lockedForQuery) return;
    const url = name
      ? '/api/pebbles?deployment=' + encodeURIComponent(name)
      : '/api/pebbles';
    try {
      const r = await fetch(url);
      // Re-check the lock after the await — loadForDeployment may
      // have landed during the network round-trip.
      if (name === null && this.lockedForQuery) return;
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data: PebbleManifestResponse = await r.json();
      // And re-check once more after the body read for the same reason.
      if (name === null && this.lockedForQuery) return;
      const byId: Record<string, PebbleManifest> = {};
      const byStone: Record<string, PebbleManifest[]> = {};
      for (const p of data.pebbles) {
        byId[p.id] = p;
        (byStone[p.stone] ||= []).push(p);
      }
      this.byId = byId;
      this.stones = [...data.stones].sort((a, b) => a.order - b.order);
      this.byStone = byStone;
      this.loaded = true;
      this.loadedFor = name;
      this.error = null;
    } catch (e) {
      this.error = String(e);
      // Leave partial state alone — stale > broken.
    }
  }

  /** Lookup with fallback to undefined for unknown ids. */
  get(pebbleId: string): PebbleManifest | undefined {
    return this.byId[pebbleId];
  }

  /** Citations[] suitable for Card.cites built from manifest provenance. */
  citationsFor(pebbleId: string): Citation[] {
    const m = this.byId[pebbleId];
    if (!m || !m.provenance.doc_id) return [];
    return [{
      id: m.provenance.doc_id,
      label: m.provenance.source_name,
      href: m.provenance.source_url ?? undefined,
    }];
  }
}

export const pebbleManifest = new PebbleManifestStore();
