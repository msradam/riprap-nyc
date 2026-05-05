# Phase 16 — Granite TimeSeries TTM r2 Battery Surge NYC fine-tune

## Goal

Fine-tune IBM's Granite TimeSeries TTM r2 (1.5M params, Apache 2.0)
specifically on multi-year NOAA Battery, Sandy Hook, and Kings Point
gauge data, replacing Riprap's current zero-shot TTM specialist with
a NYC-specialized version.

Demonstrates a THIRD foundation-model family on AMD MI300X (TerraMind
+ Prithvi + Granite TTM). Strengthens the "AMD handles entire IBM
Earth-observation stack" story.

TTM is 1.5M parameters — fine-tunes in ~5–30 minutes on MI300X.
Practically free GPU time.

## What Riprap currently does

`app/live/ttm_forecast.py` runs zero-shot TTM r2 to forecast the
*surge residual* (observed water level minus astronomical tide) at the
Battery for the next ~9.6 h. It feeds into the briefing as a live
signal.

The zero-shot model has never seen NYC tide gauge data specifically.
A NYC fine-tune should be MEASURABLY better at:
- The non-stationary surge response patterns specific to NY Harbor
- The interaction between wind direction (from NWS) and surge
- The compound-event regime (storm surge + spring tide + heavy rain)

## Why TTM, not a deep learning model from scratch

- Already in Riprap's stack, one-line swap-in via the same call signature
- 1.5M params trains in minutes — five minutes of GPU and we have
  a published checkpoint
- IBM publishes the cookbook (`granite-timeseries-cookbook`) with the
  exogenous-variable fine-tune recipe we need

## Data

- **NOAA CO-OPS API** (free, no auth): pull 6-min observed water
  level + predicted astronomical tide for Battery (8518750), Kings
  Point (8516945), Sandy Hook (8531680) for the last 5 years.
- Compute residual = observed - predicted per timestep.
- Split: 70% train / 15% val / 15% test, by time (no leakage).

For exogenous variables (TTM r2 supports them out of the box):
- Wind speed + direction from NWS METAR (KNYC, KLGA, KJFK, KEWR, KFRG)
- Atmospheric pressure
- Recent rainfall (1 hr trailing sum)

## Plan

1. Scaffold (this file).
2. Write `pull_noaa.py` — fetch 5 years of 6-min Battery data.
3. Write `pull_metar.py` — fetch 5 years of NYC airport METAR for
   exogenous variables.
4. Write `prepare_ttm_dataset.py` — align timestamps, split, scale.
5. Use the existing TTM r2 fine-tune recipe from
   `granite-timeseries-cookbook/recipes/Time_Series/Bike_Sharing_Finetuning_with_Exogenous.ipynb`,
   adapted for our (residual, exogenous) shape.
6. Fine-tune (~20 min wall-clock on MI300X).
7. Compare zero-shot TTM vs fine-tuned TTM on the held-out test split.
   Metrics: MAE, RMSE on the 9.6 h horizon residual prediction.
8. Publish as `msradam/Granite-TTM-r2-NYC-Surge`.

## Eval gate

Strong: > 10% RMSE reduction vs zero-shot on test split.
Acceptable: ≥ 5% RMSE reduction.
Negative: < 5% improvement (or worse) → publish "zero-shot is hard
to beat for surge residual" as honest result.

## Risk

Low. TTM cookbook is well-documented; 1.5M params is trivial to
fine-tune. The data engineering is the harder part (NOAA + NWS data
pull and alignment).

## What it adds to Riprap

`app/live/ttm_forecast.py` currently calls zero-shot TTM. Replace
with the fine-tuned checkpoint via a single model-id swap. The
forecast becomes meaningfully better at NY Harbor specifically.

## Reproduction (planned)

```bash
python3 experiments/16_ttm_battery_nyc/pull_noaa.py
python3 experiments/16_ttm_battery_nyc/pull_metar.py
python3 experiments/16_ttm_battery_nyc/finetune_ttm.py --epochs 10
```
