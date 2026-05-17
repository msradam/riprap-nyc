# Riprap rebrand — handoff package

What's in here, what ships from it, and what needs engineering work outside
the mockup.

## Files

| File | What it is |
|---|---|
| `Riprap Rebrand - Voice & Surface Mockups.html` | The full mockup. Open in a browser. Sections §1–§9. |
| `tokens.css` | The Civic Hydrology design tokens, unchanged from the source project. |
| `styles.css` | The existing component styles, unchanged from the source project. |
| `assets/logo.svg` | The dam mark. CC-BY 3.0 (Chintuza via the Noun Project). |
| `HANDOFF.md` | This file. |

The mockup is a single HTML document that imports `tokens.css` only — every
new component (phase banner, use-band, source strip, BYOD dialog, PDF page
preview, etc.) is styled inline so it ships as a self-contained deliverable.
Lift selectors into a SvelteKit component file when you port.

## Recommendation summary

Picked answers to BRIEF.md's four questions:

1. **Voice option** — A, rewritten in planner register. Hero deck reads
   "Type an address. Get a written briefing on flood, heat, or air-quality
   exposure. Every claim cites a public record from FEMA, NOAA, USGS, or
   city open data."
2. **Dynamic header chip** — yes. Chip text is `{hazard_tagline}` from
   `stones.yaml`, with a city pill from the deployment's city. Landing page
   defaults to "Climate-exposure briefing" (hazard-agnostic).
3. **Landing city picker** — yes, but under the input, not above it. Rotates
   through NYC, Chicago, Seattle, San Fran, Boston.
4. **Wordmark qualifier** — no. Keep `riprap` alone. The chip already carries
   the deployment context.

## What ships from the mockup directly

Each item below is text-only or CSS-only and is fundamentally a search-and-replace
in your existing Svelte components.

| # | Change | Files touched | LOC est. |
|---|---|---|---|
| 1 | Hero H1 + deck copy | `LandHero.svelte` | ~10 |
| 2 | City rotation in H1 + Try address line | `LandHero.svelte` | ~30 |
| 3 | Landing chip text → "Climate-exposure briefing" | `LandHeader.svelte` | ~3 |
| 4 | Dynamic chip from `stones.yaml` on app pages | `AppHeader.svelte` + new `/api/deployment` | ~20 |
| 5 | City picker below the search input | new `CityPicker.svelte` | ~40 |
| 6 | Phase banner above the hero | new `PhaseBanner.svelte` | ~25 |
| 7 | Responsible-use band (evidence-not-advice + non-affiliation) | new `UseBand.svelte` | ~30 |
| 8 | Source-count trust strip | new `SourceStrip.svelte` | ~20 |
| 9 | Standards strip badges (USWDS, WCAG, 508, PWA, OSS) | inline in `LandHero` | ~15 |
| 10 | Skip link (USWDS-canonical) | root layout | ~10 |
| 11 | Address input: `<label>` + `autocomplete="street-address"` + `enterkeyhint="search"` | `LandHero.svelte` | ~5 |
| 12 | Drop "Bring your own data" link target → opens BYOD dialog | `LandHero.svelte` | ~5 |

Estimate: ~210 LOC across 8 Svelte components, half a working day for
the text edits, another day for the new components if you start from the
mockup's selectors.

## What needs engineering work outside the mockup

### BYOD dialog (§6) — backend + adapter work

The dialog mock is just the surface. The engineering pieces it implies:

1. **File parsing in the browser.** Files stay on the user's machine. Use
   PapaParse for CSV, the native `Response.json()` for JSON / GeoJSON,
   js-yaml for `.yaml` / `.yml`. No server upload.
2. **Adapter auto-detection.** Map file extension + a 100-row header sniff
   to one of `socrata_records` / `geojson_polygons` / `csv_records` /
   `yaml_manifest`. The dialog's auto-detect radio is a thin wrapper around
   `core/pebbles/adapters/*` — reuse what's already there.
3. **Session-scoped registry.** Write the generated pebble manifest to
   IndexedDB. On the next briefing run, merge it with the deployment's
   `stones.yaml` registry the same way `RIPRAP_EXTRA_MANIFESTS` does in
   the CLI path. Cite the user's data as `user · {pebble_name}` so the
   audit trail shows what's public-record vs user-provided.
4. **Out of scope for v0.5** (called out in §6 of the mockup):
   - Server-side storage. Files stay in browser IndexedDB.
   - Cross-session sharing.
   - Schema validation against a published JSON Schema.
   - Multi-file uploads as a single pebble.

SvelteKit makes most of this easier than a plain SPA would:

- Use `+page.server.ts` only for the briefing run; the BYOD dialog is
  client-side only (no server-side handler needed for file ingest).
- Use SvelteKit form actions for the address submit. Keep the dialog
  as a client-only modal.
- Store the BYOD pebble registry in a Svelte store backed by IndexedDB
  (e.g. `idb-keyval`).

### PDF output (§9) — replace print-to-screen

The current `/print/<queryId>` route prints the rendered webpage with
chrome hidden via `print.css`. That has to go.

1. **New `/api/print/<queryId>.pdf` server route** that hydrates from
   the same briefing JSON the web view uses and renders the seven-page
   layout from §9 server-side.
2. **PDF engine.** WeasyPrint or Playwright/Chromium-headless. WeasyPrint
   has better PDF/UA tagging support out of the box; Playwright is faster
   and renders the layout exactly as the mockup shows. Pick based on
   whether PDF/UA-1 is a procurement gate (use WeasyPrint) or just a nice
   to have (use Playwright).
3. **PDF/UA-1 tagging.** Heading levels, list types, table cells, link
   destinations, language metadata, bookmark tree. WeasyPrint handles
   most of this from semantic HTML; Playwright needs a post-process pass
   with `pikepdf` or `pdf-lib` to add tags.
4. **Document metadata.** Title (address + briefing type), author
   ("Riprap framework"), subject, keywords, language `en-US`. Set via
   `pikepdf` or PDF engine's metadata API.
5. **Vector graphics.** Map polygons and address pin ship as PDF vector
   objects, not raster screenshots. WeasyPrint preserves SVG-as-vector;
   Playwright preserves canvas/SVG when emitting PDF (not when emitting
   PNG-then-PDF).
6. **Document hash.** SHA-256 of the briefing JSON, surfaced on the stamp
   page of every PDF. Two reviewers comparing the same briefing can
   verify by hash.
7. **Energy ledger.** Pull from the existing energy tracker; render the
   six lines on the methodology page (training target, serve hardware,
   wall time, tokens, kWh, CO₂e).

The mockup is the design target. Render to match.

### Map + evidence cards in the PDF (§9, pages 3 + 4)

- Page 3 (Map) reuses the MapLibre style and overlay layers from
  `LandMiniMap.svelte`, captured at a fixed zoom (z15 for address-level),
  re-emitted as vector PDF. Don't rasterise.
- Page 4 (Evidence cards) reads from the same Stone roll-up as the web
  Findings region, just typeset for print at smaller card sizes (see
  `.pdfx-ev-card-*` selectors in the mockup).

## Out of scope for this rebrand

Flagged in the mockup, not addressed here:

- README hero image still says NYC. Should rotate or composite per-city.
- VPAT for federal procurement (v0.6 target).
- Public a11y conformance report.
- First-language localisation. Framework supports it; landing strings don't.
- Methodology page UX. The PDF has the methodology section but there's no
  web equivalent at `/methodology` yet.

## Compliance ground covered

The mockup names which civic-tech rulebook each design decision satisfies
(§7). Quick index:

- **USWDS** — federal blue (`#005EA2`), IBM Plex, sentence-case headings,
  phase banner pattern, 44px touch targets, skip link, JS-disabled fallback.
- **GOV.UK Design System** — statement-of-purpose hero, bold-for-emphasis
  instead of italics, coverage stated as fact, GOV.UK phase-banner pattern.
- **Section 508 + WCAG 2.2 AA** — all text ≥ 4.5:1 contrast, 3px federal-blue
  focus rings, no color-only encoding, reduced-motion respected, labelled
  form inputs.
- **Plain Writing Act of 2010** — audience-first vocabulary ("audit trail",
  "source agency", "public record"), imperative voice, no internal jargon
  on user surfaces, short sentences, no em-dashes, agency-named provenance.
- **NIST AI RMF + algorithmic-accountability laws** — models named openly
  in the methodology surface and on the PDF cover, citation-mandatory
  outputs, energy ledger surfaced, no commercial APIs at runtime.
- **PDF/UA-1 (ISO 14289-1)** — tagged structure, document metadata,
  bookmarks tree, color-independent glyphs, vector graphics for the map.

## What I'd build first

In order, roughly half a day each:

1. The text edits (item 1–4 + 11–12 from the table above). Ship the new
   voice and the dynamic chip.
2. The new landing-page components (city picker, phase banner, use-band,
   source strip, standards strip, skip link). Ship the rebrand-completed
   landing page.
3. The BYOD dialog (client-side, IndexedDB-backed).
4. The PDF route. Start with WeasyPrint + the seven-page layout; layer
   PDF/UA tagging in a second pass.

The mockup is the spec. Everything in it is meant to ship verbatim except
for the BYOD adapter chain and the PDF engine, both of which need the
engineering work above.
