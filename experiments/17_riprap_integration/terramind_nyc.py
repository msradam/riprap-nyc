"""TerraMind-NYC specialist for Riprap — replaces zero-shot terramind_synthesis.

Loads our AMD-trained NYC checkpoints, fetches recent Sentinel-1 + Sentinel-2 +
DEM at the queried (lat, lon) via the live STAC path from
experiments/11_live_sentinel_fetch, runs inference, returns a structured dict
in the same shape the reconciler already expects.

Output contract (compatible with `app/context/terramind_synthesis.py:fetch`):

    {
      "ok": True,
      "synthetic_modality": True,
      "tim_chain": ["S2L2A", "S1RTC", "DEM", "LULC_predicted"],
      "label_schema": "ESA WorldCover 2021 v200, 5 macro-classes (confirmed)",
      "model": "msradam/TerraMind-base-Flood-NYC (AMD MI300X fine-tune)",
      "imagery": {
          "s2_acquired_iso": "2026-05-04T16:01:44Z",
          "s2_age_days": 1,
          "s2_cloud_pct": 7.0,
          "s2_source": "Element 84 Earth Search (ESA Copernicus License)",
          "s1_acquired_iso": "2026-05-01T22:51:31Z",
          "s1_age_days": 4,
          "s1_source": "Microsoft Planetary Computer (ESA Copernicus License)",
      },
      "class_fractions": {"developed": 78.3, "forest": 8.1, "water": 7.4, ...},
      "dominant_class": "developed",
      "dominant_pct": 78.3,
      "imperviousness_pct": 78.3,
      "green_space_pct": 13.7,
      "water_pct": 7.4,
      "polygons_geojson": {...},
      "elapsed_s": 5.2,
    }

Drop-in replacement for `app/context/terramind_synthesis.py:fetch(lat, lon)`.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

log = logging.getLogger("riprap.terramind_nyc")

ENABLE = os.environ.get("RIPRAP_TERRAMIND_NYC_ENABLE", "1").lower() in ("1", "true", "yes")
HF_REPO = os.environ.get("RIPRAP_TERRAMIND_NYC_REPO",
                          "msradam/TerraMind-base-Flood-NYC")
CHIP_PX = 256
CACHE_DIR = os.environ.get("RIPRAP_TERRAMIND_NYC_CACHE",
                            "/tmp/riprap_terramind_nyc_cache")

_MODEL = None
_MODEL_LOCK = threading.Lock()
_CONFIG_PATH = None
_CKPT_PATH = None

# WorldCover 5-macro-class palette for the GeoJSON polygons
COLORS = {
    0: ("water",      "#0284c7"),
    1: ("developed",  "#9ca3af"),
    2: ("forest",     "#16a34a"),
    3: ("herbaceous", "#86efac"),
    4: ("other",      "#d6d3d1"),
}
# Classes we don't paint (water best left transparent so basemap shoreline shows;
# "other" is too small in NYC to be informative)
HIDE_CLASSES = {"water", "other"}


def _ensure_model():
    """Lazy load the AMD-fine-tuned NYC checkpoint."""
    global _MODEL, _CONFIG_PATH, _CKPT_PATH
    if _MODEL is not None:
        return _MODEL
    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL
        from huggingface_hub import hf_hub_download
        from terratorch.tasks import SemanticSegmentationTask
        from safetensors.torch import load_file
        import torch
        import yaml as yamllib

        log.info("terramind_nyc: fetching from HF %s", HF_REPO)
        yaml_p = hf_hub_download(repo_id=HF_REPO,
                                  filename="terramind_v1_base_nyc_phase2.yaml",
                                  cache_dir=CACHE_DIR)
        ckpt_p = hf_hub_download(repo_id=HF_REPO,
                                  filename="TerraMind_v1_base_NYC_LULC.safetensors",
                                  cache_dir=CACHE_DIR)
        cfg = yamllib.safe_load(open(yaml_p))
        task = SemanticSegmentationTask(**cfg["model"]["init_args"])
        state = load_file(ckpt_p)
        state = {k: v for k, v in state.items() if not k.startswith("criterion.")}
        task.load_state_dict(state, strict=False)

        device = ("cuda" if torch.cuda.is_available()
                  else "mps" if torch.backends.mps.is_available()
                  else "cpu")
        _MODEL = task.to(device).eval()
        _CONFIG_PATH, _CKPT_PATH = yaml_p, ckpt_p
        log.info("terramind_nyc: model on %s", device)
    return _MODEL


def warm():
    if ENABLE:
        try:
            _ensure_model()
        except Exception:
            log.exception("terramind_nyc: warm() failed; specialist will no-op")


def _normalize_inputs(s2: "np.ndarray", s1: "np.ndarray", dem: "np.ndarray"):
    """ImpactMesh-flood per-band normalization. The model was trained with these
    z-scores; inference must match."""
    import numpy as np
    S2_MEAN = np.array([1223.128, 1251.355, 1423.443, 1408.984, 1786.818, 2448.316,
                        2685.642, 2745.795, 2817.936, 3194.081, 1964.659, 1399.317],
                       dtype=np.float32)
    S2_STD = np.array([2358.709, 2227.598, 2082.363, 2068.519, 2086.682, 2003.085,
                       2019.494, 2060.309, 2014.732, 2992.644, 1414.951, 1218.357],
                      dtype=np.float32)
    S1_MEAN = np.array([-9.98, -15.968], dtype=np.float32)
    S1_STD = np.array([4.24, 4.105], dtype=np.float32)
    DEM_MEAN, DEM_STD = 141.786, 189.363
    s2n = (s2 - S2_MEAN[:, None, None]) / S2_STD[:, None, None]
    s1n = (s1 - S1_MEAN[:, None, None]) / S1_STD[:, None, None]
    demn = (dem - DEM_MEAN) / DEM_STD
    return s2n, s1n, demn


def _polygonize_pred(class_idx, transform, crs):
    """Vectorize per-class predictions into a GeoJSON FeatureCollection."""
    import json
    import geopandas as gpd
    from rasterio.features import shapes
    from shapely.geometry import shape
    import numpy as np

    feats = []
    for c, (label, color) in COLORS.items():
        if label in HIDE_CLASSES:
            continue
        mask = (class_idx == c).astype("uint8")
        if mask.sum() < 8:
            continue
        polys = [shape(geom) for geom, val in
                 shapes(mask, mask=mask.astype(bool), transform=transform)
                 if val == 1]
        if not polys:
            continue
        gdf = gpd.GeoDataFrame({"geometry": polys}, crs=crs).to_crs("EPSG:4326")
        gdf["geometry"] = gdf.geometry.simplify(1e-4, preserve_topology=True)
        for geom in gdf.geometry:
            feats.append({
                "type": "Feature",
                "geometry": json.loads(
                    gpd.GeoSeries([geom], crs="EPSG:4326").to_json()
                )["features"][0]["geometry"],
                "properties": {"label": label, "class_idx": c, "fill_color": color},
            })
    return {"type": "FeatureCollection", "features": feats}


def fetch(lat: float, lon: float, timeout_s: float = 30.0) -> dict[str, Any]:
    """Run the AMD-trained TerraMind-NYC specialist at (lat, lon).

    Returns a dict matching the existing terramind_synthesis output schema,
    plus new fields for imagery freshness disclosure. Designed to never raise.
    """
    if not ENABLE:
        return {"ok": False, "skipped": "RIPRAP_TERRAMIND_NYC_ENABLE=0"}
    t0 = time.time()
    try:
        import collections
        import numpy as np
        import torch

        # Late-import the live Sentinel fetch (it lives next to us in app/context)
        from app.context.sentinel_live import fetch_recent_chips

        # Get most-recent S2 + S1 + DEM at this point (Earth Search + PC fallback)
        chips = fetch_recent_chips(lat, lon, chip_px=CHIP_PX,
                                    max_age_days=14, max_cloud=30)
        if not chips or not chips.get("ok"):
            return {"ok": False, "skipped": "no recent imagery for this point"}

        s2 = chips["s2"]            # (12, 256, 256) float32, raw L2A reflectance
        s1 = chips["s1"]            # (2, 256, 256) float32, RTC sigma0 linear
        dem = chips["dem"]          # (256, 256) float32

        s2n, s1n, demn = _normalize_inputs(s2, s1, dem)

        model = _ensure_model()
        device = next(model.parameters()).device
        # (B, C, T, H, W) — repeat single timestep 4× (matches Phase 2 training)
        T = 4
        s2_t = torch.from_numpy(s2n).unsqueeze(1).repeat(1, T, 1, 1).unsqueeze(0).to(device)
        s1_t = torch.from_numpy(s1n).unsqueeze(1).repeat(1, T, 1, 1).unsqueeze(0).to(device)
        dem_t = torch.from_numpy(demn).unsqueeze(0).unsqueeze(0).repeat(1, T, 1, 1).unsqueeze(0).to(device)

        if time.time() - t0 > timeout_s:
            return {"ok": False, "skipped": "exceeded timeout before inference"}

        with torch.no_grad():
            out = model({"S2L2A": s2_t, "S1RTC": s1_t, "DEM": dem_t})
        logits = out.output if hasattr(out, "output") else out
        if isinstance(logits, (list, tuple)):
            logits = logits[0]
        pred = logits.argmax(1)[0].cpu().numpy().astype(np.int8)

        hist = collections.Counter(pred.flatten().tolist())
        total = float(pred.size)
        fractions = {COLORS[c][0]: round(100.0 * v / total, 2)
                     for c, v in hist.items() if 0 <= c < 5}
        ordered = dict(sorted(fractions.items(),
                              key=lambda kv: kv[1], reverse=True))
        dominant = next(iter(ordered)) if ordered else "unknown"

        # Polygonize for the map layer
        polygons = None
        try:
            polygons = _polygonize_pred(pred, chips["transform"], chips["crs"])
        except Exception:
            log.exception("terramind_nyc: polygonize failed; skipping map layer")

        return {
            "ok": True,
            "synthetic_modality": True,
            "tim_chain": ["S2L2A", "S1RTC", "DEM", "LULC_predicted"],
            "label_schema": "ESA WorldCover 2021 v200, 5 macro-classes (confirmed)",
            "model": f"{HF_REPO} (AMD MI300X fine-tune)",
            "imagery": {
                "s2_acquired_iso":  chips["s2_acquired_iso"],
                "s2_age_days":      chips["s2_age_days"],
                "s2_cloud_pct":     chips.get("s2_cloud_pct"),
                "s2_source":        chips["s2_source"],
                "s1_acquired_iso":  chips["s1_acquired_iso"],
                "s1_age_days":      chips["s1_age_days"],
                "s1_source":        chips["s1_source"],
            },
            "class_fractions":     ordered,
            "dominant_class":      dominant,
            "dominant_class_display": dominant,
            "dominant_pct":        ordered.get(dominant, 0.0),
            "imperviousness_pct":  ordered.get("developed", 0.0),
            "green_space_pct":     round(ordered.get("forest", 0.0)
                                         + ordered.get("herbaceous", 0.0), 2),
            "water_pct":           ordered.get("water", 0.0),
            "n_classes_observed":  len(ordered),
            "chip_shape":          [5, CHIP_PX, CHIP_PX],
            "polygons_geojson":    polygons,
            "elapsed_s":           round(time.time() - t0, 2),
        }
    except Exception as e:
        log.exception("terramind_nyc: fetch failed")
        return {"ok": False, "err": f"{type(e).__name__}: {e}",
                "elapsed_s": round(time.time() - t0, 2)}
