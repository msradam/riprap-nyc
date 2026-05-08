"""Vectorize a uint8 prediction raster (binary mask or class index)
into an EPSG:4326 GeoJSON FeatureCollection so the frontend can paint
it on the MapLibre map.

The droplet's `/v1/prithvi-pluvial` and `/v1/terramind` routes return
their predictions as base64-encoded uint8 with a shape and (where
relevant) a class-label list. This module reconstructs the affine
transform from the chip's geographic bounds (which the HF Space
already knows) and walks `rasterio.features.shapes` to build polygons
in the chip's native CRS, then reprojects to WGS84 for the map.

Best-effort: any failure returns an empty FeatureCollection rather
than raising into the caller's path. The map layer is decorative —
the briefing is the deliverable.
"""
from __future__ import annotations

import base64
import logging

log = logging.getLogger("riprap.polygonize")

EMPTY: dict = {"type": "FeatureCollection", "features": []}


def _decode_pred(pred_b64: str, pred_shape: list[int]):
    """Inverse of the droplet's `base64(pred.tobytes())`. Returns a
    uint8 numpy array of shape `pred_shape`, or None on decode error."""
    try:
        import numpy as np
        raw = base64.b64decode(pred_b64)
        return np.frombuffer(raw, dtype="uint8").reshape(pred_shape)
    except Exception:
        log.exception("polygonize: pred decode failed")
        return None


def polygonize_class_raster(
    pred_b64: str,
    pred_shape: list[int],
    class_labels: list[str] | None,
    bounds_4326: tuple[float, float, float, float],
    *,
    drop_classes: tuple[int, ...] = (0,),
    simplify_tolerance: float = 0.0,
) -> dict:
    """Vectorize a categorical prediction raster (one integer class per
    pixel) into a FeatureCollection with one Feature per connected
    polygon. `bounds_4326` is `(minlon, minlat, maxlon, maxlat)` of the
    chip; the raster is assumed to span those bounds at uniform
    pixel size. Each feature carries `class_idx` and `class_label`
    so the frontend can color by class.

    `drop_classes`: skip pixels matching these class indices (default
    drops 0 = "Background" / "outside" / etc).
    """
    pred = _decode_pred(pred_b64, pred_shape)
    if pred is None:
        return EMPTY
    try:
        from rasterio.features import shapes
        from rasterio.transform import from_bounds
        from shapely.geometry import shape
        h, w = pred.shape
        minlon, minlat, maxlon, maxlat = bounds_4326
        # The chip is in EPSG:4326 for our use — Sentinel-2 chips are
        # natively in their UTM zone, but we can polygonize against the
        # WGS84 extent because the inference chip is a small bbox where
        # the pixel-grid → lat/lon mapping is locally affine (sub-pixel
        # error at NYC scale).
        transform = from_bounds(minlon, minlat, maxlon, maxlat, w, h)
        feats = []
        for geom, value in shapes(pred, mask=pred > 0, transform=transform):
            v = int(value)
            if v in drop_classes:
                continue
            label = (class_labels[v]
                     if class_labels and 0 <= v < len(class_labels)
                     else f"class_{v}")
            poly = shape(geom)
            if simplify_tolerance > 0:
                poly = poly.simplify(simplify_tolerance, preserve_topology=True)
            if poly.is_empty:
                continue
            feats.append({
                "type": "Feature",
                "geometry": poly.__geo_interface__,
                "properties": {
                    "class_idx": v,
                    "class_label": label,
                    "fill_color": _PALETTE.get(label.lower(), _DEFAULT_FILL),
                },
            })
        return {"type": "FeatureCollection", "features": feats}
    except Exception:
        log.exception("polygonize: class raster vectorisation failed")
        return EMPTY


def polygonize_binary_mask(
    pred_b64: str,
    pred_shape: list[int],
    bounds_4326: tuple[float, float, float, float],
    *,
    label: str = "water",
    fill_color: str = "#4A90E2",
    simplify_tolerance: float = 0.0,
) -> dict:
    """Vectorize a binary prediction raster (e.g. Prithvi water mask;
    1 = water, 0 = not). Returns one Feature per connected positive
    region. Use this for prithvi_eo_live and the buildings LoRA."""
    pred = _decode_pred(pred_b64, pred_shape)
    if pred is None:
        return EMPTY
    try:
        from rasterio.features import shapes
        from rasterio.transform import from_bounds
        from shapely.geometry import shape
        h, w = pred.shape
        minlon, minlat, maxlon, maxlat = bounds_4326
        transform = from_bounds(minlon, minlat, maxlon, maxlat, w, h)
        feats = []
        for geom, _value in shapes(pred, mask=pred > 0, transform=transform):
            poly = shape(geom)
            if simplify_tolerance > 0:
                poly = poly.simplify(simplify_tolerance, preserve_topology=True)
            if poly.is_empty:
                continue
            feats.append({
                "type": "Feature",
                "geometry": poly.__geo_interface__,
                "properties": {
                    "class_label": label,
                    "fill_color": fill_color,
                },
            })
        return {"type": "FeatureCollection", "features": feats}
    except Exception:
        log.exception("polygonize: binary mask vectorisation failed")
        return EMPTY


# Lightweight palette used by the LULC + buildings layers. Frontend
# may override via `fill_color` per feature; this is a sensible
# default keyed on lowercase class labels.
_DEFAULT_FILL = "#A0A0A0"
_PALETTE = {
    # ESRI 2020 LULC schema (terramind v1 base generative)
    "water":              "#1F77B4",
    "trees":              "#2CA02C",
    "grass":              "#7FBF53",
    "flooded vegetation": "#74C476",
    "crops":              "#E1C75A",
    "scrub/shrub":        "#A6BC44",
    "built":              "#D62728",
    "bare ground":        "#B07A4C",
    "snow/ice":            "#E0E7EC",
    "clouds":              "#CCCCCC",
    # NYC LoRA LULC schema
    "cropland":           "#E1C75A",
    "bare":               "#B07A4C",
    # Buildings LoRA
    "building":           "#D62728",
    "background":         _DEFAULT_FILL,
}
