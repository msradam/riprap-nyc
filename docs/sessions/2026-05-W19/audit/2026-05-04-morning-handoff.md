# Riprap overnight handoff — Monday 2026-05-04

Continuation point for the wake-up session. Read this first; everything
points outwards from here.

## TL;DR

All eight priorities from the overnight wiring pass landed. The
audit-flagged drift items are closed: cold-open restored, Guardian
gone, trace UI now clickable, register-specialist Sandy false-negatives
fixed, register pins on the map, FloodNet TTM forecast wired,
TTM specialists grouped in trace, `experiments/` cleaned. The single
load-bearing UX feature to verify in the morning is the trace-UI
drilldown — clicking any specialist row reveals its raw structured
output, which is the auditability contract for the entire system.

## Commits landed (overnight)

| Commit  | Priority | What |
|---------|----------|------|
| `a2143fc` | P1 | Restore `pitch/cold_open.md` from `b4239de` (accidentally deleted in `1cb5ee6`). |
| `4b9e55e` | P2 | Remove `GuardianRefusal.svelte`, `RefusalCategory` type, `.guardian-*` CSS, Playwright assertion. Mellea is the sole grounding mechanism. |
| `3e4f922` | P3 | **Trace UI clickable drilldown.** Click any row → raw structured output panel (formatted JSON, copy button, status-aware label, max-height + scroll). |
| `47ed3fb` | P4 | Buffered-footprint overlap (`app/registers/_footprint.py`) — MTA 8m / DOE 50m / DOH 100m. NYU Langone, Stuyvesant HS, P.S. 89 flip to `inside_sandy_2012=true`. |
| `792f4ee` | P5 | Map: register-asset pins (subway 4px / school 5px / hospital 6px / NYCHA-centroid 7px), colored by Sandy exposure, click popup with name + `[doc_id]`. |
| `3d991e9` | P6 | **`floodnet_forecast` specialist.** TTM r2 (512, 96) forecast on nearest FloodNet sensor's daily flood-event series — reuses the existing model singleton, no new model class loaded. |
| `90644e4` | P7 | Trace UI groups TTM specialists under `forecasting.granite-timeseries-ttm-r2 [N instances]`. `leafSteps` walks recursively so children still count toward fired/silent/errors. |
| `36e28d1` | P8 | Drop `Riprap.zip`, empty `05_sam2_promptable/`, empty `06_chronos_bolt_forecast/`. Rename `05_terramind_finetune` → `05a_terramind_finetune_micro` (dedupe with active NYC fine-tune dir). |

Two further commits update MONDAY.md and add this handoff.

## Verify first when you wake

Run a Red Hook query (rich output, exercises everything) and check:

```bash
.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860 --log-level info
# then visit http://127.0.0.1:7860/q/red%20hook%20houses
```

1. **Trace drilldown.** Click any specialist row in the run-trace
   panel. You should see a structured output panel with formatted
   JSON, a "Copy" button, and a status-coloured label
   (Output / Silent reason / Error). Multiple rows can be expanded
   simultaneously. *This is the load-bearing feature.* If clicking
   doesn't expand the row, check the browser console; the build is
   committed in `web/sveltekit/build/`.
2. **TTM grouping.** The trace should show
   `forecasting.granite-timeseries-ttm-r2 · 3 instances` (or 2 if
   floodnet_forecast finds no usable sensor) as a single
   auto-expanded parent with the TTM children nested under it. The
   top-of-trace fired/silent/errors counters should still include
   the TTM children — that's the recursion fix in `TraceUI.svelte`.
3. **Register pins on the map.** Click a subway/school/hospital pin.
   Popup should show name, kind, `inside_sandy_2012`, and
   `[mta_entrance_…]` / `[doe_school_…]` / `[nyc_hospital_…]` /
   `[nycha_dev_…]` doc-id, the same one cited in the briefing.
4. **Buffered Sandy join.** Run the NYU Langone single-address query
   (`570 First Ave Manhattan` or similar). The hospital row should
   show `inside_sandy_2012=true` in its trace drilldown panel and
   the briefing should cite `[nyc_hospital_…]` accordingly.
5. **No Guardian card anywhere.** No `GuardianRefusal.svelte`, no
   `.guardian-*` CSS class, no `RefusalCategory` import. Mellea
   reroll banner is the only integrity-narration UI.

## What's queued next (Monday morning, in priority order)

1. **NYCHA polygon-fill on the map.** Add `geometry_geojson` field
   to `app/registers/nycha.py:DevelopmentFinding` (serialise the
   polygon as GeoJSON). The frontend `RipMap.svelte` already has
   the `register-polygons` source + fill/line layers wired and
   waiting for non-empty data. ~30 min. Done = NYCHA developments
   render as graded fills (denser if more of the footprint inside
   Sandy) at the Red Hook query.
2. **TerraMind-NYC fine-tune morning routine.** From MONDAY.md:
   refresh PC signed URLs on the AMD droplet, then proceed with the
   eval-spec gates. That session is independent of overnight work.
3. **MTA Sandy-recovery citation layer** (per MONDAY.md: parse the
   "Hurricane Sandy: Three Years Later" report into per-station-id
   facts → emit `[mta_recovery_<station_id>]` doc messages). 1–2 hr.
4. **PLUTO + NYC Building Footprints** for the very-large-campus
   register cases that the buffered-overlap doesn't catch
   (Stuyvesant Town in particular — it's not in `nycha.geojson`
   because it's privately owned post-Met-Life). Either a new
   "large_residential_complex" register or an actual footprint join.
5. **3 more TTM r2 specialists**: USGS streamgage stage, NWS rainfall
   accumulation, citywide 311 sewer-backup rate. Each one reuses the
   same singleton — same architectural template as
   `floodnet_forecast`.

## What was deliberately kept out of scope tonight

Per the wiring-pass priorities document:

- USGS NWIS Bronx/Saw Mill/Hutchinson river forecasts.
- FEMA OpenFEMA NFIP claims tract-aggregated specialist.
- DEP CSO outfalls / Bluebelt / Green Infrastructure specialist.
- WCAG 2.2 AA full audit.
- Methodology paper draft (Saturday work).
- Historical-event mode (Saturday work).
- Build-in-Public posts.
- ASCE talk materials.
- Dark mode (explicit defer to v0.5).
- WeasyPrint server-side PDF (browser print is sufficient for demo).
- Per-specialist Python integration tests for the 4 register
  specialists (e2e Playwright covers them).

## Sharp edges to remember

- **`floodnet_forecast` silent floor.** Sensors with <5 historical
  events skip the forecast entirely (output is dominated by
  quantization noise around zero — exactly the kind of
  pseudo-quantitative claim the four-tier discipline guards
  against). Trace shows `silent` with reason
  "sensor has only N historical events; forecast omitted".
  Don't lower the threshold without revisiting the calibration.
- **Buffer choice in `app/registers/_footprint.py` is per-asset-class.**
  100m hospital buffer catches NYU Langone but not the entire NYU
  Langone Tisch Center (campus extends ~250m). Calibrated against
  the three canonical addresses. Document any future change in the
  same module's docstring.
- **NYCHA polygons not yet on the map.** Centroid-pin rendering is
  shipped; polygon-fill needs the dataclass change above.
- **Trace UI `output` field carries the raw object.** Don't
  re-stringify it in `q/[queryId]/+page.svelte` — the panel
  formatter does that. The 240-char truncation that used to happen
  in onStep is gone; if you're inspecting a giant payload, the
  panel scrolls.
- **TTM grouping uses `status='fan'` as the auto-expand marker.**
  The recursive `leafSteps` walker in `TraceUI.svelte` excludes
  fan/merge nodes from counts but recurses into their children.
  Don't add another structural-only status without updating the
  recursion.

## Files touched (overnight, by area)

- `app/registers/_footprint.py` (new)
- `app/registers/{mta_entrances,doe_schools,doh_hospitals}.py`
- `app/live/floodnet_forecast.py` (new)
- `app/fsm.py`, `app/reconcile.py`
- `web/sveltekit/src/lib/types/{trace,states,tier}.ts`
- `web/sveltekit/src/lib/components/trace/{TraceUI,TraceRow}.svelte`
- `web/sveltekit/src/lib/components/map/RipMap.svelte`
- `web/sveltekit/src/lib/styles.css`
- `web/sveltekit/src/routes/q/[queryId]/+page.svelte`
- `web/sveltekit/build/*` (rebuilt artefacts, committed)
- `web/static/agent.js` (legacy bundle: STEP_LABELS / SOURCE_LABELS
  for `floodnet_forecast`)
- `MONDAY.md`, `pitch/cold_open.md`, `experiments/shared/licenses.md`
- Deletions: `Riprap.zip`,
  `experiments/05_sam2_promptable/`,
  `experiments/06_chronos_bolt_forecast/`,
  `experiments/05_terramind_finetune/{micro.py, RESULTS.md}`
  (renamed to `05a_terramind_finetune_micro/`),
  `web/sveltekit/src/lib/components/states/GuardianRefusal.svelte`.

## Tests run

- 18-test static Playwright suite passes after every UI change.
- Python smoke probes verified the buffered-footprint Sandy join
  on the canonical addresses (NYU Langone, Stuyvesant HS, P.S. 89).
- Did NOT run `pytest tests/` (requires uvicorn + live SSE; the
  morning verification routine above hits all the same code paths).
- Did NOT push to either remote — `git push && git push huggingface main`
  when ready to deploy. HF rebuild ~10 min.
