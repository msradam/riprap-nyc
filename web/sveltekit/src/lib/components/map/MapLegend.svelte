<script lang="ts">
  import type { Tier } from '$lib/types/tier';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
  import TierBadge from '$lib/components/glyphs/TierBadge.svelte';
  import type { StoneKey } from '$lib/types/card';
  import { STONE_META, STONE_ORDER } from '$lib/types/card';
  import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';

  /** v0.4.5 §7 — LAYERS panel restructured to mirror Findings Stones.
   *
   *  Each Stone is its own collapsed-but-visible group with one row per
   *  map layer keyed to that Stone. Master tier toggles (the live
   *  empirical / modeled / synthetic / proxy switches the map respects
   *  today) sit at the bottom of the panel; per-Stone rows inherit
   *  their tier's master state and display the resolved ON/OFF.
   *
   *  Rows for layers that aren't yet wired into the map visibility
   *  pipeline render with a dimmed "off (not yet wired)" caption so the
   *  reader sees the catalog without thinking the toggle is broken. */

  type MasterKey = 'empirical' | 'modeled' | 'synthetic' | 'proxy';
  interface Props {
    active: Record<MasterKey, boolean>;
    /** Per-tier feature counts. Used to surface "no features" inline
     *  on each Stone row. `null` means caller wants the full catalog
     *  shown regardless of data-driven counts. */
    featureCounts?: Record<MasterKey, number> | null;
    onToggle: (key: MasterKey) => void;
  }

  let { active, featureCounts, onToggle }: Props = $props();

  type LayerRow = {
    label: string;
    source: string;
    tier: Tier;
    /** When false, the row is purely catalog — the master tier toggle
     *  doesn't yet drive a real map source. Surfaced as "not yet wired". */
    wired: boolean;
  };

  /** v0.6 — layer catalog is now derived from the loaded
   *  pebbleManifest so a Boston query sees Boston's layers, not the
   *  hardcoded NYC list (which previously rendered "Sandy Inundation
   *  Zone", "Ida HWM points", "MTA subway entrances", etc. under a
   *  Boston chip — a real bug surfaced by the user's screenshot).
   *  Pebbles flagged `display.map_layer: true` in their manifest
   *  become rows under their declared Stone. Pebbles without the
   *  flag are intentionally hidden — they have data but no geometry. */
  const stoneLayers = $derived.by<Record<StoneKey, LayerRow[]>>(() => {
    const empty: Record<StoneKey, LayerRow[]> = {
      cornerstone: [], keystone: [], touchstone: [], lodestone: [], capstone: [],
    };
    for (const stone of STONE_ORDER) {
      const pebbles = pebbleManifest.byStone[stone] ?? [];
      for (const p of pebbles) {
        if (!p.display.map_layer) continue;
        empty[stone].push({
          label: p.title,
          source: p.provenance.source_name,
          tier: (p.tier ?? 'modeled') as Tier,
          wired: true,
        });
      }
    }
    return empty;
  });

  /** Resolve a row's ON state from the master tier toggle. */
  function isOn(row: LayerRow): boolean {
    return !!active[row.tier];
  }

  function tally(stone: StoneKey): number {
    return stoneLayers[stone].length;
  }

  // Active tier toggles — rendered as small chips at the bottom of the
  // panel so the user can still flip the four master switches.
  const MASTERS: { k: MasterKey; tier: Tier; label: string }[] = [
    { k: 'empirical', tier: 'empirical', label: 'EMP' },
    { k: 'modeled',   tier: 'modeled',   label: 'MOD' },
    { k: 'proxy',     tier: 'proxy',     label: 'PRX' },
    { k: 'synthetic', tier: 'synthetic', label: 'SYN' },
  ];

  // featureCounts is intentionally accepted but not used in the catalog
  // view — the catalog shows every row regardless of live counts. Kept
  // in the prop signature so callers don't have to change.
</script>

<aside class="layers-panel" aria-label="Map layers grouped by Stone">
  <div class="layers-head">
    <span class="section-label">Layers · grouped by Stone</span>
  </div>

  {#each STONE_ORDER as stone (stone)}
    <!--
      Stones with no map layers (Boston/Chicago/SF Cornerstone +
      Keystone + Lodestone, Seattle most of them) collapse by default
      so the user isn't presented with 4 expanded "no map layers"
      rows. Stones with at least one layer (or Capstone which always
      shows its "not a map layer" line) stay open so the layers are
      immediately visible.
    -->
    <details class="layers-group region-{stone}"
             open={tally(stone) > 0 || stone === 'capstone'}>
      <summary>
        <span class="layers-caret" aria-hidden="true">▾</span>
        <span class="layers-stone-name">{STONE_META[stone].name}</span>
        <span class="layers-stone-tag">— {
          pebbleManifest.stones.find((s) => s.id === stone)?.description
            ?? STONE_META[stone].tag
        }</span>
        {#if tally(stone) > 0}
          <span class="layers-count">{tally(stone)}</span>
        {/if}
      </summary>
      <ul class="layers-list">
        {#if stone === 'capstone'}
          <li class="layers-row layers-row-empty">
            <span class="layers-empty-text">not a map layer</span>
          </li>
        {:else if stoneLayers[stone].length === 0}
          <li class="layers-row layers-row-empty">
            <span class="layers-empty-text">no map layers — see Findings cards</span>
          </li>
        {:else}
          {#each stoneLayers[stone] as row, i (i)}
            <li class="layers-row" class:dim={!row.wired}>
              <span class="layers-glyph" aria-hidden="true">
                <TierGlyph tier={row.tier} size={11} color="var(--tier-{row.tier})" />
              </span>
              <span class="layers-text">
                <span class="layers-label">{row.label}</span>
                <span class="layers-meta">{row.source} · <TierBadge tier={row.tier} compact /></span>
              </span>
              <span class="layers-state">
                {#if !row.wired}
                  <span class="layers-state-dim" title="Not yet wired to map source">off · catalog</span>
                {:else if isOn(row)}
                  on
                {:else}
                  off
                {/if}
              </span>
            </li>
          {/each}
        {/if}
      </ul>
    </details>
  {/each}

  <!-- Master tier toggles. These are the actual switches the map honours
       today; each Stone row above resolves ON/OFF from these. -->
  <div class="layers-masters" role="group" aria-label="Master tier toggles">
    <span class="section-label">Tier toggles</span>
    <div class="layers-master-row">
      {#each MASTERS as m (m.k)}
        <button
          type="button"
          class="layers-master"
          class:is-on={active[m.k]}
          aria-pressed={active[m.k]}
          onclick={() => onToggle(m.k)}
        >
          <TierGlyph tier={m.tier} size={11} color="var(--tier-{m.tier})" />
          <span>{m.label}</span>
          <span class="layers-master-state">{active[m.k] ? 'ON' : 'OFF'}</span>
        </button>
      {/each}
    </div>
  </div>
</aside>

<style>
  .layers-panel {
    background: var(--paper);
    border: 1px solid var(--rule-soft);
    padding: var(--s-3) var(--s-4) var(--s-4);
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
    font-family: var(--font-sans);
  }
  .layers-head { padding-bottom: 4px; }

  .layers-group {
    border-top: 1px solid var(--rule-soft);
    padding-top: var(--s-2);
    /* Stone-tinted left rule (v0.4.5 §9 sibling treatment). */
    border-left: 3px solid var(--stone-tint, var(--rule-soft));
    padding-left: var(--s-3);
  }
  .layers-group.region-cornerstone { --stone-tint: var(--stone-cornerstone); }
  .layers-group.region-keystone    { --stone-tint: var(--stone-keystone); }
  .layers-group.region-touchstone  { --stone-tint: var(--stone-touchstone); }
  .layers-group.region-lodestone   { --stone-tint: var(--stone-lodestone); }
  .layers-group.region-capstone    { --stone-tint: var(--stone-capstone); }

  .layers-group summary {
    cursor: pointer;
    list-style: none;
    display: flex;
    align-items: baseline;
    gap: var(--s-2);
    padding: 4px 0;
  }
  .layers-group summary::-webkit-details-marker { display: none; }
  .layers-caret {
    font-size: 10px;
    color: var(--ink-tertiary);
    transition: transform 200ms ease;
  }
  .layers-group:not([open]) .layers-caret { transform: rotate(-90deg); }
  .layers-stone-name {
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 16px;
    color: var(--ink);
  }
  .layers-stone-tag {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    letter-spacing: 0.04em;
  }
  .layers-count {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--ink-tertiary);
    letter-spacing: 0.05em;
    text-transform: lowercase;
  }

  .layers-list {
    list-style: none;
    margin: 4px 0 var(--s-2);
    padding: 0;
    display: flex;
    flex-direction: column;
  }
  .layers-row {
    display: grid;
    grid-template-columns: 16px 1fr auto;
    gap: var(--s-2);
    align-items: center;
    padding: 4px 0;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink);
    border-bottom: 1px dotted var(--rule-soft);
  }
  .layers-row:last-child { border-bottom: 0; }
  .layers-row.dim { opacity: 0.7; }
  .layers-glyph { display: inline-flex; align-items: center; }
  .layers-text { display: flex; flex-direction: column; gap: 2px; }
  .layers-label {
    color: var(--ink);
    font-family: var(--font-sans);
    font-size: 12px;
  }
  .layers-meta {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--ink-tertiary);
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .layers-state {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.05em;
    color: var(--ink);
    text-transform: uppercase;
  }
  .layers-state-dim {
    color: var(--ink-tertiary);
    text-transform: lowercase;
    font-style: italic;
  }
  .layers-row-empty .layers-empty-text {
    grid-column: 1 / -1;
    color: var(--ink-tertiary);
    font-style: italic;
    font-family: var(--font-mono);
    font-size: 11px;
  }

  .layers-masters {
    border-top: 1px solid var(--rule-soft);
    padding-top: var(--s-2);
  }
  .layers-master-row {
    margin-top: 4px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .layers-master {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    background: var(--paper);
    border: 1px solid var(--rule-soft);
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.05em;
    color: var(--ink);
  }
  .layers-master.is-on { background: var(--paper-deep); border-color: var(--ink); }
  .layers-master-state {
    margin-left: 4px;
    color: var(--ink-tertiary);
    font-size: 9px;
  }
  .layers-master.is-on .layers-master-state { color: var(--ink); }
</style>
