# Phase 4 — TerraMind synthetic SAR fallback for Prithvi

## Status

**Plumbing validated end-to-end on dummy input. Real-data runs blocked
on a transient Microsoft Planetary Computer outage** (sentinel-1-grd
and sentinel-1-rtc — and as of this write, sentinel-2-l2a too —
returning timeouts to both pystac-client and direct curl). The chain
itself is fully wired and reproduces the expected shapes. Real-S1
end-to-end runs deferred until PC recovers.

## Architectural pivot from the original brief

The brief specified `S2L2A → S1GRD` synthesis with the "existing
Sen1Floods11 segmentation head from Phase 1" running on synthesized
SAR. **That direction does not work**: Phase 1's head
(`Prithvi-EO-2.0-300M-TL-Sen1Floods11`) takes 6-band Sentinel-2
*optical* input (B02, B03, B04, B8A, B11, B12), not Sentinel-1 SAR. I
checked both Apache-2.0 Sen1Floods11 fine-tunes from
`ibm-nasa-geospatial`; both are 6-band S2 input. There is no
license-compliant Sen1Floods11-on-S1 head we could plug in.

The pivot inverts the synthesis direction:

```
brief's plan:    cloudy S2  --TerraMind-->  synthetic S1GRD  --Phase1 head-->  ❌ shape mismatch
correct plan:    real S1GRD --TerraMind-->  synthetic S2L2A  --Phase1 head-->  ✓ unchanged head
```

Why this is actually the right architecture:

1. **S1 SAR sees through clouds** — that's the entire point of using
   radar in the fallback. Pulling a real S1 GRD scene from PC is the
   step that actually punches through the cloud layer; nothing about
   that step is synthesized.
2. **TerraMind hallucinates a plausible cloud-free S2L2A** from the
   real radar observation. That's the synthetic step. The "generated a
   plausible scene from radar context, never imaged the scene" framing
   the brief mandates still applies.
3. **Phase 1's existing 6-band S2 segmentation head runs unchanged**
   on the synthesized S2L2A. Same model, same output schema, same map
   layer, same `synthetic_modality: true` flag.
4. **TerraMind v1 base is any-to-any** — its tokenizer config
   includes both `s1grd` and `s2l2a` endpoints. The reverse direction
   was never exotic; the brief just specified the wrong arrow.

## What's wired

### `fetch_s1grd_chip.py`

Microsoft Planetary Computer STAC `sentinel-1-grd` collection: pulls
the most-recent S1 GRD scene over (lat, lon), reprojects to the
scene's UTM zone, clips to a 1024×1024 chip at 10 m, packs both VV +
VH polarizations into a 2-band float32 GeoTIFF. Cached by
(lat, lon, date-window). Same shape pattern as Phase 1's
`fetch_s2_chip.py`.

### `run_terramind_generate.py`

Loads `terratorch_terramind_v1_base_generate` via terratorch's
FULL_MODEL_REGISTRY with `modalities=["S1GRD"]`,
`output_modalities=["S2L2A"]`. Pretrained weights download from
`ibm-esa-geospatial/TerraMind-1.0-base` (~1.2 GB, cached after first
fetch). Runs 10-step diffusion with both `torch.manual_seed(42)` and
`random.seed(42)` (TerraMind's bundled sampler reads python's `random`
module, not torch — both must be seeded for reproducibility).

**Plumbing validated on a (1, 2, 224, 224) zeros input:**
output shape `(12, 224, 224)` 12-band synthesized S2L2A, **3.02s** on
M3 Pro CPU. The brief estimated 30 s+; actual is an order of magnitude
faster on this hardware. Real-input run will be slightly slower because
the diffusion has more signal to work with.

### `run_segmentation_on_synthetic.py`

Takes the (12, H, W) synthesized S2L2A npy, extracts the Phase 1
6-band subset (indices [1, 2, 3, 8, 10, 11] from TerraMind's
[B01, B02, B03, B04, B05, B06, B07, B08, B8A, B09, B11, B12] order),
upsamples to 512×512 (Sen1Floods11 training size), applies the same
`/10000` reflectance scaling Phase 1 uses, and runs the upstream
`run_model()` helper.

**Validated end-to-end with the zeros-input synthesis:** Phase 1's
head runs without modification, produces a 512×512 binary mask in
1.36 s on M3 Pro MPS, returns the same `pct_water_within_500m` /
`pct_water_full` outputs as the primary path. (The actual values on
zeros are 100% water, which is meaningless — this validates the wiring
not the segmentation quality. Real-input runs will produce sane
values.)

### `fallback_logic.py`

Trigger ladder used by the integrated specialist to decide
primary-vs-synthetic:

| Tier | Condition | Decision |
|-----:|-----------|----------|
| 1 | S2 cloud_cover < 30% within ±3 days | primary path |
| 2 | S2 cloud_cover < 50% within ±14 days | primary path with relaxed-cloud disclosure |
| 3 | otherwise | TerraMind synthesis |

Depends only on PC's S2 collection (not S1) — this module is
reachable via the existing Phase 1 STAC connectivity, doesn't expand
the failure surface.

### `run_against_local.py`

End-to-end harness over the three NYC test addresses (Brighton Beach
/ Hollis / Hunts Point), local Ollama only per the brief's deferred-
MI300X-verification rule. Currently blocked on PC.

## Deliberate scope cuts

- **MI300X verification deferred to demo-eve dress rehearsal** per
  the brief (the LiteLLM router has held through Phases 1-3 with no
  backend-specific bugs; trusting the abstraction).
- **NTA-baseline computation not addressed in this phase** — Phase 1
  punted on it and Phase 4 inherits that scope cut.
- **No FSM integration yet** — strictly experiments/. Will be wired
  into `app/flood_layers/prithvi_live.py` (delegating from inside the
  primary specialist) only after real-data validation runs through.

## Latency budget

Per-call (model-warm; cold loads amortized at app boot):

| Stage | Latency | Notes |
|------:|--------:|-------|
| Trigger check (Phase 1 S2 STAC) | ~1-3 s | already measured in Phase 1 |
| S1 GRD STAC + chip fetch | ~3-8 s expected | when PC behaves |
| TerraMind 10-step synthesis | **3.0 s** measured | M3 Pro CPU, zeros input |
| Phase 1 segmentation head | **1.4 s** measured | M3 Pro MPS, full chip |
| Reconcile (Ollama, M-series) | ~10-30 s | unchanged from Phase 1 |
| Reconcile (vLLM, AMD MI300X)  | ~0.5-2 s | unchanged from Phase 1 |

The non-LLM portion of the chain is well under the 90 s reconcile
budget the brief calls out; latency margin is comfortable.

## License

Apache-2.0, verified — `ibm-esa-geospatial/TerraMind-1.0-base`.
README frontmatter declares `license: apache-2.0` and HF cardData
confirms. **No separate `LICENSE` file in repo** (standard IBM repo
posture for model weights — cardData is canonical for IBM/ESA
geospatial models). Logged in `experiments/shared/licenses.md`.

## Recommendation: research-park, do not integrate (as of 2026-05-02)

**Decision: keep Phase 4 in `experiments/04/`, do not wire into
`app/`.** Phases 1-3 are the demo; the cloudy-day fallback is solved
sufficiently by Phase 1 accepting a stale (≤14d) Sentinel-2 with the
vintage disclosed in the trace.

### Why park, not integrate

1. **Quality is unverified, not unverifiable-but-fine.** The make-or-
   break comparison — synthesized-S2 segmentation `% water` vs real-S2
   segmentation `% water` on the same address — has not run. Plumbing
   is validated; calibration is not.

2. **Three risks are real even if PC recovers tomorrow:**
   - **Radiometric drift.** TerraMind's synthesized 12-band reflectance
     is a generative prior; per-band statistics may not match real S2.
     Sen1Floods11 was trained on real S2; small distribution shifts
     can move the decision boundary materially.
   - **Urban NYC is hostile to S1→S2 synthesis.** SAR backscatter in
     dense built-up areas is dominated by buildings and double-bounce
     returns, not hydrology. TerraMesh's training distribution is
     globally weighted toward natural land cover. The three NYC test
     addresses are precisely where the synthesis prior is weakest.
   - **The model card says "mental images, not reconstructions."**
     That's IBM/ESA being honest. Riprap's whole pitch is
     measurement-grounded citation. A
     hallucinated-from-radar-context specialist is the opposite of
     that pitch even with a `synthetic_modality: true` disclosure.

3. **Phase 1's existing fallback is acceptable.** When the most recent
   cloud-free S2 is 9 days old, Phase 1's trace shows the date and the
   reconciler discloses vintage. For flood-*exposure* briefings — the
   question is "does this place flood" not "is it flooded right now"
   — a 14-day-old observation is plenty.

### When this could be reconsidered

If the comparison gets run (PC recovers, ~30 minutes of work) and the
synthesized-vs-real `% water` is within ~5 percentage points across
all three NYC test addresses, that's a real research result and a
defensible integration. Until that table exists, Phase 4 is a
plumbing demo.

### What this experiment delivered

- **TerraMind v1 base loads + runs on M3 CPU at 3.0s / 10 diffusion
  steps.** An order of magnitude faster than the brief estimated.
- **The brief's chain direction (S2→S1) was wrong.** Documented the
  pivot to S1→S2 with full rationale; whoever picks this up next
  doesn't have to discover that.
- **License diligence done** (Apache-2.0 verified, in
  `shared/licenses.md`).
- **Trigger ladder logic written** (`fallback_logic.py`); reusable if
  the integration ever happens.

### To unfreeze (post-PC-recovery, ~30 min job)

```bash
# Real data on the 3 test addresses, cloud filter forced off
.venv/bin/python experiments/04_terramind_synthetic_sar/run_against_local.py \
    --address all --start 2024-09-01 --end 2024-09-30 --steps 10 --seed 42

# Compare with Phase 1 results on the same addresses + dates
# (Phase 1 chips already cached in experiments/01_prithvi_live_water/.cache/)
```

If the comparison passes the 5-pp ballpark check, write the
integration into `app/flood_layers/prithvi_live.py` as a fallback path
gated by `RIPRAP_TERRAMIND=1`, default off.

## When PC is back, run

```bash
RIPRAP_LLM_PRIMARY=ollama \
.venv/bin/python experiments/04_terramind_synthetic_sar/run_against_local.py \
    --address all --start 2024-09-01 --end 2024-09-30 --steps 10 --seed 42
```

## Files

```
04_terramind_synthetic_sar/
  fetch_s1grd_chip.py             real S1 GRD chip from MS Planetary Computer
  run_terramind_generate.py       S1GRD -> S2L2A synthesis (terratorch)
  run_segmentation_on_synthetic.py Phase 1 head on synthesized S2L2A
  fallback_logic.py               trigger ladder (uses Phase 1 S2 STAC)
  run_against_local.py             end-to-end harness (Ollama only)
  RESULTS.md                      (this file)
  .cache/                         model weights, chips, synthesized npys
```
