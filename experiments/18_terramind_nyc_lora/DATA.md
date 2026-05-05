# Data

## Provenance

All NYC chip data used for adapter training is built from public-domain
or open-license sources. No proprietary or restricted data is mixed in.

| Component | Source | License | Vintage |
|---|---|---|---|
| Sentinel-2 L2A imagery | ESA Copernicus, served via Major-TOM Core-S2L2A on Hugging Face | ESA Copernicus Open Data License (CC-BY-equivalent, attribution required) | 2017–2024 acquisitions |
| Sentinel-1 RTC imagery (TiM aux) | Major-TOM Core-S1RTC | ESA Copernicus Open Data License | 2017–2024 |
| DEM | Major-TOM Core-DEM (Copernicus GLO-30) | ESA Copernicus Open Data License | static |
| LULC labels | ESA WorldCover 2021 v200 (10 m global), pulled directly from `s3://esa-worldcover/v200/2021/map/ESA_WorldCover_10m_2021_v200_N39W075_Map.tif` | CC-BY-4.0 | 2021 |
| Building footprints | NYC DOITT Building Footprints (1.08 M polygons, public domain via NYC OpenData) | Public domain | 2024-09 download |

## Chip pipeline

Same pipeline as Phase 2/3/4 for byte-for-byte consistency with the
existing full-fine-tune baselines (this matters for valid LoRA-vs-full-FT
comparison per ADR-005):

1. **Major-TOM filter** — pull S2L2A, S1RTC, and DEM products whose
   centroid falls inside the NYC bbox (`-74.30, 40.45, -73.65, 40.95`)
   with cloud cover ≤ 20%. Yields 22 unique parent grid cells.
2. **Slice into 224×224 sub-chips** — each Major-TOM parent is sliced
   into a 4×4 grid of non-overlapping 224×224 chips, totalling 352 chips.
   Sub-chip transforms are derived from the parent's GeoTransform.
3. **Per-chip label rasterization** —
   - LULC: read WorldCover 2021 GeoTIFF at the chip's bbox, collapse the
     11 native classes to 5 NYC-relevant macro-classes per the table
     below.
   - Buildings: rasterize NYC DOITT polygons onto the chip grid as a
     binary mask.
4. **Pack to ImpactMesh-compatible zarr.zip** — TerraTorch's
   `ImpactMeshDataModule` is the loader. Note the path-greps for
   `flood` or `fire` in `data_root`: we symlink `nyc_lulc → nyc_lulc_flood`
   to satisfy this without shipping flood data.

The driver scripts (kept verbatim from Phase 2/3 for reproducibility):

- `experiments/05_terramind_nyc_finetune/data/major_tom_nyc.py` — Major-TOM
  metadata-filter and parent download.
- `experiments/05_terramind_nyc_finetune/data/slice_and_label_nyc.py` —
  4×4 sub-chip slicing and WorldCover label rasterization.
- `experiments/13_terramind_buildings/rasterize_buildings.py` — NYC DOITT
  download and building-mask rasterization.

## LULC class collapse

WorldCover 2021 has 11 native classes. Five NYC-relevant macros are
derived as:

| Our class | WorldCover sources | Rationale |
|---|---|---|
| 0 — Impervious / urban | `Built-up (50)` excluding building footprints | Roads, parking, plazas. Drives stormwater runoff. |
| 1 — Vegetation | `Tree cover (10)`, `Shrubland (20)`, `Grassland (30)`, `Herbaceous wetland (90)`, `Mangroves (95)`, `Moss/lichen (100)` | Permeable surfaces, urban canopy. |
| 2 — Water | `Permanent water bodies (80)`, `Snow/ice (70)` | Hudson, East River, Jamaica Bay, reservoirs. |
| 3 — Bare / cropland | `Bare/sparse vegetation (60)`, `Cropland (40)` | Beach, Floyd Bennett, Plumb Beach. |
| 4 — Building | NYC DOITT polygons rasterized | Distinct from "impervious" because building rooftops have different EO signatures than ground impervious and matter for flood-exposure attribution. |

This is an editorial collapse, not a defensible classification system. The
intent is to give NYC-flood-exposure briefings a tractable land-use
prior, not to compete with land-cover benchmarks. Reported in
`MODEL_CARD.md` under "Out of scope".

## Splits

Stratified-random with `seed=42`. Counts inherited from Phase 2/3/4
(committed `impactmesh_flood_{train,val,test}.txt` lists in the source
ImpactMesh dataset directories) for byte-for-byte LoRA-vs-full-FT
comparison validity per ADR-005:

| Adapter | Train | Val | Test | Total |
|---|---|---|---|---|
| `lulc_nyc` | 224 | 48 | 64 | 336 |
| `tim_nyc` | 224 | 48 | 64 | 336 |
| `buildings_nyc` | 144 | 32 | 32 | 208 |

The test-split chip-ID lists are committed under
`adapters/{name}/splits/test.txt`. See [`EVAL.md`](EVAL.md) for the
locked-methodology contract.

## Adding new data later

The whole point of LoRA-per-task is that adding more data on top is
cheap. To extend any existing adapter with new chips:

1. Append new chip IDs to the matching `splits/train.txt`.
2. Re-run training (or warm-start from the existing adapter ckpt).
3. Re-evaluate against the unchanged test split for honest delta.
4. Update MODEL_CARD.md Results with both numbers (before-after) and a
   `Methodology change log` entry in EVAL.md noting the new train data.

The locked test split MUST NOT change when extending data — that's the
guarantee that makes longitudinal improvement claims publishable.

## Negative-data hygiene

We deliberately do NOT include:

- Imagery from outside the NYC bbox. The adapters are NYC specialists by
  design.
- Synthetically rendered S2 or building masks (e.g. from Riprap's
  Prithvi-segmented water polygons). The baseline data should be
  ground-truth from public records, not derived from another model.
- Imagery acquisitions during major weather events (Ida, Sandy). Those
  belong to flood-detection adapters (Prithvi family), not to LULC or
  Buildings, which want clear-sky baselines.

## Storage

On the AMD MI300X droplet:

- Major-TOM cache: `/root/MajorTOM/...` (S2L2A + S1RTC + DEM, ~80 GB).
- ImpactMesh-format dataset: `/root/terramind_nyc/nyc_lulc_flood/` and
  `/root/terramind_nyc/nyc_buildings_flood/` (symlinked from the
  unsuffixed path).
- Built dataset zarr.zip files: ~1–3 GB each.

Total disk footprint for all three adapter datasets: ≤ 100 GB.
