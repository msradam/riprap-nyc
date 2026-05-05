# Phase 14 — Prithvi-EO 2.0 NYC Pluvial Fine-tune

## Goal

Fine-tune NASA/IBM's Prithvi-EO 2.0 (300M, Apache 2.0) for NYC-specific
*pluvial* (basement / sub-surface) flooding, where Riprap's current
zero-shot Sen1Floods11 fine-tune is weakest.

Demonstrates a SECOND foundation-model family on AMD MI300X (TerraMind
+ Prithvi). Strengthens the AMD compatibility story.

## Why pluvial specifically

Riprap's existing Prithvi specialist uses
`ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11` zero-shot.
Sen1Floods11 was trained on global flood events most of which were
*coastal/large-water* (Hurricane Harvey, Bolivia rivers). NYC's deadliest
flood mode is Hurricane-Ida-style *pluvial*: rapid stormwater accumulating
in basement apartments, drainage backflow, sub-surface flooding. Optical
satellites largely *can't see* this, but Prithvi can be improved on the
edges where surface water IS visible.

Riprap already has the NYC-specific training labels: `data/prithvi_ida_2021.geojson`
(166 polygons from a prior Prithvi-EO offline pre-compute on
Hurricane Ida 2021). These polygons are SMALL inland water patches — the
exact pluvial pattern.

## Data

Training:
- 166 NYC-specific Ida polygons + chip the surrounding S2 imagery from
  Hurricane Ida (Aug 25 to Sep 2 2021)
- Augment with NEGATIVE samples (NYC scenes pre-Ida, no flood) — sample
  from Major-TOM cached chips already on disk

Eval:
- Held-out 20% of NYC chips, both flood-positive (Ida polys) and
  flood-negative (random NYC pre-storm)

## Plan

1. Scaffold (this file).
2. Pull S2 chips for the 166 Ida polygon centroids using AWS Open Data
   STAC (live fetch path from Phase 11). Cloud-filter to <30%.
3. Use existing Major-TOM NYC chips as flood-negative.
4. Rasterize Ida polygons onto S2 chip grids → binary masks.
5. Use the published Sen1Floods11 fine-tune YAML as starting point,
   adapt for our NYC dataset.
6. Fine-tune from `ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11`
   (continuation, not from scratch).
7. Eval on held-out NYC chips: water IoU + per-event IoU vs Sen1Floods11
   zero-shot.
8. Publish as `msradam/Prithvi-EO-2.0-NYC-Pluvial`.

## Eval gate

Strong: Water IoU on NYC pluvial subset > Sen1Floods11 zero-shot by 2pp
Acceptable: matches zero-shot performance (≥ -1pp)
Negative: drops > 1pp → publish with negative result, document framing

## Risk

Lower than TerraMind work. Prithvi recipes are well-published; the
primary risk is dataset assembly quality (matching Ida polygons to
appropriate-date S2 chips with low cloud).

## What it adds to Riprap

`app/flood_layers/prithvi_water.py` (existing) currently does
point-in-polygon against the static `prithvi_ida_2021.geojson`. With this
fine-tune, the specialist gains a `prithvi_live` mode: run inference on a
recent S2 chip and detect *current* flooding, not just baked Ida history.

Plus: Riprap's flood-event detection becomes auditable against NYC's
specific flooding patterns, not generic global flood-events.

## Reproduction (planned)

```bash
python3 experiments/14_prithvi_nyc_pluvial/build_dataset.py
docker exec terramind terratorch fit --config /root/config_prithvi_nyc.yaml \
    --ckpt_path /root/.cache/.../Prithvi-EO-2.0-300M-TL-Sen1Floods11.pt
```
