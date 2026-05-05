# Riprap Hackathon Week Audit — 2026-05-03 Evening

## TL;DR

The four register specialists (MTA entrances, NYCHA, DOE schools, DOH hospitals) are **shipped, FSM-wired, and validated end-to-end** as of commit `86861be` — the "subway-entrance specialist drift" hypothesis is wrong; it landed Sunday afternoon. The TerraMind-NYC fine-tune is running in its dedicated session (eval spec v2 in place, v1 postmortemed). The biggest real drift is in **pitch artifacts**: `pitch/cold_open.md` was deleted by commit `1cb5ee6` (Sunday 18:59 ET) along with the entire `pitch/` directory — `MONDAY.md` still shows it as ✓. The Build-in-Public posts, methodology paper PDF, ASCE materials, historical-event mode, and the four extra TTM specialists are **not started**. Visual identity v0.4.1/v0.4.2 is largely landed in `web/sveltekit/`. The planner-level refusal shim from Phase 6 is **documented as shipping in the FSM but is not actually wired into `app/planner.py`**.

## Specialist roster

| Specialist | Exists | Wired into FSM | Tested | Tier | Last touched | Notes |
|---|---|---|---|---|---|---|
| `geocode` | ✓ | ✓ | ✓ (integration) | reference | baseline | `app/geocode.py` |
| `sandy_inundation` | ✓ | ✓ | ✓ | empirical | baseline | NYC-only gated |
| `dep_stormwater` | ✓ | ✓ | ✓ | modeled | baseline | 3 scenarios |
| `floodnet` | ✓ | ✓ | ✓ | empirical | baseline | |
| `nyc311` | ✓ | ✓ | ✓ | empirical | baseline | |
| `noaa_tides` | ✓ | ✓ | ✓ | empirical | baseline | |
| `nws_alerts` | ✓ | ✓ | ✓ | empirical | baseline | |
| `nws_obs` | ✓ | ✓ | ✓ | empirical | baseline | |
| `ttm_forecast` (Battery surge) | ✓ | ✓ | ✓ | modeled | baseline | TTM r2 |
| `ttm_311_forecast` | ✓ | ✓ | ✓ | modeled | baseline | per-address TTM r2 |
| `microtopo_lidar` | ✓ | ✓ | ✓ | proxy | baseline | |
| `ida_hwm_2021` | ✓ | ✓ | ✓ | empirical | baseline | |
| `prithvi_eo_v2` (baked Ida polys) | ✓ | ✓ | ✓ | empirical | baseline | |
| `prithvi_eo_live` (Sentinel-2) | ✓ | ✓ (heavy) | ✓ | empirical | baseline | gated by `RIPRAP_HEAVY_SPECIALISTS` |
| `terramind_synthesis` (DEM→LULC) | ✓ | ✓ (heavy) | — | synthetic | baseline | |
| `rag_granite_embedding` | ✓ | ✓ | ✓ | reference | baseline | |
| `gliner_extract` | ✓ | ✓ | ✓ | reference | baseline | |
| **`mta_entrance_exposure`** | ✓ | ✓ | ✗ (no per-specialist test) | mixed | 2026-05-03 | first output Sheepshead Bay |
| **`nycha_development_exposure`** | ✓ | ✓ (heavy) | ✗ | mixed | 2026-05-03 | first output Red Hook |
| **`doe_school_exposure`** | ✓ | ✓ (heavy) | ✗ | mixed | 2026-05-03 | first output Coney Island |
| **`doh_hospital_exposure`** | ✓ | ✓ (heavy) | ✗ | mixed | 2026-05-03 | first output Coney Island |
| FEMA OpenFEMA NFIP claims | ✗ | ✗ | ✗ | — | — | not started |
| NWS NWPS reach forecast | ✗ | ✗ | ✗ | — | — | not started |
| USGS NWIS streamgages | ✗ | ✗ | ✗ | — | — | not started |
| NYC DEP CSO/Bluebelt/GI | ✗ | ✗ | ✗ | — | — | not started |
| TTM streamgage stage forecast | ✗ | ✗ | ✗ | — | — | not started |
| TTM FloodNet sensor depth | ✗ | ✗ | ✗ | — | — | not started |
| TTM NWS rainfall accumulation | ✗ | ✗ | ✗ | — | — | not started |
| TTM citywide 311 sewer-backup | ✗ | ✗ | ✗ | — | — | not started |
| Granite Guardian terminal check | ✗ | ✗ (pivoted) | — | — | — | replaced by planner-level refusal in design — but see Anomalies |

## Foundation models

| Model | Imported | Instantiated | Called | Routed via LiteLLM | Notes |
|---|---|---|---|---|---|
| Granite 4.1:3b (planner) | ✓ | ✓ | ✓ | ✓ | `app/planner.py` via `app.llm.chat` |
| Granite 4.1:8b (reconciler) | ✓ | ✓ | ✓ | ✓ | `app/reconcile.py`, `app/mellea_validator.py` |
| Granite Embedding 278M | ✓ | ✓ | ✓ | n/a (HF transformers) | `app/rag.py` |
| Granite Reranker R2 | ✓ | ✓ | ✓ (when enabled) | n/a | gated; see test_phase3 |
| GLiNER medium v2.1 | ✓ | ✓ | ✓ | n/a | `app/context/gliner_extract.py` |
| Prithvi-EO 2.0 Sen1Floods11 | ✓ | ✓ (heavy) | ✓ (live) | n/a | `app/flood_layers/prithvi_live.py` |
| TerraMind 1.0 base | ✓ | ✓ (heavy) | ✓ | n/a | `app/context/terramind_synthesis.py` |
| Granite TTM r2 (surge + 311) | ✓ | ✓ | ✓ | n/a | `app/live/ttm_forecast.py` — only 2 of planned 6 instances |
| Granite Guardian 3.2 3B-A800M | ✗ | ✗ | ✗ | — | dropped per Phase 6 pivot |

## Data sources

| Source | Status | Consumer | Notes |
|---|---|---|---|
| Sandy Inundation 2012 (NYC OEM) | implemented | `sandy_inundation`, all 4 registers | `data/sandy_inundation.geojson` |
| NYC DEP Stormwater Flood Map | implemented | `dep_stormwater`, registers | 3 scenarios |
| FloodNet sensors | implemented | `floodnet` | |
| NYC 311 service requests | implemented | `nyc311`, `ttm_311_forecast` | |
| NOAA CO-OPS tides | implemented | `noaa_tides`, `ttm_forecast` | |
| NWS alerts + obs | implemented | `nws_alerts`, `nws_obs` | |
| Hurricane Ida HWMs (USGS) | implemented | `ida_hwm` | |
| Prithvi-EO Ida polygons (baked) | implemented | `prithvi_water` | |
| Sentinel-2 via Planetary Computer | implemented | `prithvi_live` | heavy |
| MTA Subway Entrances 2024 | implemented | `mta_entrances` | `data/mta_entrances.geojson` (2120 entrances) |
| USGS 3DEP DEM 1m / HAND | implemented | registers | `data/nyc_dem_30m.tif`, `data/hand.tif` |
| NYCHA Development Data Book | implemented | `nycha` | per `b196bd8`+ |
| NYC DOE School Locations | implemented | `doe_schools` | |
| NYS DOH / NYC hospitals | implemented | `doh_hospitals` | |
| MTA Sandy-recovery report | not started | (queued) | Monday plan — `[mta_recovery_<station_id>]` doc messages |
| FEMA OpenFEMA NFIP claims | not started | — | |
| NWS NWPS reach forecast API | not started | — | |
| USGS NWIS streamgages | not started | — | |
| NYC DEP CSO outfalls | not started | — | |
| NYC DEP Bluebelt | not started | — | |
| NYC DEP Green Infrastructure DB | not started | — | |
| PLUTO building footprints | not started | (queued — fixes centroid-edge) | NYU Langone/Stuyvesant/P.S. 89 false-negatives |

## Design system v0.4.1/v0.4.2 integration

| Item | Status | Notes |
|---|---|---|
| Carto Positron / Voyager basemap | ✓ | `web/sveltekit/src/lib/components/map/baseStyle.ts` |
| IBM Plex Sans/Mono/Serif | ✓ | `tokens.css` |
| Four-tier color palette (CSS vars, WCAG-fixed values) | ✓ | `tokens.css` matches the spec hex codes |
| Epistemic-tier glyph SVG | ✓ | `lib/components/glyphs/TierGlyph.svelte` |
| Per-claim margin glyph rendering | ✓ | `Briefing.svelte` + `Claim.svelte` |
| Section-head tier badges | ✓ | `SectionHead.svelte`, `TierBadge.svelte` |
| Hoverable inline citations + drawer | ✓ | `Cite.svelte`, `CitationDrawer.svelte` |
| Trace UI as `<details>` tree with tier badges | ✓ | `TraceUI.svelte`, `TraceRow.svelte` |
| Layers panel with tier badges | ✓ | `MapLegend.svelte` (4 layer entries hit by demo deck) |
| Cold-start with sample queries | ✓ | `ColdStart.svelte` |
| Trust-signal footer | ✓ | `AppFooter.svelte` |
| WeasyPrint PDF template | ✗ | only routed at `/print/{query_id}` (browser print); no WeasyPrint dep in `requirements.txt` |
| Browser print stylesheet | ✓ | `lib/print.css` |
| Loading / skeleton states | ✓ | `SkeletonBriefing.svelte` |
| Error states | ✓ | `ErrorCard.svelte` |
| Refusal state UI | ✓ component exists | `GuardianRefusal.svelte` — but back-end refusal classifier not wired (see Anomalies) |
| Reroll banner | ✓ | `RerollBanner.svelte` |
| Synthetic-stripe SVG pattern | ✓ | `synStripe.ts`, `ThumbStripe.svelte` |
| Granite version string = 4.1 | ✓ (sampled) | |
| RegisterCard evidence format | ✓ | `RegisterCard.svelte` (rendered in `nyu-langone` demo run) |
| Dark mode | unverified | not searched |

## Accessibility

| WCAG 2.2 AA item | Status | Notes |
|---|---|---|
| Tier color contrast verified | ✓ | tokens.css comments document per-color ratios + AA/AAA passes |
| Color independence (glyph shape) | ✓ | TierGlyph component exists |
| Skip-links | ✓ | `SkipLinks.svelte` |
| Focus rings | unverified | `--accent-graphical: #D17C00` token exists but per-element outline rules not audited |
| Heading hierarchy | unverified | not audited |
| Touch-target sizing | unverified | not audited |
| `role="log"` aria-live polite for streaming | ✓ | found in `agentStream.ts`, `Briefing.svelte`, `RerollBanner.svelte`, `SkeletonBriefing.svelte` |
| Map `role="application"` + alt-text | unverified | grep didn't surface — needs walk through `RipMap.svelte` |
| `prefers-reduced-motion` respected | ✓ (partial) | rules in `tokens.css` and `styles.css`; per-component coverage unverified |
| Plain-language redirect for resident queries | unverified | `ColdStart.svelte` mentions FloodHelpNY redirect per spec — not visually verified |
| Glyph alt-text (`role="img"`) | unverified | not audited |

## Keep-list and pitch artifacts

- ✓ `experiments/05_terramind_nyc_finetune/eval/eval_spec.md` — present (also `eval_spec_v2.md` with v1 postmortem at `eval/v1_synth_sar_postmortem.md`)
- ⚠ `pitch/cold_open.md` — **DELETED** by commit `1cb5ee6` (2026-05-03 18:59 ET, "Demo deck: 10/10 live SSE tests"). MONDAY.md still says ✓. Last good content is in commit `b4239de`.
- ✓ `experiments/06_granite_guardian/adversarial_queries.jsonl` — present + planner-pivot results in `planner_refusal_summary.md` and `RESULTS.md`
- ✗ `experiments/07_historical_event_mode/` — does not exist
- ✗ Methodology paper draft (6-8 page PDF) — only `METHODOLOGY.md` (264 lines, scoring-methodology only, not the publication paper draft)
- ✗ `pitch/` directory — gone (deleted with cold_open.md). Demo-side artifacts now live in `web/sveltekit/tests/e2e/demo-script.md` and the (gitignored) `pitch/screenshots-2026-05-03/`
- ✗ `asce/` — does not exist
- ✗ Build-in-Public posts — no `posts/`, `build_in_public/`, or comparable directory

## Integration tests

- 26 tests collected in `tests/test_integration.py` (parametrized over `brighton`, `hollis`, `hunts`); plus `test_agent_e2e.py`, `test_agent_full.py`, `test_sample_queries.py`. Not executed (would exceed 30 s budget — they hit the live SSE stream).
- The 4 new register specialists have **no per-specialist integration test** in `tests/`. Coverage is via the e2e `demo-queries.spec.ts` Playwright suite (`web/sveltekit/tests/e2e/`), which runs them in the FSM during `nyu-langone`, `red-hook-houses-nycha`, `coney-island`, `sheepshead-bay` queries.
- Frontend Playwright suites: `coldstart`, `demo-queries`, `layers`, `print`, `sample`, `states`, `sticky-map` (7 spec files).

## experiments/ directory

- `00_endpoints` — completed (RESULTS.md, 8/8 endpoint smokes)
- `01_prithvi_live_water` — completed
- `02_gliner_extraction` — completed
- `03_granite_reranker` — completed
- `04_terramind_synthetic_sar` — parked-as-research per commit `271e673`
- `05_sam2_promptable` — empty directory (mid-flight or abandoned scaffolding)
- `05_terramind_finetune` — early micro-FT scaffold (`micro.py` + `RESULTS.md`); superseded by `05_terramind_nyc_finetune/`
- `05_terramind_nyc_finetune` — **active in another session**; eval_spec_v2 in place, training subdir present
- `06_chronos_bolt_forecast` — empty directory (not started)
- `06_granite_guardian` — completed-as-pivot (Guardian → planner shim; `planner_refusal_summary.md` documents FAIL on 5% FP gate)
- `07_mta_entrances` — completed and migrated to `app/registers/mta_entrances.py`
- `08_nycha_developments` — completed and migrated
- `09_doe_schools` — completed and migrated
- `10_doh_hospitals` — completed and migrated

## Anomalies and weird things

- `experiments/05_sam2_promptable/` and `experiments/06_chronos_bolt_forecast/` are **empty directories** — either abandoned scaffolds or interrupted sessions. There is also `experiments/05_terramind_finetune/` (early micro-FT) sitting next to `experiments/05_terramind_nyc_finetune/` (current).
- **Numbering collision at `05_*` and `06_*`** between the empty/legacy dirs and the active ones.
- **Planner-level refusal shim is documented as shipping but is not in `app/`.** `experiments/06_granite_guardian/RESULTS.md` and MONDAY.md both say "the planner-level refusal shim still ships in the FSM as a polite-refusal layer." A grep for `refusal|guardian` across `app/` (including `app/planner.py`) returns no hits. The frontend `GuardianRefusal.svelte` component exists but has no backend signal to display.
- **`pitch/cold_open.md` deletion** by `1cb5ee6` is almost certainly accidental — that commit's message describes adding 6 demo queries and a `demo-script.md`; deleting the cold-open is unrelated and not mentioned. Likely casualty of moving screenshots into a gitignored path.
- **`Riprap.zip` at repo root** is untracked — leftover archive.
- **CLAUDE.md / MONDAY.md disagree on AMD droplet IP**: CLAUDE.md never mentions an IP (uses `<droplet-ip>` placeholders); MONDAY.md explicitly says CLAUDE.md is wrong (cites `165.245.134.44`) and that `129.212.182.52` is production. CLAUDE.md grep doesn't surface the wrong IP, so the MONDAY.md note may itself be stale.
- **MONDAY.md status table out-of-sync** with the deletion of `pitch/cold_open.md`.
- No TODO/FIXME/XXX comments in `app/` Python or in `web/sveltekit/src/`.
- No imports from `experiments.*` inside `app/` or `web/`.
- No specialists registered in `app/fsm.py` are missing from `app/registers/` or `app/context/` (vice-versa clean).
- WeasyPrint is referenced in MONDAY.md / spec but is **not in `requirements.txt`** — `/print/{query_id}` route serves a browser-print page only.

## The single most important gap

The originally-suspected subway-entrance specialist gap is not real — that work shipped Sunday afternoon and is wired through the FSM, the reconciler, and the demo Playwright suite. The single most important *actual* gap is the **deletion of `pitch/cold_open.md` (and the entire `pitch/` directory) in commit `1cb5ee6`**. The cold-open phrasing was an explicit Sunday keep-list item ("seven-tunnels framing, no inflated dollar figure"), Sunday's MONDAY.md handoff still treats it as ✓, and the AMD demo on May 10 will require it. The content is recoverable from `git show b4239de:pitch/cold_open.md` and should be restored before any other Monday work begins.

## Recommended next-session priorities

1. **Restore `pitch/cold_open.md`** — `git show b4239de:pitch/cold_open.md > pitch/cold_open.md` and commit. ~5 min. Done = file present, MONDAY.md row still accurate, content matches the seven-tunnels framing.
2. **Wire the planner-level refusal shim into `app/planner.py`** — the documented contract from Phase 6 (FN=0% safety-critical) is not actually live. ~30–60 min. Done = planner returns `refusal_reason` field on the 50 should-refuse adversarial queries; `GuardianRefusal.svelte` renders end-to-end on at least one out-of-scope query in the e2e suite.
3. **PLUTO building-footprint join for register centroid-edge cases** — single change unlocks NYU Langone / Stuyvesant / P.S. 89 flipping to `inside_sandy_2012=true` across all four register specialists. Pre-existing queue from MONDAY.md. ~2–3 hr. Done = the three known-failing addresses each show `inside_sandy_2012=true` in the FSM trace and the briefing cites `[doh_hospital_*]` / `[doe_school_*]` accordingly.
4. **MapLibre rendering for the 4 register specialists** — entrance points coloured by Sandy/DEP, NYCHA polygon fills graded by `pct_inside_sandy`, school + hospital points in the same color ramp. The data is in state; the map layers aren't yet drawing them. ~2–4 hr. Done = layers panel shows ≥4 new layer entries on `red-hook-houses-nycha` and `nyu-langone`; e2e screenshot diff captures them.
5. **Remove dead/empty experiment dirs and clarify numbering** — delete `experiments/05_sam2_promptable/`, `experiments/06_chronos_bolt_forecast/`, and decide whether `experiments/05_terramind_finetune/` should be folded into the NYC fine-tune dir or kept as a separate phase artifact. ~15 min. Done = no empty dirs; numbering collision documented or resolved.
