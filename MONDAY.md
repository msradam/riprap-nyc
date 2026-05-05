# Monday handoff (May 4, 2026)

State of the repo at end of Sunday May 3 / overnight into May 4.
Demo is **Sunday May 10**.

## Overnight pass (Sunday evening → Monday)

Eight priorities closed against `audit/2026-05-03-evening-audit.md`:

1. `pitch/cold_open.md` restored (was accidentally deleted in 1cb5ee6).
2. Granite Guardian / refusal-classification leftovers removed —
   Mellea is the sole grounding mechanism, period.
3. **Trace UI is now clickable.** Click any specialist row to reveal
   its raw structured output (formatted JSON, copy button,
   max-height + scroll). This is the auditability contract: every
   claim in the briefing is traceable to the specialist that produced
   it directly inside the UI, not just the citation appendix.
4. Buffered-footprint overlap for the three Point-geometry register
   specialists. NYU Langone / Stuyvesant HS / P.S. 89 now correctly
   register `inside_sandy_2012=true`. Each output records its
   `footprint_buffer_m`.
5. Map renders register-asset pins (subway / school / hospital /
   NYCHA-centroid) coloured by Sandy exposure with click popups
   showing name + `[doc_id]`. NYCHA polygon-fill is queued for when
   `geometry_geojson` lands in the dataclass.
6. **`floodnet_forecast` specialist** — TTM r2 forecast on the
   nearest FloodNet sensor's flood-event recurrence. Reuses the
   (512, 96) singleton already loaded for `ttm_311_forecast` —
   *no new model class loaded into memory*. The strongest single
   TTM win for the NYU CUSP audience.
7. Trace UI groups TTM specialists under one parent node
   `forecasting.granite-timeseries-ttm-r2 [N instances]` so the
   "one foundation model, multiple data streams" architectural story
   is legible without reading per-row metadata.
8. `experiments/` cleanup: dropped two empty dirs (`05_sam2_promptable`,
   `06_chronos_bolt_forecast`), renamed `05_terramind_finetune` →
   `05a_terramind_finetune_micro` to dedupe with the active NYC
   fine-tune dir, removed `Riprap.zip` from repo root.

Commit chain: `a2143fc` … through `ed6ae9d`. Morning handoff doc
at `audit/2026-05-04-morning-handoff.md` summarises what to verify
and what's queued next.

## Where Sunday ended

All four keep-list items resolved + 4 register specialists shipped + AMD
fine-tune prep green.

| Item | Status | Path |
|---|---|---|
| Pitch cold-open locked | ✓ | `pitch/cold_open.md` |
| TerraMind-NYC fine-tune eval spec | ✓ | `experiments/05_terramind_nyc_finetune/eval/eval_spec.md` |
| 200-query adversarial set + refusal eval | ✓ (planner pivot) | `experiments/06_granite_guardian/` |
| Subway-entrance specialist (Sheepshead Bay) | ✓ | `experiments/07_mta_entrances/` |
| NYCHA-developments specialist (Red Hook) | ✓ | `experiments/08_nycha_developments/` |
| DOE-schools specialist (Coney Island) | ✓ | `experiments/09_doe_schools/` |
| DOH-hospitals specialist (Coney Island) | ✓ | `experiments/10_doh_hospitals/` |
| FSM integration of all 4 register specialists | ✓ | `app/registers/`, `app/fsm.py`, `app/reconcile.py`, `web/static/agent.js` |
| AMD droplet TerraMind smoke + STAC manifest | ✓ | `129.212.182.52:/root/terramind_nyc/` |

End-to-end smoke on "Coney Island Brooklyn" produced citations
`[mta_entrance_56]`, `[nycha_dev_239]`, `[nycha_dev_166]` alongside
`[rag_mta]` and `[nyc311]` — family-prefix chip routing works.

Last commit: `86861be` (FSM integration of 4 register specialists).

## Decisions locked

- **Refusal classification dropped entirely.** Planner-level
  classifier hit FN=0% but FP=7% (gate was <5%). Granite Guardian
  itself was already abandoned (laptop-infeasible). After the audit
  surfaced that the planner shim was documented-but-never-wired,
  the decision is now Option C: drop refusal handling. Cold-start
  framing scopes the audience; Mellea rejection sampling enforces
  grounding integrity; the four-tier glyph margin carries the
  epistemic-honesty signal. The `GuardianRefusal.svelte` component
  is deleted (was only ever rendered on a documentation page).
  Demo's integrity beat is the **Mellea grounding-failure reroll on
  the curated Hollis 0.19% → 19% case**. `experiments/06_granite_guardian/`
  is preserved as a "considered and rejected" artifact for the
  methodology paper.
- **AMD path: `129.212.182.52` is production**, not `165.245.134.44`.
  CLAUDE.md says the latter; **fix CLAUDE.md to match reality**.
  Production vLLM is on `.52`. The TerraMind container shares the
  GPU with vLLM; both fit on one MI300X.
- **TerraMind manifest is 1028 paired chips**, 2021-05 → 2026-04,
  NYC 5-borough hull +5 km, S2-cloud <30%, ≤3-day pair window. One
  year (2022-05 → 2023-04) returned 0 due to PC API intermittency —
  acceptable for the micro-fine-tune.

## First thing Monday morning

1. **Refresh Microsoft Planetary Computer signed URLs.** They have
   ~1 hr TTL; the manifest from Sunday evening is stale by morning.
   On the droplet:
   ```bash
   ssh root@129.212.182.52
   docker exec -it terramind bash
   cd /root/terramind_nyc
   python build_manifest.py --refresh-only manifest_train.jsonl
   python build_manifest.py --refresh-only manifest_holdout.jsonl
   ```
   (Recipe is in `/root/terramind_nyc/NOTES.md` on the droplet.)

2. **Kick off TerraMind-NYC fine-tune.** Spec at
   `experiments/05_terramind_nyc_finetune/eval/eval_spec.md`. Budget
   is 30 GPU-hours; alarm at 25 (set on the droplet). Predicted
   actual: ~0.16 GPU-hours at bs=8 / 3 epochs. Don't run anything
   experimental until eval-spec gates pass on the held-out set.

3. **Decide bucket** (A ship-in-demo / B publish-only / C revert):
   - A: ship the fine-tuned checkpoint as a Riprap specialist.
   - B: publish to HF as `msradam/TerraMind-1.0-NYC` with model card,
     don't ship in demo. **Bucket B is fully acceptable** per the
     spec — civic-tech publication discipline is the durable goal.
   - C: discard checkpoint, no public artefact.

## Working on Monday

- TerraMind-NYC fine-tune (above).
- **Mellea grounding-failure demo prep.** The pitch demo is the
  Hollis 0.19% → 19% case where Granite emits a number with the
  wrong order of magnitude and Mellea catches it. Demo script
  needs to:
  - Show the failed first attempt (banner: "Mellea reroll: numerics
    grounding failed").
  - Show the second attempt with the corrected number.
  - Show the audit panel with the pass/fail per-requirement.
  - Show wall-clock for the reroll (target: under 30 s end-to-end).
  - Currently reproducible via `scripts/probe_mellea.py --query
    "Hollis" --runs 5`. The demo script is the *visual* version.
- **MTA Sandy-recovery citation layer.** Parse the MTA "Hurricane
  Sandy: Three Years Later" report into per-station-id facts so
  the subway-entrance specialist can emit
  `[mta_recovery_<station_id>]` doc messages alongside the
  exposure ones.
- **NYCHA polygon-fill on the map.** Overnight session shipped
  NYCHA developments as centroid pins on the map (graded by
  `pct_inside_sandy ≥ 50%`). The next tightening is to add a
  `geometry_geojson` field to `app/registers/nycha.py`'s
  `DevelopmentFinding` dataclass and route through SSE so
  `register-polygons` actually renders graded fills (the layer +
  source are already present in `RipMap.svelte`).
- **PLUTO/Building-Footprints join** for Stuyvesant Town etc.
  Overnight pass shipped buffered-point overlap (NYU Langone,
  Stuyvesant HS, P.S. 89 now correctly flip to
  `inside_sandy_2012=true`). The 100m hospital buffer / 50m school
  buffer is honest but coarse; PLUTO + actual building footprints
  is the next step for the very-large-campus assets.

## Outstanding through Friday

In rough priority order:

1. **More specialists**:
   - FEMA OpenFEMA NFIP claims tract-aggregated (pending).
   - NWS NWPS reach-level forecast + USGS NWIS Bronx / Saw Mill /
     Hutchinson rivers.
   - NYC DEP CSO outfalls + Bluebelt + Green Infrastructure
     specialist (CSS-vs-MS4 distinction for ASCE).
   - Three more TTM r2 specialists (USGS streamgage stage, NWS
     rainfall accumulation, NYC 311 sewer-backup citywide rate).
     **FloodNet forecast already shipped in the overnight pass.**
2. **Visual identity refresh**: Carto Positron, IBM Plex, four-tier
   epistemic palette, WeasyPrint PDF export, trace UI as `<details>`
   tree.
3. **WCAG 2.2 AA pass.**
4. **Methodology paper draft** (6-8 page PDF). Goal: Saturday May 9.
5. **Historical-event mode** — vintage-cutoff queries. Saturday.
6. **Five Build-in-Public posts** through the week.
7. **5-minute hackathon pitch + 3 demo queries.** Friday rehearsal.
8. **ASCE talk materials** — May 13 (post-hackathon).

## Sharp edges to remember

- **Static assets cache hard.** When iterating on Svelte or
  agent.js, hard-reload (⌘⇧R). No cache-busting in place.
- **HF Space sleeps after idle.** Free tier; first request after
  sleep is a 30-90 s cold start. Ping the space before any demo.
- **vLLM cold compile.** First few requests against a fresh
  `vllm serve` log surprisingly low throughput while ROCm kernels
  JIT. Run benchmarks 3+ times before believing them.
- **Sandy GeoJSON has self-intersection issues** that blow up
  `unary_union`. Use `buffer(0)` (caught and fixed for NYCHA;
  may surface again for any new polygon-overlap specialist).
- **DEP column is `Flooding_Category` (int16)**, not `depth_class`.
  Documented in NYCHA RESULTS.md.
- **Centroid-edge join false-negatives** on NYU Langone / Stuyvesant
  / P.S. 89 because their centroid points lie just outside the OEM
  Sandy polygon despite real 2012 basement flooding. PLUTO
  footprint join is the queued fix.
- **Don't restart uvicorn while a model is mid-generation.** Ollama
  keeps the request alive but the FastAPI handler dies, leaving
  the user staring at a dead stream.

## Files to read in order on Monday morning

1. This file.
2. `experiments/05_terramind_nyc_finetune/eval/eval_spec.md` — the
   contract for what training output triggers ship/publish/revert.
3. `experiments/06_granite_guardian/RESULTS.md` — the Guardian →
   planner pivot decision record (so you know why Guardian is in
   the repo but not on the demo path).
4. `experiments/07_mta_entrances/RESULTS.md` — the canonical
   register-specialist pattern (the other three follow it).
5. `CLAUDE.md` — fix the AMD droplet IP (165.245.134.44 →
   129.212.182.52) at the same time as the first edit of the day.

## Status as of 2026-05-03 ~12:50 ET

- Both git remotes (origin + huggingface) up-to-date through
  `86861be`.
- HF Space rebuild was *not* triggered on the FSM-integration
  commit; do `git push huggingface main` when you want to deploy.
  (You may want to wait until Monday afternoon so a broken HF
  rebuild doesn't eat morning time.)
- Local Ollama has both `granite4.1:3b` and `granite4.1:8b` warm.
- AMD droplet `129.212.182.52` has the `terramind` container
  running with TerraTorch 1.2.7 + pystac-client + planetary-
  computer installed in system Python; HF cache populated.
- 200-query adversarial set + planner-pivot eval results
  reproducible from `experiments/06_granite_guardian/` in ~3 min.
- Mellea probe still works: `scripts/probe_mellea.py --query
  "Hollis" --runs 5`.
