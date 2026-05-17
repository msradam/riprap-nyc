/**
 * BYOD pebble registry — persistent across browser tabs / reloads,
 * scoped to this browser's IndexedDB instance.
 *
 * Privacy posture: files stay on the user's machine. We store
 * (a) the generated manifest object and (b) the parsed payload (CSV
 * rows / GeoJSON features) so a briefing run can merge them with the
 * server-side deployment registry. Cross-session sharing is
 * explicitly out of scope for v0.5.
 *
 * Storage shape — one record per pebble id:
 *   { id, manifest: <pebble manifest>, raw: <parsed payload>, addedAt }
 *
 * idb-keyval keeps the DB schema invisible; one keyval store per app.
 */

import { get, set, del, keys } from 'idb-keyval';

export interface ByodEntry {
  id: string;                     // pebble id (snake_case)
  manifest: Record<string, unknown>;
  raw: unknown;
  addedAt: string;                // ISO timestamp
}

const KEY_PREFIX = 'riprap:byod:';

class ByodRegistry {
  entries = $state<ByodEntry[]>([]);
  loaded = $state(false);
  error = $state<string | null>(null);

  async load(): Promise<void> {
    if (this.loaded) return;
    try {
      const allKeys = (await keys()) as string[];
      const ours = allKeys.filter((k) => typeof k === 'string' && k.startsWith(KEY_PREFIX));
      const records: ByodEntry[] = [];
      for (const k of ours) {
        const v = await get<ByodEntry>(k);
        if (v) records.push(v);
      }
      // Most-recent first.
      records.sort((a, b) => b.addedAt.localeCompare(a.addedAt));
      this.entries = records;
      this.loaded = true;
    } catch (e) {
      this.error = String(e);
    }
  }

  async add(manifest: Record<string, unknown>, raw: unknown): Promise<ByodEntry> {
    const id = String((manifest.id as string | undefined) ?? '').trim();
    if (!id) throw new Error('manifest.id is required');
    const entry: ByodEntry = {
      id,
      manifest,
      raw,
      addedAt: new Date().toISOString(),
    };
    await set(KEY_PREFIX + id, entry);
    // Upsert into our in-memory state (prepend; remove any duplicate)
    this.entries = [entry, ...this.entries.filter((e) => e.id !== id)];
    return entry;
  }

  async remove(id: string): Promise<void> {
    await del(KEY_PREFIX + id);
    this.entries = this.entries.filter((e) => e.id !== id);
  }

  async clear(): Promise<void> {
    for (const e of this.entries) await del(KEY_PREFIX + e.id);
    this.entries = [];
  }
}

export const byodRegistry = new ByodRegistry();
