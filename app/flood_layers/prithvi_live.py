"""Prithvi-EO 2.0 (NYC Pluvial v2 fine-tune) live water segmentation.

A per-query specialist: pulls the most recent low-cloud Sentinel-2 L2A
scene over the address from Microsoft Planetary Computer, runs the
NYC-specialized fine-tune, and reports % water within 500 m.

Distinct from `app/flood_layers/prithvi_water.py`, which serves the
offline-precomputed 2021 Ida polygons. This one is *fresh observation*
each query — same doc_id (`prithvi_live`), but the underlying model
has been swapped from the Sen1Floods11 base to
`msradam/Prithvi-EO-2.0-NYC-Pluvial` (Apache-2.0, fine-tuned on AMD
Instinct MI300X via AMD Developer Cloud — test flood IoU 0.5979,
6× over the base). The base model is still loadable by setting
RIPRAP_PRITHVI_LIVE_REPO to the IBM repo as a fallback.

Network calls (STAC search + COG band reads) and a 300M-param model
forward pass make this the slowest specialist after the LLM. Gated by
RIPRAP_PRITHVI_LIVE_ENABLE so deployments without the deps installed
silently skip it. Cloud-cover refuses out at 30%+ to honor the
Sen1Floods11 training distribution.

License: Apache-2.0. See experiments/shared/licenses.md.
"""

from __future__ import annotations

import concurrent.futures
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

# Default to the NYC Pluvial v2 fine-tune; override to the IBM-NASA base
# (`ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11`) when the v2
# artifact is unreachable or for A/B comparisons.
REPO = os.environ.get(
    "RIPRAP_PRITHVI_LIVE_REPO",
    "msradam/Prithvi-EO-2.0-NYC-Pluvial",
)
BASE_REPO = "ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11"

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
    """Probe deps in two tiers.

    Tier 1 — chip fetching (planetary_computer / pystac_client / rioxarray
    / xarray / einops) is always required: prithvi_live always pulls a
    Sentinel-2 chip from Microsoft Planetary Computer regardless of where
    inference runs.

    Tier 2 — local inference (terratorch) is only required when remote
    inference is unavailable. On the HF Space we have remote inference
    on the AMD MI300X via app/inference.py, so terratorch is not needed
    even though chip-fetch is.

    Returns (False, missing) if any required dep is missing. Splitting
    the gate this way lets the HF Space deployment fetch chips and run
    remote inference even though it doesn't fit terratorch's transitive
    dep cone (~250 MB) in the HF build sandbox."""
    chip_deps = ("planetary_computer", "pystac_client",
                 "rioxarray", "xarray", "einops")
    missing = [n for n in chip_deps
               if not _has_module(n)]
    if missing:
        return False, ", ".join(missing)
    # Tier 2: only need terratorch if we'd run inference locally.
    try:
        from app import inference as _inf
        if _inf.remote_enabled():
            return True, None
    except Exception:
        pass
    if not _has_module("terratorch"):
        return False, "terratorch (local inference)"
    return True, None


def _has_module(name: str) -> bool:
    """True if `name` imports cleanly. ImportError → not installed.
    Other exceptions (e.g. torchvision::nms RuntimeError on the HF
    Space) → treat as unavailable too; we don't want a clean-skip
    intent to crash the FSM at deps-probe time."""
    try:
        __import__(name)
        return True
    except ImportError:
        return False
    except Exception as e:
        log.warning("prithvi_live: %s import raised %s; treating as "
                    "unavailable", name, type(e).__name__)
        return False


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
    """Load Prithvi-EO 2.0 once into RAM.

    The v2 NYC Pluvial fine-tune (`msradam/Prithvi-EO-2.0-NYC-Pluvial`)
    is **architecturally distinct** from the IBM-NASA Sen1Floods11
    base: v2 ships a `UNetDecoder` + 2-class head, the base ships a
    UperNet with PSP / FPN. The model has to be built from each
    repo's own config.yaml — there's no key-mapping shim that bridges
    them.

    Strategy:

      1. If the active REPO != BASE_REPO, try to build from the v2
         yaml + v2 ckpt. The v2 yaml's data: paths point at the
         training droplet's filesystem (`/root/terramind_nyc/...`)
         which doesn't exist locally; that's fine — the
         GenericNonGeoSegmentationDataModule constructor only
         records the paths, splits aren't read until `setup()`.
      2. On any v2 failure (yaml not present, datamodule constructor
         strict, weights mismatch), fall back to the base yaml + base
         ckpt. The base path is the proven pre-C5 behaviour.

    The shared `inference.run_model` helper is only published by the
    IBM-NASA base repo; we always pull it from there.
    """
    global _MODEL, _RUN_MODEL
    if _MODEL is not None:
        return _MODEL, _RUN_MODEL
    with _INIT_LOCK:
        if _MODEL is not None:  # double-check inside the lock
            return _MODEL, _RUN_MODEL
        import importlib.util

        from huggingface_hub import hf_hub_download
        from terratorch.cli_tools import LightningInferenceModel
        log.info("prithvi_live: loading model from %s", REPO)

        # Inference helper only lives in the IBM-NASA base repo.
        inference_py = hf_hub_download(BASE_REPO, "inference.py")

        m = None
        # ---- v2 path: yaml + ckpt from the published repo ----------
        if REPO != BASE_REPO:
            try:
                # The v2 repo publishes `prithvi_nyc_phase14.yaml` and
                # `prithvi_nyc_pluvial_v2.ckpt`. Be tolerant of small
                # naming drift (best_val_loss.ckpt etc.) by probing.
                v2_yaml = None
                for name in ("prithvi_nyc_phase14.yaml",
                              "config.yaml", "phase14.yaml",
                              "prithvi_nyc_v2.yaml"):
                    try:
                        v2_yaml = hf_hub_download(REPO, name)
                        break
                    except Exception:
                        continue
                v2_ckpt = None
                for name in ("prithvi_nyc_pluvial_v2.ckpt",
                              "best_val_loss.ckpt", "model.ckpt",
                              "last.ckpt"):
                    try:
                        v2_ckpt = hf_hub_download(REPO, name)
                        break
                    except Exception:
                        continue
                if v2_yaml and v2_ckpt:
                    log.info("prithvi_live: building v2 model from "
                             "yaml=%s ckpt=%s", v2_yaml, v2_ckpt)
                    m = LightningInferenceModel.from_config(v2_yaml, v2_ckpt)
                    # prithvi_nyc_phase14.yaml uses GenericNonGeoSegmentationDataModule
                    # which omits test_transform (→ None) and uses terratorch Normalize
                    # for aug (only handles 4D/5D). IBM inference.py:run_model() calls
                    # both on a 3D dict. Patch both to match the IBM base contract:
                    # ToTensorV2 for test_transform; Kornia AugmentationSequential
                    # (accepts dict input, adds batch dim) for aug.
                    if getattr(getattr(m, 'datamodule', None),
                               'test_transform', None) is None:
                        import albumentations as A
                        import torch as _torch
                        from albumentations.pytorch import ToTensorV2
                        m.datamodule.test_transform = A.Compose([ToTensorV2()])
                        _old = m.datamodule.aug

                        # IBM's inference.py:188 calls
                        # `datamodule.aug({'image': tensor})['image']`.
                        # kornia's AugmentationSequential doesn't accept
                        # dict input cleanly and tripped the
                        # `'list' object has no attribute 'view'`
                        # error on the L4 deploy. Use a hand-rolled
                        # dict-aware normalizer instead — same math,
                        # fewer moving parts, no kornia version skew.
                        class _DictNormalize:
                            def __init__(self, mean, std):
                                self.mean = _torch.as_tensor(mean).view(-1, 1, 1).float()
                                self.std = _torch.as_tensor(std).view(-1, 1, 1).float()

                            def __call__(self, sample):
                                if isinstance(sample, dict):
                                    img = sample["image"]
                                    mean = self.mean.to(img.device)
                                    std = self.std.to(img.device)
                                    return {**sample, "image": (img - mean) / std}
                                mean = self.mean.to(sample.device)
                                std = self.std.to(sample.device)
                                return (sample - mean) / std

                        # `_old.means` / `_old.stds` come from the
                        # yaml as Python lists — calling `.view()` on
                        # them is what tripped the original
                        # `'list' object has no attribute 'view'`.
                        # _DictNormalize handles the conversion via
                        # torch.as_tensor internally; just pass the
                        # raw values whatever their type.
                        m.datamodule.aug = _DictNormalize(_old.means, _old.stds)
                        log.info("prithvi_live: patched v2 datamodule transforms "
                                 "for IBM inference.py compat (dict-aware Normalize)")
                else:
                    log.warning("prithvi_live: v2 yaml/ckpt not "
                                "discoverable in %s; falling back to base",
                                REPO)
            except Exception as e:
                log.warning("prithvi_live: v2 build failed (%s); "
                             "falling back to base", e)
                m = None

        # ---- base path: proven IBM-NASA Sen1Floods11 fine-tune -----
        if m is None:
            base_config = hf_hub_download(BASE_REPO, "config.yaml")
            base_ckpt = hf_hub_download(
                BASE_REPO, "Prithvi-EO-V2-300M-TL-Sen1Floods11.pt")
            m = LightningInferenceModel.from_config(base_config, base_ckpt)

        m.model.eval()
        if DEVICE == "cuda":
            try:
                import torch
                if torch.cuda.is_available():
                    m.model.cuda()
            except Exception:
                log.exception("prithvi_live: cuda move failed")

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


def _fetch_inner(lat: float, lon: float, timeout_s: float) -> dict[str, Any]:
    """Core fetch logic — run inside a bounded thread via fetch()."""
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

        # v0.4.5 — try the MI300X inference service first if configured.
        # On RemoteUnreachable (service down / not configured / 5xx) fall
        # through to the local terratorch path. When remote is configured
        # but returns non-ok we surface that signal directly: the local
        # path on this machine has been brittle (v2 datamodule
        # `test_transform=None` race), so a configured remote is more
        # reliable than the fallback.
        remote_attempted = False
        try:
            from app import inference as _inf
            if _inf.remote_enabled():
                remote_attempted = True
                remote = _inf.prithvi_pluvial(
                    img, scene_id=item.id,
                    scene_datetime=str(item.datetime),
                    cloud_cover=cc,
                    timeout=timeout_s,
                )
                if remote.get("ok"):
                    # Vectorize the remote prediction raster so the map
                    # actually renders the live water polygons. The
                    # droplet returns `pred_b64` (uint8 binary mask);
                    # we polygonize against the chip's WGS84 bounds
                    # which we know locally from `ref_da`.
                    polys = None
                    pred_b64 = remote.get("pred_b64")
                    pred_shape = remote.get("pred_shape")
                    if pred_b64 and pred_shape:
                        try:
                            xs = ref_da.x.values
                            ys = ref_da.y.values
                            from pyproj import Transformer
                            t_inv = Transformer.from_crs(
                                f"EPSG:{epsg}", "EPSG:4326",
                                always_xy=True)
                            minx, maxx = float(xs.min()), float(xs.max())
                            miny, maxy = float(ys.min()), float(ys.max())
                            minlon, minlat = t_inv.transform(minx, miny)
                            maxlon, maxlat = t_inv.transform(maxx, maxy)
                            from app.context._polygonize import (
                                polygonize_binary_mask,
                            )
                            polys = polygonize_binary_mask(
                                pred_b64, pred_shape,
                                (minlon, minlat, maxlon, maxlat),
                                label="water", fill_color="#1F77B4",
                                simplify_tolerance=2e-5,
                            )
                        except Exception:
                            log.exception("prithvi_live: remote polygonize failed")
                            polys = None
                    return {
                        "ok": True,
                        "item_id": item.id,
                        "item_datetime": str(item.datetime),
                        "cloud_cover": cc,
                        "pct_water_full": remote.get("pct_water_full"),
                        "pct_water_within_500m": remote.get("pct_water_within_500m"),
                        "polygons_geojson": polys,
                        "compute": f"remote · {remote.get('device', 'gpu')}",
                        "elapsed_s": round(time.time() - t0, 2),
                    }
                err = (remote.get("err")
                       or remote.get("error")
                       or remote.get("skipped")
                       or "unknown")
                return {"ok": False,
                        "skipped": f"remote prithvi-pluvial non-ok: {err}",
                        "elapsed_s": round(time.time() - t0, 2)}
        except _inf.RemoteUnreachable as e:
            log.info("prithvi_live: remote unreachable (%s)", e)
            if remote_attempted:
                # Don't fall to local — torchvision::nms is broken on the
                # CPU-tier UI Spaces and crashes the FSM specialist with
                # a confusing RuntimeError. Return a clean skipped row so
                # the trace says "remote unreachable" instead.
                return {"ok": False,
                        "skipped": f"remote prithvi-pluvial unreachable: {e}",
                        "elapsed_s": round(time.time() - t0, 2)}
        except Exception as e:
            log.exception("prithvi_live: remote call failed")
            if remote_attempted:
                return {"ok": False,
                        "skipped": f"remote prithvi-pluvial error: "
                                   f"{type(e).__name__}: {e}",
                        "elapsed_s": round(time.time() - t0, 2)}

        # Local fallback — the path that's been live since v0.4.4.
        # Reached only when remote_attempted is False (i.e. remote
        # backend not configured at all).
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
        polygons_geojson = _polygonize_mask(pred, ref_da, epsg)
        # Normalized rendering fields for the type-keyed raster card.
        # Same shape across every raster-pred pebble — the renderer
        # reads headline_value / subhead_text / narrative / raster_kind
        # without knowing which model produced them.
        pct_500_round = round(pct_500, 1)
        scene_date = str(item.datetime)[:10] if item.datetime else None
        narrative = (
            f"Prithvi-EO 2.0 NYC-Pluvial live segmentation: "
            f"{pct_500_round}% water within 500 m of this address."
        )
        if scene_date:
            narrative += f" Sentinel-2 scene from {scene_date}"
            if cc is not None:
                narrative += f" ({round(cc, 1)}% cloud cover)"
            narrative += "."
        return {
            "ok": True,
            "item_id": item.id,
            "item_datetime": str(item.datetime),
            "cloud_cover": cc,
            "pct_water_full": pct_full,
            "pct_water_within_500m": pct_500,
            "polygons_geojson": polygons_geojson,
            "compute": "local",
            "elapsed_s": round(time.time() - t0, 2),
            "headline_value": f"{pct_500_round}% flooded",
            "subhead_text": (
                f"water within 500 m · cloud {round(cc, 1)}%"
                if cc is not None else "water within 500 m"
            ),
            "narrative": narrative,
            "raster_kind": "prithvi",
            "illustrative": True,
        }
    except Exception as e:
        log.exception("prithvi_live: fetch failed")
        return {"ok": False, "err": f"{type(e).__name__}: {e}",
                "elapsed_s": round(time.time() - t0, 2)}


def fetch(lat: float, lon: float, timeout_s: float = 60.0) -> dict[str, Any]:
    """Run the specialist. Wraps _fetch_inner in a bounded thread so that
    STAC searches and COG band reads (which lack per-request HTTP timeouts)
    cannot hang the FSM indefinitely.

    Returns a dict with at minimum:
        { "ok": bool, "skipped": str | None, "item_id": str | None,
          "cloud_cover": float | None, "pct_water_within_500m": float | None }
    Designed to never raise; failures show up as ok=False with an `err`.
    """
    if not ENABLE:
        return {"ok": False, "skipped": "RIPRAP_PRITHVI_LIVE_ENABLE=0"}
    if not _DEPS_OK:
        return {"ok": False,
                "skipped": f"deps unavailable on this deployment: "
                           f"{_DEPS_MISSING}"}
    hard_timeout = timeout_s + 15.0
    from app import emissions as _emissions
    _parent_tracker = _emissions.current()
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=1,
        initializer=lambda t=_parent_tracker: _emissions.install(t),
    ) as pool:
        future = pool.submit(_fetch_inner, lat, lon, timeout_s)
        try:
            return future.result(timeout=hard_timeout)
        except concurrent.futures.TimeoutError:
            log.warning("prithvi_live: hard timeout after %.0fs (STAC/COG hung)",
                        hard_timeout)
            return {"ok": False,
                    "skipped": f"prithvi_live timed out after {hard_timeout:.0f}s"}
