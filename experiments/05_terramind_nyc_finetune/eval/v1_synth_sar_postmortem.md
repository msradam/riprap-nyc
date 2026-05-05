# v1 synth-SAR plan — postmortem

The original plan in `eval_spec.md` was a bespoke synth-SAR fine-tune
on NYC paired Sentinel-1/Sentinel-2 chips. We pivoted to v2 (the
ImpactMesh-Flood reproduction + NYC extension) on Sunday evening
2026-05-03. Documenting the lessons here so future sessions don't
re-walk this path.

## What was the v1 plan

Fine-tune `terramind_v1_base_generate` (TerraMind's diffusion sampler
head) on NYC S2L2A → S1RTC paired chips. Eval target: per-pixel L1
+ LPIPS on a held-out cloudy-April-2026 NYC test set, with the
artifact framed as Riprap's cloud-occlusion fallback path.

## Why we pivoted

1. **Bespoke STAC pipeline carried irreducible flakiness.** Sunday-
   evening Microsoft Planetary Computer API showed >50% timeout
   rate on `get_item` calls; pre-signed URLs expired ≤1 h; signed-
   URL refresh required round-trips through the same flaky API.
2. **MGRS-overlap-edge bugs.** Sentinel-2 tile lon/lat bboxes loosely
   include NYC even when the actual UTM raster footprint doesn't
   (T18TWL bbox spans Manhattan but the raster's western data edge
   is east of Manhattan UTM coords). Three iterations of anchor logic
   tonight — scene-center, NYC-lat-lon-projected, NYC-bbox-intersection
   centroid — each fixed one failure mode and revealed another.
3. **Eval shape was weak.** Per-pixel L1 and LPIPS against held-out
   real S1 RTC measure pixel reconstruction fidelity — but for a
   diffusion model on a held-out scene, the model has no incentive
   to match the *exact realization*, only the *distribution*. The
   numbers would have been noisy and hard to interpret.
4. **No clean comparator.** The base TerraMind already does S2→S1
   synthesis zero-shot. Our story would have been "we made it slightly
   better at NYC SAR" — narrow story, hard quantitative angle.

## What replaced it (v2, eval_spec_v2.md)

Two-phase reproduce-then-extend on **ImpactMesh-Flood** (CC-BY 4.0,
80,651 pre-curated chips, official train/val/test split):

- **Phase 1:** reproduce IBM-ESA's `TerraMind-base-Flood` recipe on
  AMD MI300X. Comparable mIoU on the official test split is the
  reproduction gate. Already underway as of pivot time; baseline
  eval of IBM's published checkpoint on AMD landed at
  `test/mIoU = 0.6663` (the reproduction target).
- **Phase 2:** continuation fine-tune on NYC chips with Phase-1
  Prithvi-EO water-mask pseudo-labels. The differentiated artifact.

Phase 1 alone satisfies "we fine-tuned a TerraMind variant on AMD" —
de-risking the hackathon-deliverable headline. Phase 2 is treated as
a stretch with graceful degradation.

## Salvageable bits from v1

The v1 work that survives in v2:

- **`data/build_manifest.py`** — STAC manifest builder. Useful for
  Phase 2 NYC chip generation, *if* the anchor logic is fixed
  Monday morning. The bbox cap, year-windowing, S2/S1 pairing
  logic, and pre-signing flow are all reusable.
- **`data/extract_chips.py`** — three iterations of fixes; current
  state has the data-driven anchor but still places chips on
  thin coastal overlap strips (centroid lands offshore for southern
  MGRS tiles). **Needs a fourth fix:** require the chip anchor to
  contain at least one known NYC inland reference point (Manhattan,
  Brooklyn, Queens, Bronx centroids), not just any centroid of any
  intersection.
- **Diagnosis of MGRS-overlap-edge artifact** — documented in
  `NOTES.md`; helpful for any future Sentinel-2-tile-anchored
  pipeline.

## What v1 work is now permanently shelved

- **The synth-SAR objective** — `terramind_v1_base_generate` head,
  diffusion-sampler training, per-pixel L1 + LPIPS eval. Not in v2.
  If a future session wants this, start fresh against the TerraMind
  paper's TiM-tuning recipe and the upstream `terramind_v1_base_generate`
  docs, not from this directory.
- **The April-2026 cloudy-NYC holdout set** — five records that all
  had partial S1 or S2 coverage in tonight's tests. Probably re-pull
  with a different month if needed for Phase 2.
- **The `held_out_test.parquet` + `nyc_panels/` artifact spec** —
  superseded by v2's NYC test-chip + Sandy-zone-overlap qualitative
  spec.

## Lessons that generalize

1. **Curated benchmark > bespoke pipeline** when the deliverable is
   "we fine-tuned a model on this hardware." ImpactMesh-Flood's
   one-line download is worth more than a week of STAC engineering.
2. **MGRS bbox metadata is loose; raster.bounds is reliable.** Any
   future Sentinel-2 chip-extraction code should anchor on raster
   bounds, not scene bbox.
3. **PC API flakiness is upstream and bursty.** Sunday-evening
   showed >50% timeouts; same calls Monday-morning succeeded
   instantly. Heavy retries with backoff + a fallback to manifest
   pre-signed URLs are mandatory for any serious bulk extraction.
4. **Reproduction-style fine-tunes are easier to evaluate than
   bespoke ones.** A model card with "we matched IBM's published
   number within 2pp on AMD" is a stronger claim than "our model
   has lower L1 on a custom held-out set."
5. **Eval spec before training, even if you don't ship it.** The
   v1 eval_spec.md never got a real result, but writing it surfaced
   that the synth-SAR objective had no clean comparator — which
   informed the v2 pivot.
