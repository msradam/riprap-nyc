# Phase 1 — Prithvi-EO 2.0 (Sen1Floods11 fine-tune) live water segmentation

## Status

**Working end-to-end on three NYC test addresses, both backends.**

## Model

- **Model:** `ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11`
- **Base:** Prithvi-EO 2.0 (300 M params, ViT encoder)
- **Head:** UperNet decoder fine-tuned on Sen1Floods11 (446 chips, 11 flood
  events, 6 continents)
- **License:** Apache-2.0 (verified against `LICENSE` file in the repo)
- **Loader:** `terratorch.cli_tools.LightningInferenceModel` via the
  upstream `inference.py` helper (we don't reimplement the
  preprocessing — datamodule transforms + standardization come from
  the model repo's own script).

## Pipeline

1. **`fetch_s2_chip.py`** — pulls a 6-band 1024×1024 Sentinel-2 L2A chip
   from Microsoft Planetary Computer for a (lat, lon). Bands: B02, B03,
   B04, B8A, B11, B12 in that order. Reprojects and pixel-aligns 20 m
   bands to the 10 m reference. Cached by (lat, lon, date-window).
2. **`infer_water.py`** — center-crops to 512×512 (the Sen1Floods11
   training size), scales by /10000, runs the upstream `run_model()`
   helper which handles standardization + sliding-window inference.
   Returns binary water mask, % water within a 500 m circle of the
   point, % water across the 5 km chip, and an RGB+mask overlay PNG.
3. **`emit_doc.py`** — packages the result into a
   `role: "document prithvi_live"` chat message with a key:value body
   that Granite 4.1 can ground against. doc_id format: `prithvi_live`.
4. **`run_double_gate.py`** — single-script smoke test of the whole
   pipeline + two parallel reconciler calls (Ollama + vLLM).

## Three-address validation

S2 scene picked in all three cases: `S2A_MSIL2A_20240903T153941`
(2024-09-03, < 0.03% cloud cover).

| Address | %water 500 m | %water 5 km | Plausibility |
|---------|-------------:|------------:|--------------|
| Brighton Beach (coastal)  | 0.19 % | 39.34 % | OK — address is on a dry block 2 blocks inland; chip captures Atlantic + Coney Island Creek |
| Hollis (pluvial inland)   | 0.00 % | 0.02  % | OK — Hollis is far from any surface water; the model correctly returns near-zero |
| Hunts Point (peninsula)   | 3.70 % | 23.37 % | OK — peninsula site, 500 m circle clips the Bronx River; full chip catches the East River |

The "silence over confabulation" pattern from the existing offline
Prithvi specialist holds: in Hollis the model emits ~0 % and the
reconciler simply states 0.00 % rather than inventing exposure.

## Double-gating

`run_double_gate.py` ran each address against both backends. Granite
4.1 8B asked to write a single cited sentence from the doc.

| Address | Ollama (M-series CPU/MPS) | vLLM (AMD MI300X) |
|---------|---------------------------|-------------------|
| Brighton Beach | **9.93 s** — *misread 0.19% as 19%* | **0.54 s** — correct |
| Hollis         | 5.04 s — correct (0.00 %), citation placement awkward (mid-token) | 0.60 s — correct |
| Hunts Point    | 4.52 s — correct (3.70 %) | 0.50 s — correct |

**Inference latency (Prithvi forward pass):** 7.8 – 10.3 s on M3 Pro
MPS, single chip. Cold each run because we restart Python; in the FSM
the model would stay loaded and amortize.

### Findings worth remembering

1. **Ollama's Granite 4.1 8B occasionally misreads small decimals.** On
   Brighton Beach it rendered `0.19%` as `19%` — a 100× error. The same
   prompt on vLLM produced the correct value. Possibly a tokenizer or
   sampling-temperature interaction; vLLM at temp=0 was deterministic.
   **Mitigation when this lands in production:** the existing Mellea
   `numerics_grounded` check would catch it (the haystack contains
   "0.19", not "19") and trigger a reroll. We don't need a separate
   guard, but we should re-probe with the production reroll loop on
   hand to confirm.

2. **vLLM is ~10× faster than Ollama on this prompt size.** Across all
   three addresses, vLLM averaged 0.55 s vs Ollama's 6.5 s. With
   citation-pass on first try, the AMD path is comfortably under the
   5 s/specialist demo budget; Ollama is borderline.

3. **Prithvi cold-load takes ~6 s** of the per-call latency in
   `run_double_gate.py` (model checkpoint + datamodule init). In
   production we'd load once at app boot — same pattern as the offline
   Prithvi specialist.

4. **`load_example` upstream / preprocessing parity.** The first naive
   port misinterpreted the model's `ModelOutput` and ran without the
   datamodule's standardization, producing 0% water everywhere. Always
   route through the upstream `run_model()` helper. The helper expects
   `(B, C, T, H, W)` shape (single timestamp = T=1) and applies the
   training-time normalization.

5. **Demo-safe over urban tiles.** No spurious water hits on Hollis or
   the Brighton dry block. Did not yet stress-test over dense Manhattan
   grid (next phase if needed) — flagging the brief's specific concern.

## Open work for integration

If we decide to land this in `app/`:

- **NTA-level baseline.** Phase 1 emits `nta_baseline_pct: null` so the
  reconciler refuses to make a comparative claim. To make the doc
  carry a "vs typical" sentence we need a one-time offline median over
  ~1 year of cloud-free S2 medians per NTA (~250 NTAs × ~12 monthly
  composites; multi-hour STAC + inference job). Output to
  `data/baselines/nta_water_baseline.parquet`. Not blocking for the
  demo if the doc says "0.19 % water observed today" without a delta.

- **Cloud-cover gate.** Doc emission should refuse to write when the
  chosen scene's `eo:cloud_cover` is above e.g. 20 %, since
  Sen1Floods11 was trained on near-cloud-free imagery. Currently we
  search with `<30%` and just take the lowest-CC scene; a hard refuse
  + UI "no recent clear-sky observation" message would be more
  honest.

- **Trace UI.** The structured trace card we mocked
  (`shared/trace_render.py`) renders cleanly. Production needs an
  `<r-prithvi-overlay>` Svelte component that displays the RGB+mask
  thumbnail; ~30 lines of Svelte over the existing pattern.

- **Caching.** Per-(lat, lon, date) S2 chip + mask should live in a
  small SQLite/disk cache so the same address re-queried within a
  ~3 day TTL doesn't re-segment.

## Files in this experiment

```
01_prithvi_live_water/
  fetch_s2_chip.py      6-band S2 chip from Microsoft Planetary Computer
  infer_water.py        Prithvi-EO 2.0 inference wrapper
  emit_doc.py           build prithvi_live document message
  run_double_gate.py    end-to-end + paired Ollama/vLLM probe
  RESULTS.md            (this file)
  .cache/               chips, masks, overlay PNGs, double_gate_*.json
```

## Conclusion

Specialist works on both backends with sane outputs across all three
NYC test addresses. **AMD MI300X is comfortably fast (≤1 s reconcile);
Ollama is borderline and needs the existing Mellea reroll loop to
guard against decimal-misreading.** Recommended path forward: integrate
behind the existing `app/flood_layers/` convention (additive to the
offline Prithvi specialist; new doc_id `prithvi_live`), gated by the
cloud-cover refuse rule, with the NTA baseline tracked as a follow-up.
