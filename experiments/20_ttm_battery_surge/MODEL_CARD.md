---
license: apache-2.0
base_model: ibm-granite/granite-timeseries-ttm-r2
library_name: granite-tsfm
pipeline_tag: time-series-forecasting
tags:
  - time-series
  - storm-surge
  - tide-gauge
  - noaa
  - nyc
  - new-york
  - hurricane-sandy
  - hurricane-ida
  - granite
  - ttm
  - amd
  - rocm
---

# Granite-TTM-r2-Battery-Surge

NYC-specific fine-tune of IBM Granite TimeSeries TTM r2 (1.5M params)
for storm-surge residual nowcasting at NOAA tide gauge 8518750
(The Battery, lower Manhattan). Trained on AMD Instinct MI300X via AMD
Developer Cloud. Apache 2.0.

## What this predicts

Given the past 1024 hours (~43 days) of surge residual at The Battery,
predict the next 96 hours (4 days). Surge residual is verified water
level minus the harmonic tide prediction, so the model is forecasting
the deviation from astronomical tide. That deviation is dominated by
weather (storm surge, atmospheric pressure, wind setup), which is
exactly what an emergency planner cares about for flood-exposure
nowcasts.

## Result

Test split: chronologically held-out (last 15% of 2015-2024 = 2023-2024
windows), 12,033 sliding 1024-in / 96-out windows. No leakage.

| Configuration | Test MAE (m) | Test RMSE (m) |
|---|---:|---:|
| Persistence baseline (next 96h = last value) | 0.1861 | 0.2417 |
| Zero-shot TTM r2 (no fine-tune) | 0.1467 | 0.1903 |
| **Fine-tuned TTM r2 (this work)** | **0.1091** | **0.1568** |

**Improvement over persistence baseline:** -41.4% MAE, -35.1% RMSE.
**Improvement over zero-shot TTM r2:** -25.6% MAE, -17.6% RMSE.

The zero-shot result is a meaningful finding on its own: TTM r2 is
already 21% better than the trivial persistence baseline at 96h Battery
surge forecasting before any NYC-specific training. Fine-tuning closes
another quarter of that residual error, mostly by learning NYC-specific
storm patterns (Atlantic nor'easter dynamics, river freshwater pulses,
basin geometry effects).

## Why this exists

NYC's deadliest historical floods — Sandy 2012, Ida 2021 — were both
surge-driven (Sandy: coastal storm surge stacked on king tide; Ida:
pluvial accumulation, with The Battery still showing measurable surge
residual). Riprap, the parent NYC flood-exposure briefing system, uses
this nowcast as one of several signals in its live water-level
specialist. Hourly surge residual + 96h forecast is the right shape:
short enough that the forecast is actionable for today/tomorrow, long
enough to flag building patterns 3-4 days out.

## Training data

- Source: NOAA CO-OPS API station 8518750 ("The Battery, NY")
- Range: 2015-01-01 to 2024-12-31 (10 years)
- Granularity: 6-min interval verified water level + harmonic tide
  predictions, resampled to hourly mean for training
- Samples: 87,672 hourly observations
- Surge residual range: -1.109 m to +1.591 m (with Sandy 2012 outside
  this range, by design — Sandy is in the 2012 record, not in our
  2015-2024 training distribution)
- Surge residual std: 0.224 m

Splits: chronological (no random shuffling, since adjacent timestamps
leak):
- train: 60,251 windows (first 70% of timeline)
- val: 12,031 windows (next 15%)
- test: 12,033 windows (final 15%)

## Architecture

| | |
|---|---|
| Backbone | TinyTimeMixer r2, revision `1024-96-r2` |
| Context length | 1024 hours (~43 days) |
| Prediction horizon | 96 hours (4 days) |
| Input channels | 1 (univariate surge residual) |
| Total params | ~1.5 M |
| Frozen | none (full fine-tune; tiny model, no need for PEFT) |

## Training procedure

| | |
|---|---|
| Framework | granite-tsfm 0.3.6 + transformers 4.57 + PyTorch Lightning |
| Hardware | 1× AMD Instinct MI300X (192 GB HBM3) |
| Cloud | AMD Developer Cloud |
| ROCm | 4.0.0+1a5c7ec |
| Precision | fp16-mixed |
| Optimizer | AdamW, lr 1e-4 |
| Scheduler | early-stopping on eval_loss |
| Batch | 64 |
| Epochs | 20 (max), best at val_loss minimum |
| Seed | 42 |
| Wall-clock | ~10 min |

## Inference

```python
from tsfm_public import TinyTimeMixerForPrediction
from huggingface_hub import snapshot_download
import torch

# 1. Pull this fine-tune.
ft_dir = snapshot_download("msradam/Granite-TTM-r2-Battery-Surge")

model = TinyTimeMixerForPrediction.from_pretrained(ft_dir).eval()

# 2. Build a [B, 1024, 1] tensor of past surge residuals (in metres).
#    Each row is one window of 1024 consecutive hourly residuals.
past = torch.tensor(your_residuals, dtype=torch.float32)  # [B, 1024]
past = past.unsqueeze(-1)                                  # [B, 1024, 1]

# 3. Forecast 96 hours ahead.
with torch.no_grad():
    out = model(past_values=past)
forecast = out.prediction_outputs.squeeze(-1)              # [B, 96]
```

To use NOAA Battery data directly, fetch live from
https://api.tidesandcurrents.noaa.gov/api/prod/datagetter at station
8518750, products `water_level` (6-min) and `predictions` (hourly), then
compute `water_level - predicted` as surge residual.

## Honest limitations

- **Historical distribution.** Training data ends 2024-12-31. Sandy
  (2012) and Ida (2021) are NOT in the training distribution; Ida is
  in the val/test splits because the train/val/test split is
  chronological 70/15/15 and Ida falls within the test window. Sandy
  is pre-2015 and not in this dataset at all. We did not specifically
  augment with extreme events.
- **Univariate.** Single-channel (surge residual only). No
  meteorological covariates (wind, pressure, precipitation) are passed
  in. Adding them would likely improve hurricane-event tails but
  requires multivariate fine-tuning; deferred to future work.
- **Nowcast, not climate.** This forecasts the next 96 hours. It
  is NOT a multi-decade sea-level-rise projection.
- **The Battery only.** Not transferable to other tide gauges without
  retraining. Other NYC stations (Kings Point, Sandy Hook, Bergen
  Point) would each need their own fine-tune.
- Single training run; no multi-seed averaging. Reported metrics have
  implicit confidence intervals.

## License

Apache 2.0. Underlying training data:
- NOAA Battery (NY) station 8518750 verified water-level and harmonic
  tide predictions are public-domain U.S. government data
  (NOAA CO-OPS API).

## Citation

```bibtex
@misc{granite-ttm-2024,
  title={Tiny Time Mixers (TTM): Fast Pre-trained Models for Enhanced Zero/Few-Shot Forecasting of Multivariate Time Series},
  author={Ekambaram, Vijay and others},
  year={2024},
  publisher={IBM Research},
}

@misc{ttm-battery-2026,
  title={Granite-TTM-r2-Battery-Surge: NYC tide-gauge surge fine-tune on AMD MI300X},
  author={Rahman, Adam Munawar},
  year={2026},
  publisher={Hugging Face},
  url={https://huggingface.co/msradam/Granite-TTM-r2-Battery-Surge},
}
```
