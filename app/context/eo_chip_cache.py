"""Per-query EO chip cache — Sentinel-2 L2A, Sentinel-1 RTC, DEM.

Fetches a co-registered (S2L2A, S1RTC, DEM) chip centered on (lat, lon)
and returns a dict of torch tensors ready for TerraMind-NYC inference.
The TerraMind base was trained with `temporal_n_timestamps=4`, so this
helper expands a single S2/S1 acquisition to T=4 by repetition along
the temporal axis. Single-timestep nowcasting trades some training-
distribution match for a much simpler runtime — the published LoRA
adapters still produce sensible argmax masks at T=1 / tiled.

Failure semantics mirror prithvi_live: every dependency or network
failure is converted to a clean `{ok: False, skipped: <reason>}`
result, never a raised exception. Callers (FSM specialists) that
chain off the chip can short-circuit on `ok=False` and skip the
specialist instead of surfacing a noisy error.
"""
from __future__ import annotations

import concurrent.futures
import logging
import os
import threading
import time
from typing import Any

log = logging.getLogger("riprap.eo_chip_cache")

ENABLE = os.environ.get("RIPRAP_EO_CHIP_ENABLE", "1").lower() in ("1", "true", "yes")
SEARCH_DAYS = int(os.environ.get("RIPRAP_EO_CHIP_SEARCH_DAYS", "120"))
MAX_CLOUD_PCT = float(os.environ.get("RIPRAP_EO_CHIP_MAX_CLOUD", "30"))
CHIP_PX = int(os.environ.get("RIPRAP_EO_CHIP_PX", "224"))
PIXEL_M = 10
N_TIMESTEPS = 4

# 12-band S2 L2A in TerraMind's expected order.
S2_BANDS = ["B01", "B02", "B03", "B04", "B05", "B06", "B07",
            "B08", "B8A", "B09", "B11", "B12"]

# Sentinel-1 RTC on Planetary Computer publishes vv/vh polarisations.
S1_BANDS = ["vv", "vh"]


def _has_required_deps() -> tuple[bool, str | None]:
    missing: list[str] = []
    for name in ("planetary_computer", "pystac_client",
                 "rioxarray", "xarray", "torch", "numpy"):
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if missing:
        return False, ", ".join(missing)
    return True, None


_DEPS_OK, _DEPS_MISSING = _has_required_deps()
_FETCH_LOCK = threading.Lock()


def _search_s2(lat: float, lon: float):
    """Return (item, cloud_cover) for the most recent low-cloud S2L2A
    acquisition near (lat, lon), or (None, None) if no scene exists."""
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
    if not items:
        return None, None
    item = items[0]
    cc = float(item.properties.get("eo:cloud_cover", -1))
    return item, cc


def _search_s1(item_dt, lat: float, lon: float):
    """Return the closest Sentinel-1 RTC acquisition to the given S2
    datetime, or None if Planetary Computer has nothing nearby."""
    import datetime as dt

    import planetary_computer as pc
    from pystac_client import Client
    win = dt.timedelta(days=10)
    start = item_dt - win
    end = item_dt + win
    client = Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=pc.sign_inplace,
    )
    delta = 0.02
    search = client.search(
        collections=["sentinel-1-rtc"],
        bbox=[lon - delta, lat - delta, lon + delta, lat + delta],
        datetime=f"{start.isoformat()}/{end.isoformat()}",
        max_items=10,
    )
    items = list(search.items())
    if not items:
        return None
    items.sort(key=lambda it:
               abs((it.datetime - item_dt).total_seconds())
               if it.datetime else 1e18)
    return items[0]


def _read_band(href, bbox_xy_meters, epsg):
    """Read a single COG band, clipped to the bbox, and resample to
    CHIP_PX × CHIP_PX. Returns a numpy array (CHIP_PX, CHIP_PX) float32.
    """
    import numpy as np
    import rioxarray  # noqa: F401
    da = rioxarray.open_rasterio(href, masked=False).squeeze(drop=True)
    da = da.rio.clip_box(minx=bbox_xy_meters[0], miny=bbox_xy_meters[1],
                          maxx=bbox_xy_meters[2], maxy=bbox_xy_meters[3])
    if da.shape[-2] != CHIP_PX or da.shape[-1] != CHIP_PX:
        # Resample (nearest is fine for the 10/20/60 m S2 mix; S1 is 10 m,
        # DEM is 30 m and benefits from bilinear; we keep nearest for
        # simplicity — the TerraMind LoRA was trained against terratorch's
        # default resampler which is also nearest).
        da = da.rio.reproject(
            f"EPSG:{epsg}", shape=(CHIP_PX, CHIP_PX), resampling=0
        )
    arr = da.values.astype("float32")
    return np.nan_to_num(arr)


def _fetch_modalities(lat: float, lon: float, timeout_s: float = 60.0) -> dict[str, Any]:
    """Fetch S2L2A + S1RTC + DEM as numpy arrays, resampled to a common
    CHIP_PX × CHIP_PX grid centered on (lat, lon).
    """
    import numpy as np
    from pyproj import Transformer

    t0 = time.time()
    item, cc = _search_s2(lat, lon)
    if item is None:
        return {"ok": False,
                "skipped": f"no <{MAX_CLOUD_PCT}% cloud S2 in last "
                           f"{SEARCH_DAYS}d"}
    if "proj:epsg" in item.properties:
        epsg = int(item.properties["proj:epsg"])
    else:
        code = item.properties.get("proj:code", "")
        if not code.startswith("EPSG:"):
            return {"ok": False,
                    "skipped": "STAC item missing proj:epsg / proj:code"}
        epsg = int(code.split(":", 1)[1])

    fwd = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    cx, cy = fwd.transform(lon, lat)
    half_m = CHIP_PX / 2 * PIXEL_M
    bbox = (cx - half_m, cy - half_m, cx + half_m, cy + half_m)

    if time.time() - t0 > timeout_s:
        return {"ok": False, "skipped": "STAC search exceeded budget"}

    # ---- S2L2A: 12 bands ------------------------------------------------
    s2_arrs = []
    try:
        for b in S2_BANDS:
            href = item.assets[b].href
            s2_arrs.append(_read_band(href, bbox, epsg))
    except Exception as e:
        log.warning("eo_chip: S2 band fetch failed (%s); aborting", e)
        return {"ok": False, "err": f"S2 fetch failed: {type(e).__name__}: {e}"}
    s2 = np.stack(s2_arrs)  # (12, H, W)
    if s2.mean() > 1.0:
        s2 = s2 / 10000.0  # scale L2A reflectance from int16 to ~[0, 1]

    # ---- S1RTC: 2 polarisations (best effort) ---------------------------
    s1: np.ndarray | None = None
    s1_meta: dict[str, Any] = {}
    if time.time() - t0 < timeout_s:
        try:
            s1_item = _search_s1(item.datetime, lat, lon)
            if s1_item is not None:
                s1_arrs = []
                for b in S1_BANDS:
                    href = s1_item.assets[b].href
                    s1_arrs.append(_read_band(href, bbox, epsg))
                s1 = np.stack(s1_arrs)
                s1_meta = {
                    "scene_id": s1_item.id,
                    "datetime": (s1_item.datetime.isoformat()
                                 if s1_item.datetime else None),
                }
        except Exception as e:
            log.warning("eo_chip: S1 fetch best-effort failed: %s", e)

    # ---- DEM: Copernicus 30 m via planetary_computer (best effort) ------
    dem: np.ndarray | None = None
    if time.time() - t0 < timeout_s:
        try:
            import planetary_computer as pc
            from pystac_client import Client
            client = Client.open(
                "https://planetarycomputer.microsoft.com/api/stac/v1",
                modifier=pc.sign_inplace,
            )
            dem_search = client.search(
                collections=["cop-dem-glo-30"],
                bbox=[lon - 0.02, lat - 0.02, lon + 0.02, lat + 0.02],
                max_items=1,
            )
            dem_items = list(dem_search.items())
            if dem_items:
                href = dem_items[0].assets["data"].href
                dem = _read_band(href, bbox, epsg)
                dem = dem[None, :, :]  # add channel dim
        except Exception as e:
            log.warning("eo_chip: DEM fetch best-effort failed: %s", e)

    return {
        "ok": True,
        "lat": lat, "lon": lon,
        "epsg": epsg, "chip_px": CHIP_PX, "pixel_m": PIXEL_M,
        "s2": s2, "s1": s1, "dem": dem,
        "s2_meta": {
            "scene_id": item.id,
            "datetime": (item.datetime.isoformat() if item.datetime else None),
            "cloud_cover": cc,
        },
        "s1_meta": s1_meta,
        "elapsed_s": round(time.time() - t0, 2),
    }


def _to_terramind_tensors(modalities: dict[str, Any]) -> dict[str, Any]:
    """Shape numpy modality arrays into the (B, C, T, H, W) tensors
    TerraMind expects with `temporal_n_timestamps=4`. Single-timestep
    fetches get tiled to T=4 — same observation in every slot.
    """
    import torch
    s2 = modalities["s2"]  # (12, H, W)
    s2_t = torch.from_numpy(s2).float().unsqueeze(1)  # (12, 1, H, W)
    s2_t = s2_t.repeat(1, N_TIMESTEPS, 1, 1).unsqueeze(0)  # (1, 12, T, H, W)
    chips = {"S2L2A": s2_t}
    if modalities.get("s1") is not None:
        s1 = modalities["s1"]  # (2, H, W)
        s1_t = torch.from_numpy(s1).float().unsqueeze(1)
        s1_t = s1_t.repeat(1, N_TIMESTEPS, 1, 1).unsqueeze(0)
        chips["S1RTC"] = s1_t
    if modalities.get("dem") is not None:
        dem = modalities["dem"]  # (1, H, W)
        dem_t = torch.from_numpy(dem).float().unsqueeze(1)
        dem_t = dem_t.repeat(1, N_TIMESTEPS, 1, 1).unsqueeze(0)
        chips["DEM"] = dem_t
    return chips


def _fetch_and_build(lat: float, lon: float, timeout_s: float) -> dict[str, Any]:
    """Inner fetch + tensor build, run inside a bounded thread."""
    with _FETCH_LOCK:
        try:
            modalities = _fetch_modalities(lat, lon, timeout_s=timeout_s)
        except Exception as e:
            log.exception("eo_chip: fetch failed")
            return {"ok": False, "err": f"{type(e).__name__}: {e}"}
        if not modalities.get("ok"):
            return modalities
        try:
            modalities["tensors"] = _to_terramind_tensors(modalities)
        except Exception as e:
            log.exception("eo_chip: tensor build failed")
            return {"ok": False,
                    "err": f"tensor build failed: {type(e).__name__}: {e}"}
        # Compute the chip's WGS84 bbox so downstream TerraMind specialists
        # can polygonise their predictions onto the map. The chip is
        # CHIP_PX × CHIP_PX at PIXEL_M (10 m) in the scene's UTM zone;
        # reproject the four corners to EPSG:4326 and use the
        # axis-aligned envelope.
        try:
            from pyproj import Transformer
            half_m = (CHIP_PX * PIXEL_M) / 2.0
            t_to_utm = Transformer.from_crs(
                "EPSG:4326", f"EPSG:{modalities['epsg']}", always_xy=True)
            t_to_4326 = Transformer.from_crs(
                f"EPSG:{modalities['epsg']}", "EPSG:4326", always_xy=True)
            cx, cy = t_to_utm.transform(lon, lat)
            corners_utm = [
                (cx - half_m, cy - half_m),
                (cx - half_m, cy + half_m),
                (cx + half_m, cy - half_m),
                (cx + half_m, cy + half_m),
            ]
            corners_ll = [t_to_4326.transform(x, y) for x, y in corners_utm]
            lons = [c[0] for c in corners_ll]
            lats = [c[1] for c in corners_ll]
            modalities["bounds_4326"] = (
                min(lons), min(lats), max(lons), max(lats))
        except Exception:
            log.exception("eo_chip: bounds_4326 reprojection failed")
        return modalities


def fetch(lat: float, lon: float, timeout_s: float = 60.0) -> dict[str, Any]:
    """Run the chip pipeline. Always returns a dict with at minimum
    `{ok, skipped|err, ...}`; on success the dict carries the
    co-registered numpy arrays plus `tensors` (the TerraMind-shaped
    torch dict).

    Runs in a daemon thread so that STAC searches and COG band downloads
    (which use requests/rioxarray without per-call timeouts) are bounded
    by a hard wall-clock deadline even when the network hangs.
    """
    if not ENABLE:
        return {"ok": False, "skipped": "RIPRAP_EO_CHIP_ENABLE=0"}
    if not _DEPS_OK:
        return {"ok": False,
                "skipped": f"deps unavailable on this deployment: "
                           f"{_DEPS_MISSING}"}
    # Hard wall-clock cap: pystac_client / rioxarray COG reads don't expose
    # uniform per-request timeouts, so we bound the whole pipeline here.
    hard_timeout = timeout_s + 15.0
    # Propagate the parent thread's emissions tracker into the worker so
    # any inference._post calls made inside _fetch_and_build are recorded.
    from app import emissions as _emissions
    _parent_tracker = _emissions.current()
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=1,
        initializer=lambda t=_parent_tracker: _emissions.install(t),
    ) as pool:
        future = pool.submit(_fetch_and_build, lat, lon, timeout_s)
        try:
            return future.result(timeout=hard_timeout)
        except concurrent.futures.TimeoutError:
            log.warning("eo_chip: hard timeout after %.0fs (STAC/COG hung)", hard_timeout)
            return {"ok": False, "skipped": f"eo_chip timed out after {hard_timeout:.0f}s"}
