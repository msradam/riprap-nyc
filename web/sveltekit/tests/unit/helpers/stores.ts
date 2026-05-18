/**
 * Store seeding helpers — drop the global rune stores into a
 * deterministic state for one test. Mirrors what /api/* responses
 * + the SSE handshake would do at run time.
 */
import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';
import { deployment } from '$lib/stores/deployment.svelte';
import { briefingState } from '$lib/stores/briefingState.svelte';
import type { CityFixture } from '../fixtures/cities';

/** Reset every store to its idle state. Call from `beforeEach`. */
export function resetStores(): void {
  pebbleManifest.byId = {};
  pebbleManifest.stones = [];
  pebbleManifest.byStone = {};
  pebbleManifest.loaded = false;
  pebbleManifest.loadedFor = null;
  pebbleManifest.error = null;

  deployment.current = null;
  deployment.loaded = false;
  deployment.error = null;

  briefingState.reset();
}

/** Seed every store as if the SSE handshake for a given city had
 *  already completed: deployment chip + pebble scaffold loaded, phase
 *  set to 'done'. */
export function seedForCity(fixture: CityFixture): void {
  // pebbleManifest — as if /api/pebbles?deployment=<city> resolved
  const byId: Record<string, typeof fixture.manifest.pebbles[number]> = {};
  const byStone: Record<string, typeof fixture.manifest.pebbles[number][]> = {};
  for (const p of fixture.manifest.pebbles) {
    byId[p.id] = p;
    (byStone[p.stone] ||= []).push(p);
  }
  pebbleManifest.byId = byId;
  pebbleManifest.stones = [...fixture.manifest.stones].sort((a, b) => a.order - b.order);
  pebbleManifest.byStone = byStone;
  pebbleManifest.loaded = true;
  pebbleManifest.loadedFor = fixture.key === 'elsewhere' ? null : fixture.key;
  pebbleManifest.error = null;

  // deployment — as if /api/deployment?deployment=<city> resolved
  deployment.current = fixture.deployment;
  deployment.loaded = true;
  deployment.error = null;

  // briefingState — settled at 'done' so the UI is in the post-run state
  briefingState.phase = 'done';
  briefingState.ready = true;
  briefingState.activeStep = null;
  briefingState.firedCount = fixture.manifest.pebbles.length;
  briefingState.totalSpecialists = fixture.manifest.pebbles.length;
}

/** A `forEach`-friendly helper: run a callback for every city fixture. */
export function forEachCity<T>(
  fixtures: readonly CityFixture[],
  fn: (city: CityFixture) => T,
): Map<string, T> {
  const results = new Map<string, T>();
  for (const f of fixtures) results.set(f.key, fn(f));
  return results;
}
