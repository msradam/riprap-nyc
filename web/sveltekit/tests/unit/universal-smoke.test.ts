/**
 * Universal smoke — every component listed below must mount and emit
 * non-empty rendered output under happy-dom without throwing. Catches
 * the class of bug where a Svelte 5 rune or import path crash makes a
 * whole region of the UI dark; the per-component tests assert
 * content, this one is the floor.
 *
 * Adding a new component to src/lib/components/ should mean adding a
 * row here too. The test list is intentionally maintained by hand:
 * each entry pins what the minimal valid props look like, which is
 * itself a contract.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render, type RenderResult } from '@testing-library/svelte';
import type { Component } from 'svelte';
import { resetStores, seedForCity } from './helpers/stores';
import { BOSTON } from './fixtures/cities';

// Shell
import AppHeader from '$lib/components/shell/AppHeader.svelte';
import AppFooter from '$lib/components/shell/AppFooter.svelte';
import StatusPill from '$lib/components/shell/StatusPill.svelte';
import RipMark from '$lib/components/shell/RipMark.svelte';
import SkipLink from '$lib/components/shell/SkipLink.svelte';
import SkipLinks from '$lib/components/shell/SkipLinks.svelte';
import ColdStart from '$lib/components/shell/ColdStart.svelte';
// Briefing
import Briefing from '$lib/components/briefing/Briefing.svelte';
import CitationDrawer from '$lib/components/briefing/CitationDrawer.svelte';
import SectionHead from '$lib/components/briefing/SectionHead.svelte';
// Findings
import FindingsRegion from '$lib/components/findings/FindingsRegion.svelte';
import StoneRegion from '$lib/components/findings/StoneRegion.svelte';
import StoneTally from '$lib/components/findings/StoneTally.svelte';
import RunHealthStrip from '$lib/components/findings/RunHealthStrip.svelte';
// Map
import MapLegend from '$lib/components/map/MapLegend.svelte';
// States
import ErrorCard from '$lib/components/states/ErrorCard.svelte';
import SkeletonBriefing from '$lib/components/states/SkeletonBriefing.svelte';
import RerollBanner from '$lib/components/states/RerollBanner.svelte';
// Trace
import TraceUI from '$lib/components/trace/TraceUI.svelte';
import StatusGlyph from '$lib/components/trace/StatusGlyph.svelte';
// Glyphs
import AssetPin from '$lib/components/glyphs/AssetPin.svelte';
import TierBadge from '$lib/components/glyphs/TierBadge.svelte';
import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';

import type { FindingsData, StoneTrace, StoneKey } from '$lib/types/card';

const emptyStone = (s: StoneKey): StoneTrace => ({
  stone: s, members: [], fired: 0, silent_by_design: 0, errored: 0, ms: 0,
});

const EMPTY_FINDINGS: FindingsData = {
  cards: [],
  stones: ['cornerstone', 'touchstone', 'keystone', 'lodestone', 'capstone']
    .map((s) => emptyStone(s as StoneKey)),
  wallSeconds: 0,
};

interface SmokeCase {
  name: string;
  Component: Component<any>;  // eslint-disable-line @typescript-eslint/no-explicit-any
  props: Record<string, unknown>;
}

const ALL_ON = { empirical: true, modeled: true, proxy: true, synthetic: true };

const CASES: SmokeCase[] = [
  // Shell
  { name: 'AppHeader',         Component: AppHeader,         props: { queryId: 'test-q' } },
  { name: 'AppFooter',         Component: AppFooter,         props: {} },
  { name: 'StatusPill',        Component: StatusPill,        props: {} },
  { name: 'RipMark',           Component: RipMark,           props: {} },
  { name: 'SkipLink',          Component: SkipLink,          props: {} },
  { name: 'SkipLinks',         Component: SkipLinks,         props: {} },
  { name: 'ColdStart',         Component: ColdStart,         props: {} },

  // Briefing
  { name: 'Briefing',          Component: Briefing,
    props: { blocks: [], citations: {} } },
  { name: 'CitationDrawer',    Component: CitationDrawer,    props: { citations: {} } },
  { name: 'SectionHead',       Component: SectionHead,
    props: { n: '01', label: 'Test', title: 'Test section' } },

  // Findings
  { name: 'FindingsRegion',    Component: FindingsRegion,
    props: { data: EMPTY_FINDINGS } },
  { name: 'StoneRegion',       Component: StoneRegion,
    props: { stone: 'cornerstone', cards: [], trace: emptyStone('cornerstone') } },
  { name: 'StoneTally',        Component: StoneTally,
    props: { cardCount: 0, members: [] } },
  { name: 'RunHealthStrip',    Component: RunHealthStrip,
    props: { cards: [], stones: EMPTY_FINDINGS.stones, wallSeconds: 0 } },

  // Map
  { name: 'MapLegend',         Component: MapLegend,
    props: { active: ALL_ON, onToggle: () => {} } },

  // States
  { name: 'ErrorCard',         Component: ErrorCard,
    props: { state: 'geocoder' } },
  { name: 'SkeletonBriefing',  Component: SkeletonBriefing,  props: {} },
  { name: 'RerollBanner',      Component: RerollBanner,
    props: { attempt: 1, attemptMax: 3 } },

  // Trace
  { name: 'TraceUI',           Component: TraceUI,
    props: { root: {
      id: 'root', name: 'root', status: 'ok' as const, ms: 0, tier: null,
    } } },
  { name: 'StatusGlyph',       Component: StatusGlyph,
    props: { status: 'ok' as const } },

  // Glyphs
  { name: 'AssetPin',          Component: AssetPin,
    props: { kind: 'SCH' as const, size: 10 } },
  { name: 'TierBadge',         Component: TierBadge,
    props: { tier: 'empirical' as const } },
  { name: 'TierGlyph',         Component: TierGlyph,
    props: { tier: 'empirical' as const, size: 11, color: 'var(--tier-empirical)' } },
];

beforeEach(() => {
  resetStores();
  // Most components read from the stores (deployment, pebbleManifest);
  // seeding Boston is the strictest test — non-NYC + non-trivial
  // manifest means a component reaching for a hardcoded NYC string
  // is more likely to fail.
  seedForCity(BOSTON);
});

describe('Universal smoke: every shipped component mounts under happy-dom', () => {
  it.each(CASES.map((c) => [c.name, c] as const))(
    '%s mounts without throwing',
    (_name, c) => {
      let result: RenderResult<Component<any>> | null = null;  // eslint-disable-line @typescript-eslint/no-explicit-any
      expect(() => {
        result = render(c.Component, { props: c.props });
      }).not.toThrow();
      // Even an "empty" component should produce SOME DOM (a wrapping
      // element, an aria-live region, etc.). Catches the case where a
      // component throws silently and renders nothing.
      expect(result?.container?.firstChild,
        `${c.name} rendered no DOM`,
      ).not.toBeNull();
    },
  );
});
