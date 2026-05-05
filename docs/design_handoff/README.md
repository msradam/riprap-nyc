# Handoff: Riprap Findings Region (v0.4.4)

## Overview

**Riprap** is a citation-grounded Flood Exposure Briefing tool for New York City. A user enters an address, neighborhood, or proposed development; Riprap returns a written briefing where every numeric claim links to its primary public-record source (FEMA, USGS, NYC DOITT, FloodNet, NYC OpenData, etc.).

This handoff covers the **Findings region** — the structured-data sibling of the briefing prose. It groups model outputs into five named "Stones" (cognitive roles), each rendered as a card stack with explicit epistemic tiering, smart provenance traces, and cross-linking to the map.

The target codebase is **SvelteKit** (Svelte 5 with runes). The files in `design_files/` are React-based prototypes — design references, not production code. Recreate them as Svelte components.

## About the Design Files

The files in `design_files/` are **design references created in HTML + React** — high-fidelity prototypes showing the intended look and behavior. They are **not production code to copy directly**.

Your task is to **recreate these designs in the existing Svelte codebase**, using its established patterns (Svelte 5 runes, scoped styles, the project's existing route structure and data layer). Lift visual values, copy, and interaction logic from the references; do not transpile JSX to Svelte.

**File pairing** (each prototype area has one or two source files):

- `Riprap Stone-Grouped UI v0.4.4.html` — main prototype, the v0.4.4 Findings region in context
- `findings.jsx` — Findings region: stones, cards, run-health, grammar reference (the centerpiece of this handoff)
- `briefing.jsx` — long-form briefing prose with inline citations
- `map.jsx` — mini-map with FEMA AE / HWM / FloodNet / 311 / address layers and link highlighting
- `trace.jsx`, `stones-trace.jsx`, `stone-evidence.jsx` — provenance trace variants
- `shell.jsx` — app header, footer, cold-start state
- `glyphs.jsx` — four tier glyphs as inline SVG
- `tokens.css` — design tokens (colors, type, spacing). Port verbatim.
- `styles.css` — component CSS. Reference only; rewrite as scoped Svelte styles.
- `tweaks-panel.jsx`, `design-canvas.jsx`, `landing-variants.*` — prototype-time tooling. Ignore.

## Fidelity

**High-fidelity (hifi).** Pixel-perfect mockups with final colors, typography, spacing, glyphs, and interactions. Recreate the UI pixel-perfectly using the codebase's existing libraries and patterns. The tier color values, the IBM Plex font stack, the 4/8/12/16/24/32/48/64/96 spacing scale, and the four-tier glyph system are all final.

The Findings region in particular has been through several iterations (v0.4.0 → v0.4.4) and is settled. Don't redesign card layouts; port them as-is.

## Screens / Views

The product is a single-page app with two states: **cold-start** (no query) and **briefing** (query active).

### 1. Cold-start

Empty state with the wordmark, a deck explaining what Riprap is, a query input, three sample-query buttons, and a "How Riprap is built" trust band. See `shell.jsx` → `<ColdStart>`.

- **Layout**: centered single column, max-width ~720px, paper background (`--paper`)
- **Wordmark**: `riprap` lowercase, IBM Plex Mono 14px / 600, with a 0.85em accent bar `▌` prefix
- **Deck**: serif paragraph, 18px, line-height 1.55, ink-secondary
- **Query input**: full width, 1px ink border, mono placeholder, 16px
- **Submit**: ink fill, paper text, mono caps, 13px
- **Sample queries**: three buttons in a column, each shows mode (caps mono) / query (sans 16px) / sub (mono 12px tertiary)
- **Trust band**: section-label heading, italic-serif "Cornerstone remembers. Keystone tallies. Touchstone watches. Lodestone projects. Capstone writes it all down with citations." then a bullet list

### 2. Briefing (active query)

Three-region layout, vertical stack:

1. **App header** (sticky top): wordmark · context · query pill · methodology / export PDF / live status
2. **Briefing prose region**: long-form text with inline `[N]` citations, three side-by-side panes (excerpt · evidence cards · mini map)
3. **Findings region**: the v0.4.4 Stone-grouped card stack (this handoff's focus)
4. **Footer**: tier legend + build line

The Findings region is the substantial new surface. Everything below documents it.

## Findings Region (v0.4.4) — detailed spec

### Composition

```
<FindingsRegion>
  <RunHealthStrip />               ← 1 row, top, summarizes all 25 model calls
  <StoneRegion stone="cornerstone" />
  <StoneRegion stone="keystone" />
  <StoneRegion stone="touchstone" />
  <StoneRegion stone="lodestone" />
  <StoneRegion stone="capstone" />
  <CardGrammarReference />         ← optional, on by default; one stub per variant
</FindingsRegion>
```

### Stones

Five fixed roles, in order:

| key | name | role | tag |
|---|---|---|---|
| `cornerstone` | Cornerstone | the hazard reader | what NYC's ground remembers |
| `keystone` | Keystone | the asset register | what's exposed |
| `touchstone` | Touchstone | the present-tense witness | what's happening now |
| `lodestone` | Lodestone | the future-pointer | what's coming |
| `capstone` | Capstone | the writer | what we say, with citations |

Each `<StoneRegion>` has:

- **Header**: Stone name (IBM Plex Serif 26px italic for the name, sans for the role) · role tagline · `<StoneTally>` chip showing `N/M cards fired` · provenance toggle button
- **Provenance trace**: smart-default expansion (see below). Renders specialist tree with status pips.
- **Card grid**: 12-column grid, each card spans 4 cols by default (3 per row); register/timeseries/raster cards may span 6.

### Card data schema

```ts
type Card = {
  stone: "cornerstone" | "keystone" | "touchstone" | "lodestone" | "capstone";
  tier: "empirical" | "modeled" | "proxy" | "synthetic";
  variant: CardVariant;       // see below
  source: string;             // short label, e.g. "FEMA"
  agency: string;             // long form, e.g. "FEMA preliminary FIRM, panel 36047C..."
  vintage: string;            // e.g. "2024-Q3" or "2007–present"
  title: string;              // card title
  // variant-specific fields:
  headline?: string; subhead?: string;
  columns?: string[]; rows?: (string | number)[][];
  scalars?: { label: string; value: string; unit?: string }[];
  spark?: number[]; histogram?: number[];
  timeseries?: { hours: number[]; values: number[]; threshold?: number };
  forecast?: { years: number[]; p10: number[]; p50: number[]; p90: number[] };
  raster?: "stormwater" | "fema-ae" | "hwm" | "floodnet-density" | ...;
  register?: { tag: string; label: string; sourceId: string; detail: string }[];
  comparison?: { left: ScalarSet; right: ScalarSet; delta: string };
  meta?: Record<string, string>;
  // citation fan-out:
  cites?: { id: string; label: string; href?: string }[];
  // map link:
  mapLayer?: "fema-ae" | "hwm" | "floodnet" | "nycha" | "address" | ...;
};
```

See `findings.jsx` lines 12–230 for the canonical `CARDS` table populated for the Red Hook query.

### Card grammar (12 variants)

Every card uses the same chrome — title row (sans 14/600), source · agency · vintage row (mono 11/tertiary), a body block, and a footer with the **tier badge** (3-letter caps mono) and a "cite" button. The body block is one of:

| variant | shape | use |
|---|---|---|
| `headline` | one big number/label, scenario-tagged subhead | single-fact cards: "Zone AE" |
| `tabular` | small N×3 table, mono | observation lists: HWM marks |
| `scalars` | 2–3 labeled scalars in a row | "1.2 m · 0.18 mi · 2012" |
| `spark` | 60×24 inline sparkline, no axes | trend at a glance |
| `histogram` | 8–12 bar histogram, mono labels | distributions |
| `timeseries` | 240×84 line chart with threshold rule | hourly water level, 311 calls |
| `forecast` | 240×88 fan chart (p10/p50/p90) | 2050/2080 SLR, surge |
| `raster` | 240×120 stylized raster thumbnail | FEMA AE polygon, stormwater extent, HWM contour |
| `raster-pred` | same shape with dashed top-rule (synthetic tier) | TerraMind 2050 prediction |
| `register` | 3-col dense list (tag · label · sourceId), detail in `title=` tooltip | NYCHA buildings, schools |
| `comparison` | side-by-side scalar columns with delta | FEMA-AE vs Prithvi-2050 |
| `meta` | definition list of run metadata | model id, prompt hash, latency |

**Synthetic tier** cards (TerraMind predictions, prior-only Lodestone outputs) get a **dashed top-rule** (1px dashed `--tier-synthetic-line`) to telegraph "no observed data here." Comparison cards always render synthetic.

The `<CardGrammarReference>` region renders one stub per variant in `findings.jsx` lines 529–581 — a visual catalog the design team uses to spot-check fidelity. Keep it, gate it on `showGrammar` prop (default true in dev, false in prod).

### Tier system

Four epistemic tiers, encoded redundantly:

| tier | color | glyph | badge | meaning |
|---|---|---|---|---|
| `empirical` | `#0B5394` (8.59:1) | filled square | EMP | observed, ground-truth |
| `modeled` | `#2A6FA8` (5.41:1) | open square | MOD | computed from observations |
| `proxy` | `#6B6B6B` (5.74:1) | dotted ring | PRX | indirect signal, e.g. 311 calls |
| `synthetic` | `#2A6FA8` + dashed | hatched square | SYN | model prior, no observation |

Glyphs are inline SVG, 12×12, black-stroke. See `glyphs.jsx` for the four shapes.

**Accessibility**: tier is *always* encoded by color + glyph + label, never color alone. Modeled and synthetic share a hue; the dashed top-rule and glyph carry the difference.

### Provenance trace

Every Stone has a tree of specialists ("CORN-001: pull FEMA NFHL → CORN-002: parse panel index → ..."). Each specialist has a status: `ok` / `warn` / `error` / `silent`.

**Smart-default rule** (`provenanceMode = "smart"`):

- All-`ok` Stone → **collapsed** by default, single-line summary "12/12 specialists fired clean"
- Any `warn` or `error` → **expanded**, full tree visible
- All `silent` → collapsed, single-line "no firings (section omitted from briefing)"

`provenanceMode = "expanded"` forces all expanded; `"collapsed"` forces all collapsed (warn/error still get a count chip).

The trace UI: indented tree, mono ids, status pip (●/▲/■/○) in tier-color or warn/error colors. Specialist names italic-serif. Hovering a specialist row dims the rest. See `trace.jsx` for the leaf and `stones-trace.jsx` for the per-Stone composition.

### Run-health strip

Single row above the Stones, full-width. Shows:

- Total specialists fired / total specialists registered (e.g. `83/100`)
- Per-tier breakdown as four chips: `EMP 41 · MOD 28 · PRX 12 · SYN 2`
- Total runtime (e.g. `3.4s`)
- Cache-hit ratio (e.g. `92%`)

Mono throughout. Background `--paper-deep`, 1px ink-soft top + bottom rule.

### Hover linking

Every card with a `mapLayer` is hoverable. On hover (or focus), the card's `key` becomes the page-level `linkedKey`. The briefing's map frame reads `linkedKey` and:

- Adds `is-link-{layer}` class to its root, which lights up that layer (see `map.jsx` for the CSS rules)
- Renders a small label badge bottom-right: "linked: {layer}"

The same applies in reverse: hovering a layer in the map sets `linkedKey` to the corresponding card key, which gets a 2px accent outline.

In Svelte: lift `linkedKey` to `+page.svelte` as `let linkedKey = $state(null)`, pass it down both branches, and have the cards / layers update it on `pointerenter` / `focus` / `pointerleave` / `blur`.

### Density

`density: "compact" | "comfortable"` (default `comfortable`).

- **Comfortable**: 16px card padding, 14px line-height multiplier 1.4
- **Compact**: 10px card padding, 12px line-height multiplier 1.25, register-card row height 18px (vs 24px)

Pass through to all card bodies; only register/tabular/meta visibly change.

## Interactions & Behavior

- **Card hover**: 200ms `background-color` transition to `--paper-deep`, 2px accent outline if linked
- **Cite button**: opens a small popover with the full citation list (`cites[]`), each row a link to the source PDF/page
- **Provenance toggle**: button with `aria-expanded`, animates the tree open/closed via `details`/`summary` or scoped `max-height` transition (≤200ms)
- **Map layer hover**: sets `linkedKey`, 100ms layer fill opacity transition
- **Reduced motion**: all transitions become 0.01ms via the global rule in `tokens.css`. Don't add motion on top.
- **Keyboard**: every card is `tabindex=0` with `aria-label="{tier} card · {title} · {source}"`. Cite button is real `<button>`. Provenance toggle is real `<button>`.
- **Loading**: cards show a 1px ink-soft skeleton (no spinner); replace with content when the specialist returns
- **Error / silent**: cards with status `error` render a 1-line "specialist failed: {reason}" in tier-error color and stay; cards with status `silent` are omitted entirely (silence over confabulation — design tenet)

## State Management

Svelte 5 runes; lift to `+page.svelte`:

```svelte
<script>
  let query = $state(null);
  let density = $state("comfortable");
  let provenanceMode = $state("smart");
  let showComparison = $state(false);
  let showGrammar = $state(false);   // dev-only toggle
  let linkedKey = $state(null);

  // Data: load once per query, hydrate from server
  let cardsByStone = $derived(loadCards(query));
  let runHealth = $derived(summarize(cardsByStone));
</script>
```

Children take props via `$props()`. No Svelte stores unless cross-route.

Data fetching: assume the existing codebase has a `+page.server.ts` load function that runs the 25 specialists and returns the `Card[]` payload. This handoff doesn't change the data layer; it changes the rendering.

## Design Tokens

Port `tokens.css` verbatim. Key values:

**Tier colors** (all WCAG AA on white):
- `--tier-empirical: #0B5394` (8.59:1)
- `--tier-modeled: #2A6FA8` (5.41:1)
- `--tier-proxy: #6B6B6B` (5.74:1)
- `--tier-synthetic: #2A6FA8` (pattern-differentiated)

**Neutrals**:
- `--paper: #FAFAF7` (warm near-white, USGS-report register)
- `--paper-deep: #F2F2EE`
- `--ink: #1A1A1A` · `--ink-secondary: #4A4A4A` · `--ink-tertiary: #6B6B6B`
- `--rule: #1A1A1A` · `--rule-soft: #C9C9C5`

**Accent**:
- `--accent: #B8620A` (for text, AA)
- `--accent-graphical: #D17C00` (for shapes/lines, ≥3:1)

**Type**:
- `--font-sans: "IBM Plex Sans"` (UI, body)
- `--font-serif: "IBM Plex Serif"` (Stone names, hero italic emphasis, oversized stone numerals)
- `--font-mono: "IBM Plex Mono"` (labels, source ids, badges, table cells)

All three are SIL OFL / Apache; self-host or load from Google Fonts. **No system fallbacks for branding** — always specify the Plex stack, fall through only on load failure.

**Spacing** (`--s-1` through `--s-9`): 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96 px. Use these tokens; don't hand-roll values.

**Type scale** (suggested, not enforced):
- 11px mono labels (`section-label`)
- 12–13px mono row text
- 14px sans card titles (600)
- 16px sans body
- 18px sans deck text
- 26px serif italic Stone names
- 36–52px serif headlines (italic for emphasis)

**Radius**: 0 throughout (this is a civic-tech-clean, USGS-report register; no rounded corners except `1px` on focus rings).

**Shadows**: none. Differentiation by 1px rules and `--paper-deep` fills only.

## Assets

- **Fonts**: IBM Plex Sans / Serif / Mono. Self-host woff2 or Google Fonts.
- **Wordmark**: text + accent bar `▌` prefix, no logo file
- **Tier glyphs**: inline SVG, see `glyphs.jsx`
- **Map raster thumbnails**: hand-drawn SVG approximations using each layer's conventional palette. See `findings.jsx` → `RasterThumb`. Replace with real raster previews if/when MapLibre tile snapshots are wired up.
- **Real map**: the production map should use **MapLibre GL** with a custom `style.json` that respects the tier palette. Style fragments are sketched in `shell.jsx` comments.
- **No icon library.** No Lucide, no Heroicons. SVG glyphs for tiers, mono characters (⌕, ↗, ▌) for chrome.
- **No emoji.**

## Files in this bundle

```
design_handoff_riprap_findings/
├── CLAUDE_CODE_PROMPT.md        ← paste this into Claude Code first
├── README.md                     ← you are here
└── design_files/
    ├── Riprap Stone-Grouped UI v0.4.4.html   ← main prototype, open in browser
    ├── Riprap Landing.html
    ├── Riprap Landing Variants.html
    ├── tokens.css                ← port verbatim
    ├── styles.css                ← reference only
    ├── findings.jsx              ← Findings region (this handoff's centerpiece)
    ├── briefing.jsx              ← long-form prose
    ├── evidence.jsx              ← evidence card stack used in briefing
    ├── map.jsx                   ← mini-map with link highlighting
    ├── trace.jsx
    ├── stones-trace.jsx
    ├── stone-evidence.jsx
    ├── shell.jsx                 ← header, footer, cold-start
    ├── glyphs.jsx                ← four tier glyphs
    ├── tweaks-panel.jsx          ← prototype tooling, ignore
    ├── design-canvas.jsx         ← prototype tooling, ignore
    ├── landing-variants.css      ← marketing-page exploration, ignore unless asked
    └── landing-variants.jsx      ← marketing-page exploration, ignore unless asked
```

## Scope

**In scope** for this handoff: the Findings region (5 Stones, 12 card variants, run-health strip, smart provenance, hover linking, card grammar reference). Briefing prose and map are in scope to the extent they connect to Findings via `linkedKey`.

**Out of scope**: the cold-start state, the marketing landing page, the methodology PDF, the export-PDF flow. Port these later.

## Open questions for the design team

These are deliberately *not* resolved in the prototype; raise them with the designer before locking implementation:

1. Should `register` cards paginate when N > 20, or stay scrollable in a fixed-height card?
2. The `comparison` card is currently always synthetic (FEMA-AE vs Prithvi-2050). Will there be empirical-vs-empirical comparisons (e.g. FEMA-AE vs HWM observed)?
3. Run-health cache-hit ratio — is this surfaced to end users, or is it dev-mode only?
4. Provenance trace expansion: should expanded state survive across query changes, or reset?
