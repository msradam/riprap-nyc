"""Run Prithvi-EO 2.0 (Sen1Floods11) on a real Hurricane Ida pre/post pair.

Pre-event:  HLS.S30.T18TWK.2021237T153809.v2.0   (2021-08-25, 3% cloud)
Post-event: HLS.S30.T18TWK.2021245T154911.v2.0   (2021-09-02, 1% cloud,
                                                  ~12h after peak rainfall)

This is the genuinely-defensible Prithvi run for the demo: a real flood
event, two clean scenes within the model's optical comfort zone, with a
diff that isolates *new* surface water attributable to Ida from the
permanent rivers/harbor that are present in both scenes.

Honest framing baked into the metadata:
- The model still misses subway and basement flooding (sub-surface; the
  dominant Ida damage mode in NYC). Optical satellite cannot see those.
- By 16:02 UTC Sep 2 (~12 h post-peak), pluvial street water had largely
  drained. The diff signal is mostly: Jamaica Bay marsh ponding,
  riverside spillover, low-lying park inundation.
- This is what an Apache-2.0 foundation model can defensibly contribute
  to a flood-event assessment, and we say so in the report.

    python scripts/run_prithvi_ida.py
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

PRE_SCENE  = "HLS.S30.T18TWK.2021237T153809.v2.0"
POST_SCENE = "HLS.S30.T18TWK.2021245T154911.v2.0"
PRE_DATE   = "2021-08-25"
POST_DATE  = "2021-09-02"
EVENT      = "Hurricane Ida"

MODEL_REPO = "ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11"
PRITHVI_BAND_NAMES = ["B02", "B03", "B04", "B8A", "B11", "B12"]


def _stage_stack(out_path: Path, scene_id: str) -> bool:
    if out_path.exists():
        print(f"  reusing {out_path.name}", file=sys.stderr)
        return True
    import numpy as np
    import planetary_computer
    import pystac_client
    import rasterio
    print(f"fetching {scene_id}...", file=sys.stderr)
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    item = catalog.get_collection("hls2-s30").get_item(scene_id)
    if item is None:
        print(f"  {scene_id} not retrievable", file=sys.stderr)
        return False
    arrays = []
    profile = None
    for band in PRITHVI_BAND_NAMES:
        with rasterio.open(item.assets[band].href) as ds:
            arrays.append(ds.read(1))
            if profile is None:
                profile = ds.profile.copy()
    stack = np.stack(arrays, axis=0).astype("float32")
    stack[stack <= -9000] = 0.0
    stack = stack / 10000.0
    stack = np.clip(stack, 0.0, 1.0).astype("float32")
    profile.update(count=6, dtype="float32",
                   compress="DEFLATE", tiled=True,
                   blockxsize=256, blockysize=256, nodata=0.0)
    with rasterio.open(out_path, "w", **profile) as ds:
        for i in range(6):
            ds.write(stack[i], i + 1)
    print(f"  wrote {out_path.name} ({out_path.stat().st_size // (1024*1024)} MB)",
          file=sys.stderr)
    return True


def _run_prithvi(stack_path: Path, out_dir: Path) -> Path | None:
    """Run inference if needed; return path to pred .tiff."""
    pred_path = out_dir / f"pred_{stack_path.stem}.tiff"
    if pred_path.exists():
        print(f"  reusing existing pred: {pred_path.name}", file=sys.stderr)
        return pred_path

    from huggingface_hub import hf_hub_download
    inf_py = hf_hub_download(MODEL_REPO, "inference.py")
    cfg = hf_hub_download(MODEL_REPO, "config.yaml")
    ckpt = hf_hub_download(MODEL_REPO, "Prithvi-EO-V2-300M-TL-Sen1Floods11.pt")

    spec = importlib.util.spec_from_file_location("prithvi_inf", inf_py)
    pm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pm)

    print(f"  running Prithvi on {stack_path.name}...", file=sys.stderr)
    pm.main(data_file=str(stack_path), config=cfg, checkpoint=ckpt,
            output_dir=str(out_dir), rgb_outputs=False, input_indices=None)
    if pred_path.exists():
        return pred_path
    cands = list(out_dir.glob(f"pred_{stack_path.stem}*"))
    return cands[0] if cands else None


def main() -> int:
    out_geojson = OUT_DIR / "prithvi_ida_2021.geojson"
    if out_geojson.exists():
        print(f"already exists: {out_geojson}", file=sys.stderr)
        return 0

    pre_stack  = OUT_DIR / f"hls_stack_pre_ida_{PRE_DATE}.tif"
    post_stack = OUT_DIR / f"hls_stack_post_ida_{POST_DATE}.tif"
    if not (_stage_stack(pre_stack,  PRE_SCENE) and
            _stage_stack(post_stack, POST_SCENE)):
        return 1

    out_dir = OUT_DIR / "prithvi_runs"
    out_dir.mkdir(exist_ok=True)
    pre_pred  = _run_prithvi(pre_stack,  out_dir)
    post_pred = _run_prithvi(post_stack, out_dir)
    if pre_pred is None or post_pred is None:
        print("inference failed", file=sys.stderr)
        return 2

    # ---- diff: NEW water in post that wasn't in pre = Ida-attributable ----
    import geopandas as gpd
    import rasterio
    from rasterio.features import shapes
    from shapely.geometry import mapping, shape

    with rasterio.open(pre_pred) as ds:
        pre = ds.read(1)
    with rasterio.open(post_pred) as ds:
        post = ds.read(1)
        transform = ds.transform
        crs = ds.crs

    # The model emits 0 / 255. New-water = post(255) AND pre(!=255)
    new_water = (post == 255) & (pre != 255)
    n_new = int(new_water.sum())
    n_pre = int((pre == 255).sum())
    n_post = int((post == 255).sum())
    print(f"  pre  water px: {n_pre:>8d} ({100*n_pre/pre.size:.2f}%)", file=sys.stderr)
    print(f"  post water px: {n_post:>8d} ({100*n_post/post.size:.2f}%)", file=sys.stderr)
    print(f"  NEW  water px: {n_new:>8d} ({100*n_new/post.size:.2f}%)", file=sys.stderr)

    # also save the post mask for "all post-event water" if useful
    post_water = post == 255

    # vectorize NEW water (Ida-attributable inundation)
    feats_new = []
    for geom, val in shapes(new_water.astype("uint8"),
                              mask=new_water, transform=transform):
        if val == 1:
            poly = shape(geom)
            if poly.area > 0:
                feats_new.append({"type": "Feature",
                                   "geometry": mapping(poly),
                                   "properties": {"class": "new_water_post_ida"}})

    # vectorize ALL post-event water (for legend / context)
    feats_post = []
    for geom, val in shapes(post_water.astype("uint8"),
                              mask=post_water, transform=transform):
        if val == 1:
            poly = shape(geom)
            if poly.area > 0:
                feats_post.append({"type": "Feature",
                                    "geometry": mapping(poly),
                                    "properties": {"class": "post_event_water"}})

    g_new = gpd.GeoDataFrame.from_features(feats_new, crs=crs).to_crs("EPSG:4326") \
        if feats_new else gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    g_post = gpd.GeoDataFrame.from_features(feats_post, crs=crs).to_crs("EPSG:4326") \
        if feats_post else gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    new_features = json.loads(g_new.to_json())["features"]
    post_features = json.loads(g_post.to_json())["features"]

    out = {
        "type": "FeatureCollection",
        "features": new_features,
        "_post_event_water_features": post_features,  # carried for reference
        "event": EVENT,
        "pre_scene_id": PRE_SCENE,  "pre_scene_date": PRE_DATE,
        "post_scene_id": POST_SCENE, "post_scene_date": POST_DATE,
        "model": MODEL_REPO,
        "crs": "EPSG:4326",
        "interpretation": (
            "Polygons in `features` are pixels classified as water in the "
            "post-event scene but NOT in the pre-event scene — i.e., "
            "candidate Hurricane Ida-attributable inundation. The Sep 2 "
            "Sentinel-2 pass was ~12 h after peak rainfall; pluvial street "
            "and basement flooding (the dominant Ida damage mode in NYC) "
            "had largely drained by then, so this signal mostly captures "
            "marsh ponding, riverside spillover, and low-lying park water. "
            "Subway and basement flooding are not surface-visible to "
            "optical satellites."
        ),
    }
    out_geojson.write_text(json.dumps(out))
    print(f"\nwrote {len(new_features)} new-water polygons + "
          f"{len(post_features)} post-event water polygons "
          f"-> {out_geojson} ({out_geojson.stat().st_size // 1024} KB)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
