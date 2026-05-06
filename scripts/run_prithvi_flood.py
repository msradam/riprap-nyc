"""Run Prithvi-EO-2.0-300M-TL-Sen1Floods11 once on a low-cloud HLS scene
over NYC. Save the resulting water mask as a vectorized GeoJSON for use
as a Riprap flood-layer specialist.

This script defers to IBM's official inference.py (downloaded from the
model repo) rather than reimplementing the inference loop — that file
knows about the temporal/location-coord embeddings, the per-window
albumentations stack, and the upernet decoder output shape, all of
which are easy to get wrong.

    python scripts/run_prithvi_flood.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data"
OUT_DIR.mkdir(exist_ok=True, parents=True)

# NYC needs two MGRS tiles to cover everything:
#  T18TWL covers Manhattan, Bronx, western Brooklyn, Newark Bay
#  T18TXK covers eastern Brooklyn, Queens, Far Rockaway, Jamaica Bay, Long Island Sound
SCENES = [
    ("HLS.S30.T18TWL.2024247T153941.v2.0", "2024-09-04"),  # 1% cloud, central NYC
    ("HLS.S30.T18TXK.2024252T153819.v2.0", "2024-09-08"),  # 0% cloud, eastern NYC
]
SCENE_ID, SCENE_DATE = SCENES[0]  # back-compat for legacy users
MODEL_REPO = "ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11"
PRITHVI_BAND_NAMES = ["B02", "B03", "B04", "B8A", "B11", "B12"]


def _stage_stack(out_path: Path, scene_id: str = SCENE_ID) -> bool:
    if out_path.exists():
        return True
    import numpy as np
    import planetary_computer
    import pystac_client
    import rasterio
    print(f"fetching scene {scene_id}...", file=sys.stderr)
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    item = catalog.get_collection("hls2-s30").get_item(scene_id)
    if item is None:
        print("  scene not retrievable", file=sys.stderr)
        return False
    arrays = []; profile = None
    for band in PRITHVI_BAND_NAMES:
        with rasterio.open(item.assets[band].href) as ds:
            arrays.append(ds.read(1))
            if profile is None:
                profile = ds.profile.copy()
    stack = np.stack(arrays, axis=0).astype("float32")
    # Replace nodata -9999 with the inference.py NO_DATA_FLOAT sentinel (0.0001).
    # inference.py only treats nodata correctly when explicit mean/std are
    # configured — for this Sen1Floods11 fine-tune mean/std are None, so we
    # do the substitution upstream and write a clean float32 raster in 0..1
    # reflectance units (constant_scale=0.0001 in config => DN/10000).
    stack[stack <= -9000] = 0.0
    stack = stack / 10000.0
    stack = np.clip(stack, 0.0, 1.0).astype("float32")
    profile.update(count=6, dtype="float32",
                   compress="DEFLATE", tiled=True,
                   blockxsize=256, blockysize=256, nodata=0.0)
    with rasterio.open(out_path, "w", **profile) as ds:
        for i in range(6):
            ds.write(stack[i], i + 1)
    print(f"  wrote {out_path} ({out_path.stat().st_size // (1024*1024)} MB) "
          f"(reflectance units, nodata→0)", file=sys.stderr)
    return True


def _process_one(scene_id: str, scene_date: str) -> list[dict]:
    """Stage one MGRS tile, run Prithvi, vectorise to features. Returns
    a list of GeoJSON Features in EPSG:4326 (so they can be merged across
    tiles in different UTM zones)."""
    stack_path = OUT_DIR / f"hls_stack_{scene_date}.tif"
    if not _stage_stack(stack_path, scene_id=scene_id):
        return []

    from huggingface_hub import hf_hub_download
    inf_py = hf_hub_download(MODEL_REPO, "inference.py")
    cfg = hf_hub_download(MODEL_REPO, "config.yaml")
    ckpt = hf_hub_download(MODEL_REPO, "Prithvi-EO-V2-300M-TL-Sen1Floods11.pt")

    spec = importlib.util.spec_from_file_location("prithvi_inf", inf_py)
    pm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pm)

    out_dir = OUT_DIR / "prithvi_runs"
    out_dir.mkdir(exist_ok=True)

    pred_path = out_dir / f"pred_{stack_path.stem}.tiff"
    if not pred_path.exists():
        print(f"running Prithvi on {scene_id}...", file=sys.stderr)
        pm.main(data_file=str(stack_path), config=cfg, checkpoint=ckpt,
                output_dir=str(out_dir), rgb_outputs=False, input_indices=None)
    else:
        print(f"  reusing existing pred: {pred_path}", file=sys.stderr)

    if not pred_path.exists():
        cands = list(out_dir.glob(f"pred_{stack_path.stem}*"))
        pred_path = cands[0] if cands else None
    if pred_path is None or not pred_path.exists():
        print(f"  no prediction tiff for {scene_id}", file=sys.stderr)
        return []

    import geopandas as gpd
    import rasterio
    from rasterio.features import shapes
    from shapely.geometry import mapping, shape

    with rasterio.open(pred_path) as ds:
        pred = ds.read(1); transform = ds.transform; src_crs = ds.crs

    water_mask = pred == 255
    n_water = int(water_mask.sum())
    print(f"  {scene_id}: {n_water} water px "
          f"({100*n_water/pred.size:.2f}%)", file=sys.stderr)

    feats = []
    for geom, val in shapes(water_mask.astype("uint8"),
                              mask=water_mask, transform=transform):
        if val == 1:
            poly = shape(geom)
            if poly.area > 0:
                feats.append({"type": "Feature",
                               "geometry": mapping(poly),
                               "properties": {"class": "water",
                                              "scene_id": scene_id,
                                              "scene_date": scene_date}})

    if not feats:
        return []

    # Reproject to EPSG:4326 for cross-tile merging
    g = gpd.GeoDataFrame.from_features(feats, crs=src_crs)
    g = g.to_crs("EPSG:4326")
    return json.loads(g.to_json())["features"]


def main() -> int:
    out_geojson = OUT_DIR / "prithvi_flood_nyc.geojson"
    if out_geojson.exists():
        print(f"already exists: {out_geojson}", file=sys.stderr)
        return 0

    all_features = []
    scene_ids = []; scene_dates = []
    for scene_id, scene_date in SCENES:
        feats = _process_one(scene_id, scene_date)
        all_features.extend(feats)
        if feats:
            scene_ids.append(scene_id); scene_dates.append(scene_date)

    out = {"type": "FeatureCollection", "features": all_features,
            "scene_ids": scene_ids, "scene_dates": scene_dates,
            "model": MODEL_REPO, "crs": "EPSG:4326"}
    out_geojson.write_text(json.dumps(out))
    print(f"\nwrote {len(all_features)} water polygons across "
          f"{len(scene_ids)} scenes -> {out_geojson} "
          f"({out_geojson.stat().st_size // 1024} KB)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
