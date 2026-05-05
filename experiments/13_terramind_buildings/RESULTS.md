# Phase 13 — TerraMind for NYC Building Footprint Segmentation

## Goal

Fine-tune TerraMind base on a binary building/non-building segmentation task,
using NYC's authoritative public-domain Building Footprints dataset as
ground truth. Different downstream task than Phase 2 (LULC); same base model.

Civic-tech angle: the model agrees with the city's own building inventory.
NYC OpenData publishes `nyc_dof_building_footprints_2024.shp` (~1.1M polygons,
public domain). A model that segments "is this pixel inside a city-recorded
building footprint?" is directly auditable against city records.

## Why this is interesting

- **Real ground truth.** Not pseudo-labels, not WorldCover proxies. NYC's
  own surveyed building polygons.
- **Direct civic-tech relevance.** New construction detection, illegal-build
  detection, post-storm damage cross-reference.
- **Different task than Phase 2.** LULC is 5-class macros; buildings is
  binary fine-grained. Tests TerraMind's flexibility on the same backbone.
- **Pixel-precise eval possible.** Building IoU vs the polygon raster is a
  clean, defensible metric.

## Data

- **Sentinel-2 + Sentinel-1**: from Major-TOM Core (already cached locally
  for the 22 NYC parent chips).
- **Labels**: NYC DOF Building Footprints (`https://data.cityofnewyork.us/
  Housing-Development/Building-Footprints/nqwf-w8eh`). Public domain.
  Rasterize polygons onto each chip's grid — pixel value 1 inside any
  building polygon, 0 elsewhere.
- **Sub-chip count**: same 224/48/64 train/val/test as Phase 2, since we
  reuse the same parent-chip slicing. ImpactMesh format compatibility
  preserved.

## Plan

1. Scaffold (this file).
2. Write `download_footprints.py` — pull DOF Building Footprints shapefile
   into `experiments/13_terramind_buildings/data/`.
3. Write `rasterize_to_chips.py` — for each parent chip, rasterize building
   footprints onto the chip's grid in EPSG:32618 to produce binary
   GeoTIFF labels (the same `MASK/<chip_id>_annotation_flood.tif` format
   the ImpactMesh datamodule expects).
4. Write `phase4_buildings.yaml` — modify Phase 2 YAML for `num_classes: 2`,
   loss `dice`, no class-weights mismatch.
5. Smoke-test on 1 parent chip end-to-end.
6. Run full fine-tune (~3 GPU-hr; smaller dataset than Phase 1, fewer epochs).
7. Eval: Building IoU on test split, plus visual panels.
8. Publish as `msradam/TerraMind-base-NYC-Buildings`.

## Eval gate

Building IoU on test split:
- Strong: > 0.50 (NYC building footprints are dense and well-delineated;
  this should be achievable)
- Acceptable: 0.30 - 0.50
- Negative: < 0.30 → publish with negative-result framing

For comparison: published satellite-imagery building-segmentation models
typically hit 0.60-0.75 IoU on similar datasets. Our 22-chip dataset is
small so expectations are calibrated downward.

## Risk

Medium. The data-prep is non-trivial (rasterize ~1M polygons onto 22 chip
grids), but rasterio's `rasterize()` handles this directly. Estimated 2 hr
of careful porting.

## What it adds to Riprap

A new specialist `app/context/terramind_buildings.py` that returns:
- `building_density_pct` at this 2.56km tile (= predicted building pixel %)
- `building_count_estimate` (rough connected-component count)

This complements the existing register specialists (`mta_entrances`,
`nycha`, `doe_schools`, `doh_hospitals`) which check for *known* critical
infrastructure. Building density gives a *coarse spatial measure* of how
built-up the area is — useful for impervious-surface modeling.

## Reproduction (planned)

```bash
python3 experiments/13_terramind_buildings/download_footprints.py
python3 experiments/13_terramind_buildings/rasterize_to_chips.py
docker exec terramind terratorch fit --config /root/config_phase4_buildings.yaml
```
