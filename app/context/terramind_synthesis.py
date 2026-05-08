"""TerraMind v1 base as a real-time FSM node — DEM → ESRI LULC.

Per user query: take the geocoded (lat, lon), pull a DEM patch from
Riprap's existing NYC-wide LiDAR raster (already used by the microtopo
specialist — no STAC dependency), run TerraMind to generate a
plausible categorical land-cover map from the terrain context, and
emit class fractions the reconciler can cite as a synthetic-prior
context layer alongside the empirical and modeled flood evidence.

Why DEM → LULC (and not DEM → S2L2A as initially prototyped):
  - LULC is *categorical* and *interpretable*. The output is one of
    10 ESRI Land Cover classes per pixel; class fractions like "78%
    Built Area" go straight into the briefing as cite-able claims.
  - S2L2A is 12-channel reflectance — uninterpretable downstream
    without a separate segmentation head.
  - LULC is *comparable to ground truth*: NYC PLUTO land-use class
    is already in the data layer; future calibration possible.

Class label mapping is *tentative* against ESRI 2020-2022 schema
(which TerraMesh's LULC tokenizer was trained on). The doc body
discloses the mapping as tentative and the reconciler is instructed
to use hedged framing ("the synthetic land-cover prior identifies …
likely class …") rather than asserting hard labels.

Why this shape:
  - **No STAC dependency.** Microsoft Planetary Computer search has
    been intermittent during this hackathon; the DEM raster is local
    and always available.
  - **Real-time.** < 0.3 s synthesis + < 0.5 s DEM patch read on M3
    CPU once warm.
  - **Honesty discipline.** Synthetic-prior tier, fourth epistemic
    class alongside empirical / modeled / proxy.

License: Apache-2.0 — `ibm-esa-geospatial/TerraMind-1.0-base`.
"""

from __future__ import annotations

import logging
import os
import random
import threading
import time
from typing import Any

log = logging.getLogger("riprap.terramind")

ENABLE = os.environ.get("RIPRAP_TERRAMIND_ENABLE", "1").lower() in ("1", "true", "yes")
DEFAULT_STEPS = int(os.environ.get("RIPRAP_TERRAMIND_STEPS", "10"))
DEFAULT_SEED = int(os.environ.get("RIPRAP_TERRAMIND_SEED", "42"))
CHIP_PX = int(os.environ.get("RIPRAP_TERRAMIND_CHIP_PX", "224"))
CHIP_M = CHIP_PX * 30  # NYC DEM is at 30 m -> 6.72 km square
HALF_M = CHIP_M / 2

_MODEL = None
_INIT_LOCK = threading.Lock()

# Tentative ESRI 2020-2022 Land Cover class mapping for TerraMind v1's
# LULC tokenizer output (10 channels, argmax over channel axis -> class
# index 0-9). The README/docs don't expose the exact mapping and the
# tokenizer source confirms only "ESRI LULC" without a label table, so
# the names below are best-effort. The doc body discloses tentativeness.
LULC_CLASSES = [
    "water",                # 0
    "trees",                # 1
    "grass",                # 2
    "flooded_vegetation",   # 3
    "crops",                # 4
    "scrub_shrub",          # 5
    "built_area",           # 6
    "bare_ground",          # 7
    "snow_ice",             # 8
    "clouds_or_no_data",    # 9
]


def _has_required_deps() -> tuple[bool, str | None]:
    """Probe deps. terramind_synthesis runs only locally (no remote path
    in app/inference.py for DEM-driven synthesis), so it always needs
    terratorch. On the HF Space terratorch isn't installed, so this
    specialist returns a clean `skipped: deps unavailable` outcome.

    Distinguishes a *truly missing* package (ModuleNotFoundError) from
    a *transient race* (other ImportError — typically sklearn's
    "partially initialized module" from concurrent imports)."""
    missing = []
    for name in ("terratorch", "rasterio"):
        try:
            __import__(name)
        except ModuleNotFoundError:
            missing.append(name)
        except ImportError:
            log.debug("terramind: import race on %s, will retry on demand", name)
        except Exception as e:
            # torchvision::nms RuntimeError on HF Space — local inference
            # is unavailable; treat as missing so fetch() returns a clean
            # skip rather than crashing in _ensure_model.
            log.warning("terramind: %s import raised %s; treating as "
                        "unavailable", name, type(e).__name__)
            missing.append(f"{name} ({type(e).__name__})")
    return (not missing, ", ".join(missing) if missing else None)


_DEPS_OK, _DEPS_MISSING = _has_required_deps()


def _ensure_model():
    """Lazy load with a lock so the parallel-block worker can't double-init."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _INIT_LOCK:
        if _MODEL is not None:
            return _MODEL
        # Heavy import deferred to first call so module import stays cheap
        # and HF Spaces (no terratorch) doesn't pay it at all.
        import terratorch.models.backbones.terramind.model.terramind_register  # noqa
        from terratorch.registry import FULL_MODEL_REGISTRY
        log.info("terramind: loading v1 base generate (DEM -> LULC)")
        m = FULL_MODEL_REGISTRY.build(
            "terratorch_terramind_v1_base_generate",
            modalities=["DEM"],
            output_modalities=["LULC"],
            pretrained=True,
            timesteps=DEFAULT_STEPS,
        )
        m.eval()
        _MODEL = m
        log.info("terramind: model ready")
    return _MODEL


def warm():
    """Call at app boot to amortize the ~6 s checkpoint load + first-call
    JIT. No-op when deps are absent."""
    if ENABLE and _DEPS_OK:
        try:
            _ensure_model()
        except Exception:
            log.exception("terramind: warm() failed; specialist will no-op")


def _read_dem_patch(lat: float, lon: float):
    """Read a CHIP_PX×CHIP_PX DEM patch centered on (lat, lon) from the
    local NYC-wide LiDAR raster. Returns (array, bounds_4326) where
    bounds_4326 is (minlon, minlat, maxlon, maxlat) so the synthesised
    LULC can be georeferenced onto the same extent for map rendering.
    Returns None if outside the raster's extent."""
    from pathlib import Path

    import numpy as np
    import rasterio
    from rasterio.windows import from_bounds
    dem_path = (Path(__file__).resolve().parents[2]
                / "data" / "nyc_dem_30m.tif")
    if not dem_path.exists():
        return None
    with rasterio.open(dem_path) as src:
        # The DEM is in EPSG:4326 (geographic) in our cache — convert
        # the chip extent in the same CRS by building a rough degree
        # bbox from a meters-square half-side at NYC latitude.
        # 1 degree lat ≈ 111 km, 1 degree lon ≈ 85 km at 40.7°N.
        d_lat = (HALF_M / 111_000.0)
        d_lon = (HALF_M / 85_000.0)
        win = from_bounds(lon - d_lon, lat - d_lat,
                          lon + d_lon, lat + d_lat,
                          src.transform)
        arr = src.read(1, window=win, boundless=True, fill_value=0).astype("float32")
    if arr.size == 0 or arr.shape[0] < 8 or arr.shape[1] < 8:
        return None
    # Resize to CHIP_PX × CHIP_PX via torch interpolation. The exact
    # pixel-perfect alignment doesn't matter for a synthetic prior; the
    # model just needs a real terrain patch to condition on.
    import torch
    t = torch.from_numpy(arr).unsqueeze(0).unsqueeze(0)
    t = torch.nn.functional.interpolate(t, size=(CHIP_PX, CHIP_PX),
                                         mode="bilinear", align_corners=False)
    out = t.squeeze(0).numpy()  # (1, CHIP_PX, CHIP_PX)
    # Replace NaN sentinel values with median elevation so the model
    # doesn't see NaN tokens.
    if np.isnan(out).any():
        med = float(np.nanmedian(out))
        out = np.nan_to_num(out, nan=med)
    bounds_4326 = (lon - d_lon, lat - d_lat, lon + d_lon, lat + d_lat)
    return out, bounds_4326


# Map class index -> visual color for the categorical fill on the
# MapLibre layer. Colors picked to be visually distinct from the
# existing red (Sandy) / blue (DEP) / cyan (Prithvi) / orange (Ida HWM).
LULC_FILL_COLORS = {
    "water":              "#0284c7",  # not used (we keep water clear so
                                       # the underlying basemap shows)
    "trees":              "#16a34a",  # green
    "grass":              "#86efac",  # pale green
    "flooded_vegetation": "#a3e635",  # lime
    "crops":              "#fde047",  # yellow
    "scrub_shrub":        "#bef264",
    "built_area":         "#9ca3af",  # neutral gray
    "bare_ground":        "#d6d3d1",  # warm light gray
    "snow_ice":           "#f3f4f6",
    "clouds_or_no_data":  "#000000",  # not used (kept transparent)
}
# Classes we don't render at all (transparent) — water is best left
# uncolored so the basemap shoreline reads through; clouds/no-data is
# semantically meaningless to fill.
LULC_HIDE_CLASSES = {"water", "clouds_or_no_data"}


def _polygonize_lulc(class_idx, bounds_4326: tuple) -> dict:
    """Vectorize the per-pixel argmax classification into one MultiPolygon
    per class label, then dump as a single GeoJSON FeatureCollection in
    EPSG:4326. Each feature carries `label` + `class_idx` properties so
    the frontend can colour by category.
    """
    import json

    import geopandas as gpd
    from rasterio.features import shapes
    from rasterio.transform import from_bounds as transform_from_bounds
    from shapely.geometry import shape

    minlon, minlat, maxlon, maxlat = bounds_4326
    h, w = class_idx.shape
    transform = transform_from_bounds(minlon, minlat, maxlon, maxlat, w, h)
    feats = []
    for i, label in enumerate(LULC_CLASSES):
        if label in LULC_HIDE_CLASSES:
            continue
        mask = (class_idx == i).astype("uint8")
        if mask.sum() < 8:  # skip tiny noise
            continue
        polys = []
        for geom, value in shapes(mask, mask=mask.astype(bool),
                                   transform=transform):
            if value != 1:
                continue
            polys.append(shape(geom))
        if not polys:
            continue
        # Dissolve via geopandas + simplify lightly. The chip is 30 m
        # per pixel and we don't need pixel-edge fidelity at urban zoom.
        gdf = gpd.GeoDataFrame({"geometry": polys}, crs="EPSG:4326")
        gdf["geometry"] = gdf.geometry.simplify(1e-4, preserve_topology=True)
        for geom in gdf.geometry:
            feats.append({
                "type": "Feature",
                "geometry": json.loads(gpd.GeoSeries([geom],
                                                    crs="EPSG:4326").to_json())["features"][0]["geometry"],
                "properties": {"label": label, "class_idx": i,
                               "fill_color": LULC_FILL_COLORS.get(label, "#9ca3af")},
            })
    return {"type": "FeatureCollection", "features": feats}


def fetch(lat: float, lon: float, timeout_s: float = 60.0) -> dict[str, Any]:
    """Run the specialist. Returns:
        { ok: bool,
          skipped: str | None,
          synthetic_modality: bool,
          tim_chain: list[str],
          diffusion_steps: int, diffusion_seed: int,
          dem_mean_m: float,
          class_fractions: dict[str, float],  # tentative ESRI labels
          dominant_class: str,                 # highest-fraction label
          dominant_pct: float,
          n_classes_observed: int,
          chip_shape: list[int],
          elapsed_s: float,
          err: str | None }

    Designed never to raise. Failures show up as ok=False with reason.
    """
    if not ENABLE:
        return {"ok": False, "skipped": "RIPRAP_TERRAMIND_ENABLE=0"}
    t0 = time.time()
    try:
        import numpy as np
        patch = _read_dem_patch(lat, lon)
        if patch is None:
            return {"ok": False, "skipped": "no DEM coverage at this point"}
        dem, bounds_4326 = patch
        dem_mean = float(dem.mean())

        # v0.4.5+ — try the MI300X inference service first if configured.
        # The droplet's /v1/terramind dispatch handles adapter='synthesis'
        # via _terramind_synthesis_inference (DEM -> generative LULC). On
        # the HF Space terratorch's torchvision binary doesn't load, so
        # this is the only working path there.
        try:
            from app import inference as _inf
            if _inf.remote_enabled():
                # The terramind v1 base generative encoder embedding
                # layer unpacks `B, C, H, W = x.shape` (verified against
                # terratorch_terramind_v1_base_generate). DEM has C=1, so
                # the on-the-wire shape is (1, 1, H, W) 4-D.
                # `_read_dem_patch` returns a 3-D (1, H, W) array (it
                # interpolates to CHIP_PX×CHIP_PX through a 4-D
                # torch.functional.interpolate then squeezes the batch),
                # so we add only the batch dim — not two.
                import numpy as _np_local
                dem_arr = _np_local.asarray(dem, dtype="float32")
                if dem_arr.ndim == 2:                # (H, W)
                    dem_remote = dem_arr[None, None, :, :]
                elif dem_arr.ndim == 3:              # (1, H, W)
                    dem_remote = dem_arr[None, :, :, :]
                elif dem_arr.ndim == 4:              # already (1, 1, H, W)
                    dem_remote = dem_arr
                else:
                    raise ValueError(
                        f"unexpected DEM shape {dem_arr.shape}; "
                        "expected 2/3/4-D")
                remote = _inf.terramind("synthesis", None, None, dem_remote,
                                          timeout=timeout_s)
                if remote.get("ok"):
                    elapsed = round(time.time() - t0, 2)
                    # Polygonize the prediction raster for the map
                    # layer. The droplet returns the per-pixel argmax;
                    # we vectorize against the chip's bounds.
                    polys = None
                    pred_b64 = remote.get("pred_b64")
                    pred_shape = remote.get("pred_shape")
                    class_labels = (remote.get("class_labels")
                                    or LULC_CLASSES)
                    if pred_b64 and pred_shape:
                        try:
                            from app.context._polygonize import (
                                polygonize_class_raster,
                            )
                            polys = polygonize_class_raster(
                                pred_b64, pred_shape, class_labels,
                                tuple(bounds_4326),
                                simplify_tolerance=2e-5,
                            )
                        except Exception:
                            log.exception("terramind/synthesis: "
                                          "polygonize failed")
                            polys = None
                    out = {
                        "ok": True,
                        "synthetic_modality": True,
                        "tim_chain": ["DEM", "LULC_synthetic"],
                        "diffusion_steps": remote.get("diffusion_steps",
                                                       DEFAULT_STEPS),
                        "diffusion_seed": DEFAULT_SEED,
                        "dem_mean_m": round(dem_mean, 2),
                        "class_fractions": remote.get("class_fractions") or {},
                        "dominant_class": remote.get("dominant_class") or "unknown",
                        "dominant_pct": remote.get("dominant_pct") or 0.0,
                        "n_classes_observed": remote.get("n_classes_observed") or 0,
                        "chip_shape": remote.get("shape") or [],
                        "bounds_4326": list(bounds_4326),
                        "polygons_geojson": polys,
                        "label_schema": remote.get("label_schema") or "",
                        "compute": f"remote · {remote.get('device', 'gpu')}",
                        "elapsed_s": elapsed,
                    }
                    return out
                # remote returned non-ok — surface that signal directly
                return {"ok": False,
                        "skipped": f"remote terramind synthesis non-ok: "
                                   f"{remote.get('error') or remote.get('detail') or 'unknown'}",
                        "elapsed_s": round(time.time() - t0, 2)}
        except _inf.RemoteUnreachable as e:
            log.info("terramind_synthesis: remote unreachable (%s); local fallback", e)
        except Exception as e:
            log.exception("terramind_synthesis: remote call failed")
            return {"ok": False,
                    "skipped": f"remote terramind synthesis error: "
                               f"{type(e).__name__}: {e}",
                    "elapsed_s": round(time.time() - t0, 2)}

        # Local fallback — original path; only available where terratorch
        # imports without the torchvision::nms RuntimeError.
        if not _DEPS_OK:
            return {"ok": False, "skipped": f"deps unavailable: {_DEPS_MISSING}"}
        import torch
        random.seed(DEFAULT_SEED)
        torch.manual_seed(DEFAULT_SEED)

        model = _ensure_model()
        # `dem` is 2-D (H, W) from `_read_dem_patch.src.read(1, ...)`. The
        # terramind v1 base generative encoder wants (B=1, C=1, H, W) 4-D.
        dem_t = torch.from_numpy(dem).unsqueeze(0).unsqueeze(0).float()
        if time.time() - t0 > timeout_s:
            return {"ok": False, "skipped": "terramind exceeded budget"}

        with torch.no_grad():
            out = model({"DEM": dem_t}, timesteps=DEFAULT_STEPS,
                        verbose=False)
        lulc = out["LULC"]
        if hasattr(lulc, "detach"):
            lulc = lulc.detach().cpu().numpy()
        if lulc.ndim == 4:
            lulc = lulc[0]  # (n_classes, H, W)
        # Argmax over class channel -> per-pixel class index, then
        # fraction by class. This is the cite-able structured output.
        class_idx = lulc.argmax(axis=0)  # (H, W)
        unique, counts = np.unique(class_idx, return_counts=True)
        total = float(class_idx.size)
        fractions: dict[str, float] = {}
        for u, c in zip(unique, counts, strict=False):
            label = (LULC_CLASSES[int(u)] if 0 <= int(u) < len(LULC_CLASSES)
                     else f"class_{int(u)}")
            fractions[label] = round(100.0 * c / total, 2)
        # Sort dominant -> tail for deterministic doc body ordering.
        ordered = dict(sorted(fractions.items(),
                              key=lambda kv: kv[1], reverse=True))
        dominant_class = next(iter(ordered)) if ordered else "unknown"
        dominant_pct = ordered.get(dominant_class, 0.0)
        # Class indices map to TerraMesh's LULC tokenizer codebook; the
        # exact label-to-index mapping isn't published. Surface a tentative
        # name plus the raw index so a reader can see we're not asserting
        # ground truth.
        dominant_idx = next((i for i, lbl in enumerate(LULC_CLASSES)
                             if lbl == dominant_class), -1)
        dominant_display = (
            f"class_{dominant_idx} (tentative: {dominant_class})"
            if dominant_idx >= 0 else dominant_class
        )

        # Polygonize the categorical raster for the map layer.
        # Best-effort — failure here doesn't fail the specialist.
        try:
            polygons_geojson = _polygonize_lulc(class_idx, bounds_4326)
        except Exception:
            log.exception("terramind: polygonize failed; skipping map layer")
            polygons_geojson = None

        return {
            "ok": True,
            "synthetic_modality": True,
            "tim_chain": ["DEM", "LULC_synthetic"],
            "diffusion_steps": DEFAULT_STEPS,
            "diffusion_seed": DEFAULT_SEED,
            "dem_mean_m": round(dem_mean, 2),
            "class_fractions": ordered,
            "dominant_class": dominant_class,
            "dominant_class_display": dominant_display,
            "dominant_pct": dominant_pct,
            "n_classes_observed": len(ordered),
            "chip_shape": list(lulc.shape),
            "bounds_4326": list(bounds_4326),
            "polygons_geojson": polygons_geojson,
            "label_schema": "ESRI 2020-2022 Land Cover (tentative — "
                            "TerraMind tokenizer source confirms ESRI but "
                            "not exact label-to-index mapping)",
            "elapsed_s": round(time.time() - t0, 2),
        }
    except Exception as e:
        msg = str(e)
        # Translate the torchvision binary-extension failure into a clean
        # skip. The HF Space ships torchvision via a transitive sentence-
        # transformers dep, but its C extension can't load alongside our
        # CPU torch wheel, so terratorch's NMS call raises RuntimeError.
        # Surface this honestly — the local inference path is unavailable
        # on this deployment, same outcome as a missing terratorch.
        if "torchvision::nms" in msg or "torchvision_C" in msg:
            log.warning("terramind: torchvision binary unavailable on this "
                        "deployment; skipping local inference")
            return {"ok": False,
                    "skipped": "local inference unavailable on this "
                               "deployment (torchvision binary extension "
                               "not loadable); no remote synthesis path",
                    "elapsed_s": round(time.time() - t0, 2)}
        log.exception("terramind: fetch failed")
        return {"ok": False, "err": f"{type(e).__name__}: {e}",
                "elapsed_s": round(time.time() - t0, 2)}
