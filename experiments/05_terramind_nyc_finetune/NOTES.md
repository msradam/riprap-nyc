# TerraMind-NYC fine-tune — session log (Sunday 2026-05-03)

## Where things live

- **Droplet:** `129.212.182.52` (root, key auth). MI300X, gfx942, 192 GiB
  VRAM. Other droplet `165.245.134.44` was unreachable at prep time.
- **Container:** `terramind` (rocm:latest, `sleep infinity`). Bind-mounts
  `/root/hf-cache` only. Files are pushed in via `docker cp`. Keep this
  container alive — terratorch 1.2.7 is installed in its system Python.
- **Host workdir:** `/root/terramind_nyc/` — manifests, chip cache, scripts.
- **Repo mirror (this dir):** every host script also lives here so the work
  is in git. `data/chips/` is gitignored (1305-pair × 224×224 × 14-band
  cache will be ≥4 GB once the pipeline is fixed).

## vLLM stopped — GPU is free for training

User authorized stopping the production `vllm` container. **Restart with
`docker start vllm` after training/eval is complete and the integration
decision is made.**

## Manifest

- 1305 paired `(S2L2A, S1RTC)` records, 2021-05 → 2026-04, NYC bbox,
  ≤ 30 % cloud, S2/S1 within ±3 days.
- 5 cloudy April-2026 holdout records.
- Pre-signed URLs expire ~1 h. Refresh via `python3 build_manifest.py`
  inside the container before each extraction batch.

## Encoder smoke — PASSING

```
[smoke] device=cuda  GPU=AMD Instinct MI300X  VRAM=205.8 GB
[smoke] loaded in 1.9 s; params=87.3 M
[smoke] forward 2900 ms -> 12 outputs, each (1, 196, 768)
```

Note: this is the **encoder** smoke. The actual fine-tune target
(`terramind_v1_base_generate`, the diffusion-sampler head used for
S2 → S1 synthesis) has *not* been smoke-tested yet. Backward pass +
optimizer step + checkpoint save also not yet exercised. That's the
remaining smoke-gate item once data is unblocked.

## Data pipeline — KNOWN BUG, not yet fixed

`data/extract_chips.py` was iterated through three anchor strategies
this evening:

1. **Scene-center anchor (original):** ~50 % of chips landed on no-data
   raster corners or open ocean.
2. **NYC-center lat/lon (-73.97, 40.72) reference:** 6/10 zero —
   Sentinel-2 tile bboxes are looser than the actual UTM raster
   footprints; many tiles only barely overlap NYC.
3. **Manhattan-ref filter (`scene_contains_reference`) + Manhattan
   anchor:** the filter correctly narrowed to MGRS tile T18TWL, but
   Manhattan UTM (≈585 600 E in zone 18N) lands at the *western
   overlap edge* of T18TWL's data extent. The chip window falls outside
   the raster's actual footprint and rasterio's `boundless=True` returns
   pure zero-fill. **All S2 reads in the latest run returned 100 %
   zero.** S1 reads worked sometimes (different CRS, different extents).

The right fix (not implemented yet):

- Open the S2 anchor band first; project NYC bbox into the raster's UTM;
  intersect with `src.bounds`; place the chip at the centroid of that
  intersection. Data-driven, avoids the lat/lon → raster-bbox mismatch.
- Add a post-extraction guard: skip chips whose S2 or S1 stack is
  > 50 % zero, log them in `extract_summary.json`.

Plus PC API hardening:

- STAC `get_item` was timing out > 50 % of the time during this
  Sunday-evening session (possibly upstream maintenance / load). Retry-
  with-backoff is in place. If it persists Monday morning we should
  fall back to using the manifest's signed URLs directly and only
  re-sign on 403.

## Gate status (per the user's prompt)

| Gate | Status |
|---|---|
| `eval/eval_spec.md` locked before training | ✅ done |
| Data pipeline validated on 10 sample pairs | ❌ blocked on bug above |
| 100-step training smoke clean | ❌ blocked on data pipeline |

## Recommended Monday-morning resume order

1. Refresh manifest URLs (`python3 build_manifest.py` inside container).
2. Patch `extract_chips.py`:
   - Replace lat/lon anchor with `(NYC_bbox ∩ raster.bounds)` UTM
     centroid (data-driven).
   - Add the `> 50 % zero-fill` post-extraction skip.
3. Re-extract 10 sample pairs; visually QA the panel PNGs (S2 RGB,
   S1 VV, S1 VH side-by-side). Confirm the same NYC features
   (bridges, harbor, parks) appear in both modalities.
4. Write the 100-step training smoke (`training/smoke_train.py`):
   real chip batch from disk, forward through `terramind_v1_base_generate`,
   backward, AdamW step, val-loss compute, checkpoint save, sample
   reconstruction PNG every 25 steps. Watch gradient norms + memory.
5. Snapshot the droplet.
6. Kick off full training run.

## Anomalies worth logging

- Droplet SSH dropped briefly mid-session (~30 s); recovered with no
  intervention, all containers stayed up. Worth a `dmesg` review Monday.
- AMD GPU reported intermittent "low-power state" — expected with vLLM
  stopped and no other GPU work.

## Costs so far

Negligible — idle droplet hours, modest STAC + COG egress to the
container. **No snapshot taken yet.** Recommend snapshotting after the
data pipeline is fixed and the train smoke passes.
