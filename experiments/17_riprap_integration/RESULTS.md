# Phase 17 — Riprap end-to-end integration of all NYC AMD fine-tunes

## Goal

Wire the four AMD-trained NYC fine-tunes (Phase 2 LULC + Phase 12 TiM
+ Phase 13 Buildings + Phase 14 Prithvi-NYC + Phase 16 TTM-NYC) into
Riprap's existing FSM as production specialists. The hackathon
submission then demonstrates the full briefing flow with all six
foundation models running locally on AMD.

This experiment is the *deployment story* — taking the published HF
checkpoints and showing them serve real Riprap queries, not just the
isolated Gradio demo.

## Scope

NOT a fine-tune. Pure integration work — porting code from
`experiments/05_terramind_nyc_finetune/publish/space/local_app.py`
into Riprap's `app/` modules with proper FSM hooks.

## What gets touched

### New specialists

`app/context/sentinel_live.py` — `fetch_recent_chips(lat, lon)` from
Earth Search (S2 + DEM) + PC (S1 RTC), with multi-source fallback and
per-MGRS-cell cache. From experiments/11_live_sentinel_fetch.

`app/context/terramind_nyc.py` — wraps the AMD-trained NYC LULC + TiM
+ Buildings checkpoints. Returns a single dict with class fractions,
imperviousness, building density, and freshness disclosures. Replaces
`app/context/terramind_synthesis.py`'s zero-shot path while keeping
the same output schema for backward compatibility.

### Modified specialists

`app/flood_layers/prithvi_water.py` — gains a `prithvi_live` mode that
uses the Phase 14 NYC pluvial fine-tune on a freshly-fetched S2 chip,
in addition to the existing point-in-polygon test against
`prithvi_ida_2021.geojson`.

`app/live/ttm_forecast.py` — model-id swap from zero-shot TTM r2 to
the Phase 16 NYC-fine-tuned variant.

### FSM updates

`app/fsm.py:step_terramind` already exists; just point it at
`terramind_nyc` instead of `terramind_synthesis`. No new action
needed — the dict shape matches.

`app/reconcile.py:579-608` (the TerraMind doc-message block) updates
the framing from "tentative ESRI labels" to "WorldCover macro-classes
(confirmed) + AMD-trained NYC fine-tune". Drops the "tentative"
disclaimer since labels are now real ground truth.

### Tests

`tests/test_terramind_nyc.py` — three NYC reference points (Manhattan
center, Brighton Beach, Bronx Zoo). Expected class distributions
(Manhattan should be ≥70% developed; Brighton Beach should have ≥10%
water; Bronx Zoo should have ≥15% forest). Mock the live Sentinel
fetch in CI.

## Success criteria

- A real Riprap query for "Empire State Building" returns a briefing
  whose `terramind_nyc` doc body cites:
  - imperviousness (= developed%)
  - green-space %
  - water %
  - building-density % (if Phase 13/15 lands)
  - flood-prediction % (if Phase 14 lands)
  - S2 acquisition age in days
  - S1 acquisition age in days
- The reconciler's Mellea grounding pass succeeds on those numbers.
- The full flow runs in < 12 s end-to-end, including the live Sentinel
  fetch (~5 s) plus all 14 specialists (~6 s) plus reconciliation.

## Plan

1. Scaffold (this file).
2. Port `local_app.py` chip-fetch + inference logic into
   `app/context/terramind_nyc.py`. Mirror the dict shape from
   `app/context/terramind_synthesis.py:fetch()`.
3. Port the live Sentinel multi-source fetch from Phase 11 into
   `app/context/sentinel_live.py`.
4. Wire `step_terramind` in `app/fsm.py` to use the new module.
5. Update `app/reconcile.py` framing (drop "tentative" disclaimer
   when `label_schema` says "confirmed").
6. Add unit tests for the new modules in `tests/`.
7. Run a smoke briefing for "2940 Brighton 3rd St, Brooklyn" (the
   existing worked example in ARCHITECTURE.md §3.2). Confirm the new
   sentence appears in the briefing.
8. Update ARCHITECTURE.md §7 to add TerraMind-NYC + the AMD-fine-tune
   provenance line.

## What this enables for the submission

A judge clicking through the Riprap UI sees:
- Type address → live trace shows `step_terramind_nyc` running with the
  AMD-fine-tuned ckpt loading
- The briefing paragraph cites imperviousness, green-space %, building
  density — with `[terramind_nyc]` citations
- The bottom-of-briefing "what models powered this" section lists six
  foundation models, one of them flagged AMD-trained
- The MapLibre overlay shows the predicted LULC polygons

That's the demo for the video.

## Risk

Low. All the heavy ML is done by this phase; this is just plumbing.
Estimated half-day for a clean port.

## Reproduction (planned)

```bash
# After fine-tunes published to HF:
git pull origin main   # latest Riprap with the integration
RIPRAP_TERRAMIND_VARIANT=nyc \
RIPRAP_PRITHVI_VARIANT=nyc \
RIPRAP_TTM_VARIANT=nyc \
.venv/bin/uvicorn web.main:app --port 7860
```
