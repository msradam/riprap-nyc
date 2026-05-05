# Prompt for Claude Code

Copy-paste this whole block into Claude Code as your opening message. It frames the task and points at the files in this bundle.

---

You're implementing a high-fidelity design into the existing Riprap codebase, which is **SvelteKit**. The design is a citation-grounded Flood Exposure Briefing UI for NYC, with the new "Findings region" as the centerpiece.

The design lives in `design_handoff_riprap_findings/`. **Read `README.md` first**, then the `design_files/` directory. The HTML/JSX prototypes there are React-based references — your job is to **port them to Svelte 5 components** using runes (`$state`, `$derived`, `$props`) and the project's existing patterns. Do not copy JSX or React idioms; recreate the same visual + interaction grammar in idiomatic Svelte.

**Order of work:**

1. **Tokens first.** Port `design_files/tokens.css` verbatim into the app's global stylesheet (or wherever design tokens live in the existing codebase). The four epistemic tier colors (`--tier-empirical/modeled/proxy/synthetic`), the paper-register neutrals, the IBM Plex font stack, and the spacing scale are non-negotiable — every component below references them.

2. **Card grammar.** Build the 12 card-body variants documented in §"Card grammar" of the README as small leaf components: `<HeadlineCard>`, `<TabularCard>`, `<ScalarsCard>`, `<SparkCard>`, `<HistogramCard>`, `<TimeseriesCard>`, `<ForecastCard>`, `<RasterCard>`, `<RasterPredCard>`, `<RegisterCard>`, `<ComparisonCard>`, `<MetaCard>`. Each takes a `card` prop matching the schema in §"Card data schema". A wrapper `<FindingCard>` renders the chrome (header strip, tier glyph, source, agency, footer with tier badge) and slots the body. Synthetic cards get a dashed top-rule.

3. **Stone region.** A `<StoneRegion>` component groups cards by Stone (cornerstone / keystone / touchstone / lodestone / capstone). Header has the Stone name (serif italic), role tagline, run-tally chip, and a provenance toggle. Provenance trace renders below the header per the smart-default rules in §"Provenance trace".

4. **Findings region.** Composes 5 `<StoneRegion>`s in fixed order, with a `<RunHealthStrip>` above them and (optionally) `<CardGrammarReference>` below. Wire props through: `density`, `provenanceMode`, `queryKey`, `showComparison`, `showGrammar`.

5. **Cross-component linking.** Hovering a card sets `linkedKey` (Svelte store or `$state` lifted to the page). The briefing's map frame highlights the matching layer. See §"Hover linking" in the README.

6. **Briefing + map + trace.** Once Findings is solid, port `briefing.jsx`, `map.jsx`, and `trace.jsx` similarly. The briefing is a long-form text region with inline citations whose hover state lights up the corresponding map layer.

**Conventions to follow (read these before writing code):**

- **Svelte 5 runes only.** No legacy `let`-as-state, no stores unless cross-route. Lift state to `+page.svelte` and pass via `$props()`.
- **No emoji.** No icon font. Tier glyphs are inline SVG; see `glyphs.jsx` for the four shapes (filled square / open square / dotted ring / hatched square).
- **No Tailwind.** This codebase uses scoped `<style>` blocks per component. Reuse the token CSS variables from step 1 — don't redeclare colors or spacing.
- **No animation libraries.** All transitions are CSS, ≤200ms, and respect `prefers-reduced-motion` (already covered by the global rule in `tokens.css`).
- **Accessibility is a hard requirement.** Tier is encoded by *color + glyph + label* (never color alone). Focus rings are 3px accent. Every interactive card needs `aria-label`. Provenance toggles are buttons with `aria-expanded`.

**What to ignore in the bundle:**

- The `Riprap Landing*.html` files are exploratory marketing-page variants, not part of this handoff. Port them only if explicitly asked.
- `design-canvas.jsx`, `tweaks-panel.jsx`, `landing-variants.*` are prototype-time tooling, not product code.
- The React component files (`*.jsx`) are reference implementations. Use them to read structure, copy strings/numbers, and verify visual fidelity — don't transpile them.

**When in doubt, open the HTML file in a browser** (`Riprap Stone-Grouped UI v0.4.4.html`) and compare your Svelte output side-by-side. Pixel parity on the Findings region is the bar.
