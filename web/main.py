"""HeliOS-NYC web UI — FastAPI + SSE streaming of the Burr FSM trace.

Run: uvicorn web.main:app --reload --port 8000
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.context import floodnet  # noqa: E402
from app.flood_layers import dep_stormwater, sandy_inundation  # noqa: E402
from app.fsm import iter_steps  # noqa: E402

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

app = FastAPI(title="Riprap")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

import json as _json  # noqa: E402

import geopandas as _gpd  # noqa: E402
from fastapi.responses import JSONResponse, Response  # noqa: E402

_LAYER_CACHE: dict = {}


def _clip_simplify(gdf, lat: float, lon: float, radius_m: float = 1500,
                   simplify_ft: float = 8, props_keep=None):
    """Clip a NYC-wide layer to a small bbox around a point and simplify.

    Uses shapely's clip_by_rect (much faster than gpd.overlay on dense
    polygons) and a pre-bbox-filter via .cx so we never touch geometries
    outside the AOI.
    """
    import shapely.geometry as sg

    pt = _gpd.GeoSeries([sg.Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:2263")[0]
    half = radius_m * 3.281
    minx, miny, maxx, maxy = pt.x - half, pt.y - half, pt.x + half, pt.y + half

    sub = gdf.cx[minx:maxx, miny:maxy]
    if sub.empty:
        return {"type": "FeatureCollection", "features": []}

    clipped = sub.copy()
    clipped["geometry"] = sub.geometry.clip_by_rect(minx, miny, maxx, maxy)
    clipped = clipped[~clipped.geometry.is_empty & clipped.geometry.notna()]
    if clipped.empty:
        return {"type": "FeatureCollection", "features": []}

    clipped["geometry"] = clipped.geometry.simplify(simplify_ft, preserve_topology=True)
    g = clipped.to_crs("EPSG:4326")
    if props_keep is not None:
        g = g[[c for c in g.columns if c in props_keep or c == "geometry"]]
    else:
        g = g[["geometry"]]
    return _json.loads(g.to_json())


@app.on_event("startup")
def _warm_caches():
    """Prime slow loads so the first user query doesn't pay the cold-cost penalty."""
    print("[startup] warming flood layers...", flush=True)
    sandy_inundation.load()
    for scen in ["dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current"]:
        dep_stormwater.load(scen)
    print("[startup] flood layers ready", flush=True)
    print("[startup] warming RAG (Granite Embedding 278M + 5 PDFs)...", flush=True)
    from app import rag
    rag.warm()
    print("[startup] RAG ready", flush=True)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/compare")
def compare_page():
    return FileResponse(STATIC / "compare.html")


@app.get("/register/{asset_class}")
def register_page(asset_class: str):
    if asset_class not in ("schools", "nycha", "mta_entrances"):
        return JSONResponse({"error": f"unknown asset class {asset_class!r}"}, status_code=404)
    return FileResponse(STATIC / "register.html")


@app.get("/api/register/{asset_class}")
def api_register(asset_class: str):
    """Return a pre-computed asset-class register."""
    if asset_class not in ("schools", "nycha", "mta_entrances"):
        return JSONResponse({"error": f"unknown asset class {asset_class!r}"},
                            status_code=404)
    f = ROOT.parent / "data" / "registers" / f"{asset_class}.json"
    if not f.exists():
        script = f"scripts/build_{asset_class}_register.py"
        return JSONResponse(
            {"error": f"register not built — run python {script}",
             "rows": []},
            status_code=503,
        )
    return JSONResponse(_json.loads(f.read_text()),
                        headers={"Cache-Control": "public, max-age=300"})


@app.get("/api/compare")
async def compare_stream(a: str, b: str, request: Request):
    """Two parallel FSM runs, results returned as a single SSE stream.
    Each event is tagged with side="a" or side="b" so the client can
    route updates to the correct panel."""
    import asyncio
    import queue
    from app.fsm import iter_steps

    def gen_for_side(side: str, q_text: str, out_q):
        try:
            for ev in iter_steps(q_text):
                ev["side"] = side
                out_q.put(ev)
        except Exception as e:
            out_q.put({"side": side, "kind": "error", "err": str(e)})
        out_q.put({"side": side, "kind": "_done"})

    out_q: "queue.Queue[dict]" = queue.Queue()

    def kick():
        # run both sides in parallel threads — each Burr Application owns
        # its own state so this is safe, and Ollama with NUM_PARALLEL=2
        # serves both reconcile calls concurrently.
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, gen_for_side, "a", a, out_q)
        loop.run_in_executor(None, gen_for_side, "b", b, out_q)

    async def event_stream():
        kick()
        yield f"event: hello\ndata: {json.dumps({'a': a, 'b': b})}\n\n"
        done = 0
        while done < 2:
            try:
                ev = await asyncio.to_thread(out_q.get, True, 1.0)
            except Exception:
                continue
            if ev.get("kind") == "_done":
                done += 1
                continue
            if ev.get("kind") == "step":
                yield f"event: step\ndata: {json.dumps(ev, default=str)}\n\n"
            elif ev.get("kind") == "final":
                yield f"event: final\ndata: {json.dumps(ev, default=str)}\n\n"
            elif ev.get("kind") == "error":
                yield f"event: error\ndata: {json.dumps(ev)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/stream")
async def stream(q: str, request: Request):
    """Server-sent-events stream: each FSM action yields one event."""
    def gen():
        try:
            yield f"event: hello\ndata: {json.dumps({'query': q})}\n\n"
            for ev in iter_steps(q):
                if ev["kind"] == "step":
                    yield f"event: step\ndata: {json.dumps(ev, default=str)}\n\n"
                else:
                    yield f"event: final\ndata: {json.dumps(ev, default=str)}\n\n"
            yield "event: done\ndata: {}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'err': str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/layers/sandy")
def layer_sandy(lat: float, lon: float, r: float = 1500):
    key = ("sandy", round(lat, 4), round(lon, 4), int(r))
    if key not in _LAYER_CACHE:
        _LAYER_CACHE[key] = _clip_simplify(sandy_inundation.load(), lat, lon, r)
    return JSONResponse(_LAYER_CACHE[key],
                        headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/layers/dep_extreme_2080")
def layer_dep_2080(lat: float, lon: float, r: float = 1500):
    key = ("dep2080", round(lat, 4), round(lon, 4), int(r))
    if key not in _LAYER_CACHE:
        _LAYER_CACHE[key] = _clip_simplify(
            dep_stormwater.load("dep_extreme_2080"),
            lat, lon, r, props_keep={"Flooding_Category"})
    return JSONResponse(_LAYER_CACHE[key],
                        headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/layers/prithvi_water")
def layer_prithvi_water(lat: float, lon: float, r: float = 1500):
    """Prithvi-EO 2.0 (Sen1Floods11) satellite water mask, clipped to a
    bbox around the address for performance."""
    key = ("prithvi", round(lat, 4), round(lon, 4), int(r))
    if key not in _LAYER_CACHE:
        from app.flood_layers import prithvi_water as pw
        gdf, _meta = pw._load()
        if gdf is None:
            return JSONResponse({"type": "FeatureCollection", "features": []})
        _LAYER_CACHE[key] = _clip_simplify(gdf, lat, lon, r,
                                            props_keep=set(),
                                            simplify_ft=4)
    return JSONResponse(_LAYER_CACHE[key],
                        headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/floodnet_near")
def floodnet_near(lat: float, lon: float, r: float = 1000):
    sensors = floodnet.sensors_near(lat, lon, r)
    ids = [s.deployment_id for s in sensors]
    events = floodnet.flood_events_for(ids)
    by_dep: dict = {}
    for e in events:
        by_dep.setdefault(e.deployment_id, []).append(e)

    features = []
    for s in sensors:
        if s.lat is None or s.lon is None:
            continue
        evs = by_dep.get(s.deployment_id, [])
        peak = max((e.max_depth_mm or 0 for e in evs), default=0)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [s.lon, s.lat]},
            "properties": {
                "deployment_id": s.deployment_id,
                "name": s.name,
                "street": s.street,
                "borough": s.borough,
                "n_events_3y": len(evs),
                "peak_depth_mm": peak,
            },
        })
    return JSONResponse({"type": "FeatureCollection", "features": features})
