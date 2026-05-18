/**
 * Component-level rendering tests for cardAdapter — the heart of the
 * UI bug the user reported.
 *
 * The user-visible failure: querying a Boston address showed the NYC
 * scaffold ("□ sandy not invoked", "□ ida_hwm not invoked", …) below
 * a header chip that read "NYC". This file is the regression seal for
 * that whole class of bug:
 *
 *   given the API response for `<city>` + the pebbleManifest a
 *   `<city>`-routed UI WOULD have loaded, adaptFinalToFindings
 *   produces cards whose pebble ids are exactly the `<city>` set —
 *   no leakage across, no ghosts.
 *
 * No browser. No Playwright. Runs in ~1s under vitest.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { adaptFinalToFindings } from '$lib/client/cardAdapter';
import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';
import type { PebbleManifest, PebbleStone } from '$lib/stores/pebbleManifest.svelte';
import {
  STONES,
  NYC_MANIFEST, BOSTON_MANIFEST,
  NYC_ONLY_IDS,
  NYC_FINAL, BOSTON_FINAL,
} from './fixtures/cardAdapter';

/**
 * Drop the manifest store into a deterministic state for one test.
 * adaptFinalToFindings reads `pebbleManifest.stones` and
 * `pebbleManifest.byStone` directly; populating those gives us a
 * fully controlled scaffold.
 */
function seedManifest(stones: PebbleStone[], pebbles: PebbleManifest[]): void {
  const byId: Record<string, PebbleManifest> = {};
  const byStone: Record<string, PebbleManifest[]> = {};
  for (const p of pebbles) {
    byId[p.id] = p;
    (byStone[p.stone] ||= []).push(p);
  }
  pebbleManifest.byId = byId;
  pebbleManifest.stones = stones;
  pebbleManifest.byStone = byStone;
  pebbleManifest.loaded = true;
  pebbleManifest.error = null;
}

beforeEach(() => {
  pebbleManifest.byId = {};
  pebbleManifest.stones = [];
  pebbleManifest.byStone = {};
  pebbleManifest.loaded = false;
  pebbleManifest.error = null;
});

/**
 * Card ids come in three flavours:
 *   - `pebble-<id>`   templated path (BYOD / non-curated)
 *   - `fsm-<slug>`    curated builder, e.g. `fsm-nws-obs`, `fsm-capstone-meta`
 *   - bare ids        legacy / direct pebble matches
 *
 * Tests compare against the underlying pebble id, which we extract from
 * the card's actual id and from any pebble-prefixed templated card.
 */
function pebbleIdsInCards(cards: { id: string }[]): Set<string> {
  const out = new Set<string>();
  for (const c of cards) {
    if (c.id.startsWith('pebble-')) out.add(c.id.slice('pebble-'.length));
    else if (c.id.startsWith('fsm-')) out.add(c.id.slice('fsm-'.length).replace(/-/g, '_'));
    else out.add(c.id);
  }
  return out;
}

function pebbleIdsInStoneRoster(findings: { stones: { members: { id: string }[] }[] }): Set<string> {
  const out = new Set<string>();
  for (const s of findings.stones) for (const m of s.members) out.add(m.id);
  return out;
}

describe('adaptFinalToFindings — per-query scaffold seal', () => {
  // ───────────────────────────────────────── happy path — NYC
  it('NYC manifest + NYC final → roster carries every NYC pebble', () => {
    // Asserting against findings.stones[].members[] uses the manifest's
    // pebble id directly (see fillRosterFromManifests), which is the
    // stable contract. Card ids are derived slugs (`fsm-ida-hwm` etc.)
    // and intentionally not part of the public contract.
    seedManifest(STONES, NYC_MANIFEST);
    const findings = adaptFinalToFindings(NYC_FINAL as never, null, 12.3);
    const rosterIds = pebbleIdsInStoneRoster(findings);

    for (const expected of ['sandy', 'ida_hwm', 'nyc311', 'npcc4_slr',
                            'mta_entrances', 'doe_schools']) {
      expect(rosterIds.has(expected),
        `${expected} missing from NYC roster. Got: [${[...rosterIds].sort().slice(0, 20).join(', ')}]`,
      ).toBe(true);
    }
  });

  // ───────────────────────────────────────── the actual bug — Boston
  it('Boston manifest + Boston final → ZERO NYC-only ids in cards', () => {
    seedManifest(STONES, BOSTON_MANIFEST);
    const findings = adaptFinalToFindings(BOSTON_FINAL as never, null, 3.4);
    const ids = pebbleIdsInCards(findings.cards);

    const leaked = [...ids].filter(id => NYC_ONLY_IDS.has(id));
    expect(leaked, `NYC-only pebble cards leaked into Boston render: ${leaked.join(', ')}`).toEqual([]);
  });

  it('Boston manifest + Boston final → renders boston_311 + water_level', () => {
    seedManifest(STONES, BOSTON_MANIFEST);
    const findings = adaptFinalToFindings(BOSTON_FINAL as never, null, 3.4);
    const ids = pebbleIdsInCards(findings.cards);

    for (const expected of ['boston_311', 'water_level']) {
      expect(ids.has(expected),
        `${expected} missing from Boston render. Got: [${[...ids].sort().join(', ')}]`,
      ).toBe(true);
    }
  });

  // ───────────────────────────────────────── THE bug the user reported
  it('NYC manifest + Boston final (mis-loaded scaffold) → ghost NYC rows in stones roster', () => {
    // The WRONG state — Boston run but the UI loaded the NYC scaffold.
    // The user's screenshot showed "□ sandy not invoked", "□ ida_hwm not
    // invoked"… coming from the per-Stone roster (NOT from cards[]).
    // fillRosterFromManifests reads pebbleManifest.byStone for *every*
    // stone; with the NYC scaffold loaded those rows get rendered as
    // not_invoked even when the run was Boston.
    seedManifest(STONES, NYC_MANIFEST);
    const findings = adaptFinalToFindings(BOSTON_FINAL as never, null, 3.4);

    // findings.stones[].members has every pebble in the loaded scaffold;
    // a Boston run with NYC scaffold puts NYC ids into Cornerstone /
    // Keystone with status='not_invoked'. That IS the visible bug.
    const rosterIds = pebbleIdsInStoneRoster(findings);
    const ghosts = [...rosterIds].filter(id => NYC_ONLY_IDS.has(id));

    expect(
      ghosts.length,
      'expected ghost NYC ids in the stones roster under the (incorrect) NYC-scaffold-for-Boston-run mode — the bug the user reported. If this drops to 0 with a real Boston scaffold loaded, the UI fix has landed.',
    ).toBeGreaterThan(0);

    // Document the specific ghosts so the test failure is informative.
    expect(ghosts).toEqual(expect.arrayContaining(['sandy', 'ida_hwm', 'doe_schools']));
  });

  it('Boston manifest + Boston final → ZERO NYC ghosts in stones roster (the fix)', () => {
    // The CORRECT state — Boston scaffold loaded for a Boston run. The
    // per-Stone roster should contain ONLY Boston (and federal) ids.
    // This is the regression seal: once the UI loads the per-query
    // scaffold, this assertion holds.
    seedManifest(STONES, BOSTON_MANIFEST);
    const findings = adaptFinalToFindings(BOSTON_FINAL as never, null, 3.4);

    const rosterIds = pebbleIdsInStoneRoster(findings);
    const ghosts = [...rosterIds].filter(id => NYC_ONLY_IDS.has(id));
    expect(ghosts,
      `Boston roster contains NYC ghosts: ${ghosts.join(', ')}`,
    ).toEqual([]);
    expect(rosterIds.has('boston_311')).toBe(true);
  });

  it('empty manifest + Boston final → no NYC-only cards even with no scaffold', () => {
    seedManifest(STONES, []);
    const findings = adaptFinalToFindings(BOSTON_FINAL as never, null, 3.4);
    const ids = pebbleIdsInCards(findings.cards);
    const leaked = [...ids].filter(id => NYC_ONLY_IDS.has(id));
    expect(leaked).toEqual([]);
  });
});
