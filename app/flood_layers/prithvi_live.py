"""Prithvi-EO 2.0 (Sen1Floods11 fine-tune) live water segmentation.

A per-query specialist: pulls the most recent low-cloud Sentinel-2 L2A
scene over the address from Microsoft Planetary Computer, runs the
IBM-NASA flood-mapping fine-tune, and reports % water within 500 m.

Distinct from `app/flood_layers/prithvi_water.py`, which serves the
offline-precomputed 2021 Ida polygons. This one is *fresh observation*
each query — different doc_id (`prithvi_live`), different epistemic
claim, additive to the static layer.

Network calls (STAC search + COG band reads) and a 300M-param model
forward pass make this the slowest specialist after the LLM. Gated by
RIPRAP_PRITHVI_LIVE_ENABLE so deployments without the deps installed
silently skip it. Cloud-cover refuses out at 30%+ to honor the
Sen1Floods11 training distribution.

License: Apache-2.0 (verified — `ibm-nasa-geospatial/Prithvi-EO-2.0-
300M-TL-Sen1Floods11`). See experiments/shared/licenses.md.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

log = logging.getLogger("riprap.prithvi_live")

ENABLE = os.environ.get("RIPRAP_PRITHVI_LIVE_ENABLE", "1").lower() in ("1", "true", "yes")
SEARCH_DAYS = int(os.environ.get("RIPRAP_PRITHVI_LIVE_SEARCH_DAYS", "120"))
MAX_CLOUD_PCT = float(os.environ.get("RIPRAP_PRITHVI_LIVE_MAX_CLOUD", "30"))
DEVICE = os.environ.get("RIPRAP_PRITHVI_LIVE_DEVICE", "cpu")
REPO = "ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11"

# Sen1Floods11 expects 6 bands in this exact order.
BANDS = ["B02", "B03", "B04", "B8A", "B11", "B12"]
IMG_SIZE = 512  # Sen1Floods11 training crop
CHIP_PX = 1024
CHIP_M = CHIP_PX * 10
HALF_M = CHIP_M / 2
CENTER_RADIUS_M = 500
PIXEL_M = 10

_MODEL = None
_RUN_MODEL = None
_INIT_LOCK = threading.Lock()  # serializes lazy load if multiple threads
                               # hit fetch() before _MODEL is populated


def _has_required_deps() -> tuple[bool, str | None]:
    """Heavy-EO deps (terratorch / planetary_computer / rioxarray /
    pystac-client / xarray / einops) live in requirements-experiments.txt
    only — they don't fit Riprap's HF Spaces' Py3.10 dep cone alongside
    transformers<5 / hf_hub<1 / granite-tsfm<0.3.4 / mellea<0.4.

    Probe each importable name once at module load. If any are missing,
    fetch() returns a clean `skipped: deps_unavailable` outcome instead
    of crashing with a noisy ModuleNotFoundError in the trace. Local
    dev + AMD path have these installed and the specialist runs."""
    missing = []
    for name in ("terratorch", "planetary_computer", "pystac_client",
                 "rioxarray", "xarray", "einops"):
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if missing:
        return False, ", ".join(missing)
    return True, None


_DEPS_OK, _DEPS_MISSING = _has_required_deps()


def warm():
    """Optional pre-load. The FSM action is lazy too — calling warm()
    here just amortizes the first-query cost at app boot."""
    if not ENABLE:
        return
    try:
        _ensure_model()
    except Exception:
        log.exception("prithvi_live: warm() failed; specialist will no-op")


def _ensure_model():
    global _MODEL, _RUN_MODEL
    if _MODEL is not None:
        return _MODEL, _RUN_MODEL
    with _INIT_LOCK:
        if _MODEL is not None:  # double-check inside the lock
            return _MODEL, _RUN_MODEL
        import importlib.util

        from huggingface_hub import hf_hub_download
        from terratorch.cli_tools import LightningInferenceModel
        config_path = hf_hub_download(REPO, "config.yaml")
        checkpoint = hf_hub_download(REPO, "Prithvi-EO-V2-300M-TL-Sen1Floods11.pt")
        log.info("prithvi_live: loading model")
        m = LightningInferenceModel.from_config(config_path, checkpoint)
        m.model.eval()
        if DEVICE == "cuda":
            try:
                import torch
                if torch.cuda.is_available():
                    m.model.cuda()
            except Exception:
                log.exception("prithvi_live: cuda move failed")

        inference_py = hf_hub_download(REPO, "inference.py")
        spec = importlib.util.spec_from_file_location("_prithvi_inference",
                                                       inference_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MODEL = m
        _RUN_MODEL = mod.run_model
        return _MODEL, _RUN_MODEL


def _search_recent_scene(lat: float, lon: float):
    """Most recent low-cloud S2 L2A item near (lat, lon) in the last
    SEARCH_DAYS days, or None."""
    import datetime as dt

    import planetary_computer as pc
    from pystac_client import Client
    end = dt.datetime.utcnow().date()
    start = end - dt.timedelta(days=SEARCH_DAYS)
    client = Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=pc.sign_inplace,
    )
    delta = 0.02
    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=[lon - delta, lat - delta, lon + delta, lat + delta],
        datetime=f"{start}/{end}",
        query={"eo:cloud_cover": {"lt": MAX_CLOUD_PCT}},
        max_items=20,
    )
    items = sorted(
        search.items(),
        key=lambda it: (it.properties.get("eo:cloud_cover", 100),
                        -(it.datetime.timestamp() if it.datetime else 0)),
    )
    return items[0] if items else None


def _build_chip(item, lat: float, lon: float):
    """Returns (img, ref_da, epsg) — img is the (6, H, W) center-cropped
    float32 array; ref_da is the rioxarray DataArray of the reference
    band BEFORE the center crop (kept so we can compute the affine
    transform for polygonization in EPSG:4326)."""
    import numpy as np
    import rioxarray  # noqa: F401
    import xarray as xr
    from pyproj import Transformer
    if "proj:epsg" in item.properties:
        epsg = int(item.properties["proj:epsg"])
    else:
        code = item.properties.get("proj:code", "")
        if code.startswith("EPSG:"):
            epsg = int(code.split(":", 1)[1])
        else:
            raise RuntimeError("STAC item missing proj:epsg / proj:code")
    fwd = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    cx, cy = fwd.transform(lon, lat)
    xmin, xmax = cx - HALF_M, cx + HALF_M
    ymin, ymax = cy - HALF_M, cy + HALF_M
    ref = rioxarray.open_rasterio(item.assets[BANDS[0]].href, masked=False).squeeze(drop=True)
    ref = ref.rio.clip_box(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax)
    ref = ref.isel(y=slice(0, CHIP_PX), x=slice(0, CHIP_PX))
    arrs = [ref.astype("float32")]
    for b in BANDS[1:]:
        da = rioxarray.open_rasterio(item.assets[b].href, masked=False).squeeze(drop=True)
        da = da.rio.clip_box(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax)
        if da.shape != ref.shape:
            da = da.rio.reproject_match(ref)
        arrs.append(da.astype("float32"))
    stacked = xr.concat(arrs, dim="band", join="override").assign_coords(band=BANDS)
    img = stacked.values  # (6, H, W)
    # Center crop to IMG_SIZE x IMG_SIZE.
    _, h, w = img.shape
    sy, sx = (h - IMG_SIZE) // 2, (w - IMG_SIZE) // 2
    img = img[:, sy:sy + IMG_SIZE, sx:sx + IMG_SIZE]
    if img.mean() > 1:
        img = img / 10000.0
    return np.nan_to_num(img.astype("float32")), ref, epsg


def _polygonize_mask(pred, ref_da, epsg: int) -> dict | None:
    """Vectorize the binary water mask into an EPSG:4326 GeoJSON
    FeatureCollection so the frontend can paint it on the MapLibre
    map. Returns None on failure (best-effort — never raises into the
    caller path)."""
    try:
        import json

        import geopandas as gpd
        from rasterio.features import shapes
        from rasterio.transform import from_origin
        from shapely.geometry import shape
        # Reconstruct the affine transform of the center-cropped pred.
        # ref_da has 1024 px at 10 m; we cropped to the central 512.
        xs = ref_da.x.values
        ys = ref_da.y.values
        if len(xs) < IMG_SIZE or len(ys) < IMG_SIZE:
            return None
        # rioxarray gives pixel-centered coords; offset by half a pixel
        # to the upper-left to build a from_origin transform.
        sy = (len(ys) - IMG_SIZE) // 2
        sx = (len(xs) - IMG_SIZE) // 2
        # ys are descending (top-to-bottom); take the top of the crop.
        top_y = float(ys[sy]) + (PIXEL_M / 2.0)
        left_x = float(xs[sx]) - (PIXEL_M / 2.0)
        transform = from_origin(left_x, top_y, PIXEL_M, PIXEL_M)
        # Polygonize only the water class (1).
        mask = (pred == 1).astype("uint8")
        polys = []
        for geom, value in shapes(mask, mask=mask.astype(bool),
                                   transform=transform):
            if value != 1:
                continue
            polys.append(shape(geom))
        if not polys:
            return {"type": "FeatureCollection", "features": []}
        gdf = gpd.GeoDataFrame({"geometry": polys},
                                crs=f"EPSG:{epsg}").to_crs("EPSG:4326")
        # Simplify slightly to keep the SSE payload small (10 m raster
        # over 5 km square = up to ~10 k tiny squares; simplification
        # collapses adjacent water pixels into smooth polygons).
        gdf["geometry"] = gdf.geometry.simplify(0.00005, preserve_topology=True)
        return json.loads(gdf.to_json())
    except Exception:
        log.exception("prithvi_live: polygonize failed")
        return None


def fetch(lat: float, lon: float, timeout_s: float = 60.0) -> dict[str, Any]:
    """Run the specialist. Returns a dict with at minimum:
        { "ok": bool,
          "skipped": str | None,    # reason if no observation
          "item_id": str | None,
          "item_datetime": str | None,
          "cloud_cover": float | None,
          "pct_water_within_500m": float | None,
          "pct_water_full": float | None }
    Designed to never raise; failures show up as ok=False with an `err`.
    """
    if not ENABLE:
        return {"ok": False, "skipped": "RIPRAP_PRITHVI_LIVE_ENABLE=0"}
    if not _DEPS_OK:
        # Clean "not deployed here" signal instead of a ModuleNotFoundError
        # surfaced as an exception. Same trace-card layout as ENABLE=0.
        return {"ok": False,
                "skipped": f"deps unavailable on this deployment: "
                           f"{_DEPS_MISSING}"}
    t0 = time.time()
    try:
        item = _search_recent_scene(lat, lon)
        if item is None:
            return {"ok": False, "skipped": f"no <{MAX_CLOUD_PCT}% cloud "
                    f"S2 in last {SEARCH_DAYS}d"}
        cc = float(item.properties.get("eo:cloud_cover", -1))
        if time.time() - t0 > timeout_s:
            return {"ok": False, "skipped": "stac search exceeded budget"}
        img, ref_da, epsg = _build_chip(item, lat, lon)
        if time.time() - t0 > timeout_s:
            return {"ok": False, "skipped": "chip build exceeded budget"}
        model, run_model = _ensure_model()
        x = img[None, :, None, :, :]  # (1, 6, 1, H, W)
        pred_t = run_model(x, None, None, model.model, model.datamodule, IMG_SIZE)
        import numpy as np
        pred = pred_t[0].cpu().numpy().astype("uint8")
        pct_full = float(100.0 * pred.mean())
        yy, xx = np.indices(pred.shape)
        cy, cx = pred.shape[0] // 2, pred.shape[1] // 2
        radius_px = CENTER_RADIUS_M / PIXEL_M
        circle = (yy - cy) ** 2 + (xx - cx) ** 2 <= radius_px ** 2
        pct_500 = float(100.0 * pred[circle].mean()) if circle.sum() else 0.0
        # Polygonize the water mask into EPSG:4326 GeoJSON for the map.
        polygons_geojson = _polygonize_mask(pred, ref_da, epsg)
        return {
            "ok": True,
            "item_id": item.id,
            "item_datetime": str(item.datetime),
            "cloud_cover": cc,
            "pct_water_full": pct_full,
            "pct_water_within_500m": pct_500,
            "polygons_geojson": polygons_geojson,
            "elapsed_s": round(time.time() - t0, 2),
        }
    except Exception as e:
        log.exception("prithvi_live: fetch failed")
        return {"ok": False, "err": f"{type(e).__name__}: {e}",
                "elapsed_s": round(time.time() - t0, 2)}
