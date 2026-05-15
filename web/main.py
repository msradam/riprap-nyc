"""Riprap web UI — FastAPI + SSE streaming of the Burr FSM trace.

Run: uvicorn web.main:app --reload --port 8000
"""
from __future__ import annotations

import json
import os
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app import emissions  # noqa: E402
from app.context import floodnet  # noqa: E402
from app.flood_layers import dep_stormwater, sandy_inundation  # noqa: E402
from app.fsm import iter_steps  # noqa: E402
from app.stones import DATA_STONES  # noqa: E402
from app.stones import capstone as _capstone_stone  # noqa: E402

# Map FSM step name -> Stone for the SSE stone_start / stone_done envelope.
# Steps not in this map (geocode, rag_granite_embedding, gliner_extract,
# nta_resolve and friends) don't open a Stone boundary — they're
# orientation / policy infrastructure shared across Stones.
_STEP_TO_STONE: dict[str, str] = {
    # Cornerstone — single_address + polygon-aggregated (neighborhood)
    "sandy_inundation":           "Cornerstone",
    "dep_stormwater":             "Cornerstone",
    "ida_hwm_2021":               "Cornerstone",
    "prithvi_eo_v2":              "Cornerstone",
    "microtopo_lidar":            "Cornerstone",
    "sandy_nta":                  "Cornerstone",
    "dep_extreme_2080_nta":       "Cornerstone",
    "dep_moderate_2050_nta":      "Cornerstone",
    "dep_moderate_current_nta":   "Cornerstone",
    "microtopo_nta":              "Cornerstone",
    # Keystone (the chip fetch is infrastructure for the LoRA pair, but
    # it's logically Keystone-adjacent and we surface it under that
    # banner so the trace doesn't show a phantom orphan step).
    "mta_entrance_exposure":      "Keystone",
    "nycha_development_exposure": "Keystone",
    "doe_school_exposure":        "Keystone",
    "doh_hospital_exposure":      "Keystone",
    "terramind_synthesis":        "Keystone",
    "eo_chip_fetch":              "Keystone",
    "terramind_buildings":        "Keystone",
    # Touchstone
    "floodnet":                   "Touchstone",
    "nyc311":                     "Touchstone",
    "nws_obs":                    "Touchstone",
    "noaa_tides":                 "Touchstone",
    "prithvi_eo_live":            "Touchstone",
    "terramind_lulc":             "Touchstone",
    "nyc311_nta":                 "Touchstone",
    # Lodestone
    "nws_alerts":                 "Lodestone",
    "ttm_forecast":               "Lodestone",
    "ttm_311_forecast":           "Lodestone",
    "floodnet_forecast":          "Lodestone",
    "ttm_battery_surge":          "Lodestone",
    # Capstone — the reconciler step's name varies between strict and
    # legacy paths; both map to Capstone.
    "reconcile_granite41":        "Capstone",
    "mellea_reconcile_address":   "Capstone",
    "reconcile_neighborhood":     "Capstone",
    "reconcile_development":      "Capstone",
    "reconcile_live_now":         "Capstone",
}

# Pretty-printed Stone metadata the frontend renders as parent-row labels.
_STONE_META: dict[str, dict] = {
    s.NAME: {"name": s.NAME, "tagline": s.TAGLINE,
             "description": s.DESCRIPTION}
    for s in DATA_STONES
}
_STONE_META[_capstone_stone.NAME] = {
    "name": _capstone_stone.NAME,
    "tagline": _capstone_stone.TAGLINE,
    "description": _capstone_stone.DESCRIPTION,
}

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
SVELTEKIT_BUILD = ROOT / "sveltekit" / "build"

app = FastAPI(title="Riprap")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# SvelteKit static build (adapter-static). Serves the new design-system UI
# from /, /q/sample, /q/<query>. The legacy custom-element pages remain at
# /legacy, /single, /compare, /register/* for as long as they're useful.
if SVELTEKIT_BUILD.exists():
    app.mount("/_app", StaticFiles(directory=SVELTEKIT_BUILD / "_app"), name="sveltekit_assets")

# Top-level static assets the SvelteKit build emits next to the HTML
# entry points (favicon.svg / favicon.png / robots.txt). These would
# fall through to the SPA fallback and 404 without explicit routes;
# adapter-static expects them under /, not /_app.
def _serve_build_asset(name: str):
    p = SVELTEKIT_BUILD / name
    if not p.exists():
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return FileResponse(p, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/favicon.svg", include_in_schema=False)
def _favicon_svg():
    return _serve_build_asset("favicon.svg")


@app.get("/favicon.png", include_in_schema=False)
def _favicon_png():
    return _serve_build_asset("favicon.png")


@app.get("/favicon.ico", include_in_schema=False)
def _favicon_ico():
    # No .ico in the build, but browsers still probe for it. Redirect-
    # by-content to the PNG so the tab gets the dam mark either way.
    return _serve_build_asset("favicon.png")


@app.get("/robots.txt", include_in_schema=False)
def _robots():
    return _serve_build_asset("robots.txt")

import json as _json  # noqa: E402

import geopandas as _gpd  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

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
    if os.environ.get("RIPRAP_NYCHA_REGISTERS", "0").lower() in ("1", "true", "yes"):
        print("[startup] pre-loading register catalogs...", flush=True)
        try:
            # NYCHA + DOE schools read from pre-built JSON catalogs at
            # data/registers/{nycha,schools}.json — sub-ms per query.
            from app.registers._loader import load_register
            n_nycha = len(load_register("nycha"))
            n_schools = len(load_register("schools"))
            print(f"[startup] catalogs ready: nycha={n_nycha} rows, "
                  f"schools={n_schools} rows", flush=True)
            # DOH hospitals has no pre-built catalog (~150 entries; we
            # read the GeoJSON directly and sample baked rasters per hit).
            from app.registers import doh_hospitals as _r_hospitals
            _r_hospitals._load_hospitals()
            print("[startup] hospitals geojson loaded", flush=True)
        except Exception as _e:
            print(f"[startup] register warm failed (non-fatal): {_e}", flush=True)
    print("[startup] warming RAG (Granite Embedding 278M + 5 PDFs)...", flush=True)
    # RAG warm loads sentence-transformers, which on some HF Space rebuilds
    # has hit transformers-lazy-import edge cases (CodeCarbonCallback). The
    # Space *must* start even if RAG fails — the FSM still works without
    # RAG citations (specialists deliver their own grounded data, and the
    # rag step in fsm.py already handles `rag=[]` gracefully). Surface the
    # failure loudly in logs but don't kill the app.
    try:
        from app import rag
        rag.warm()
        print("[startup] RAG ready", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[startup] RAG warm FAILED — continuing without RAG: "
              f"{type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
    # Pre-import the heavy EO/ML stacks on the main thread so the
    # parallel-fanout workers don't race each other on first
    # import (sklearn's "partially initialized module" surfaces as a
    # spurious ImportError when terratorch / tsfm_public both pull
    # sklearn concurrently from worker threads).
    # Warm the Ollama LLM models so the first user query doesn't pay a
    # cold-load penalty (~70 s for the 3B planner, ~12 s for the 8B
    # reconciler at Q4_K_M). Sets keep_alive to 24 h so they stay
    # resident across queries. Both calls use num_ctx that matches the
    # production call sites (Mellea's 4096), so Ollama's KV cache is
    # pre-allocated at the right size and the first reconcile doesn't
    # pay an extra grow-and-reinit cost.
    if os.environ.get("RIPRAP_SKIP_LLM_WARM", "").lower() not in ("1", "true", "yes"):
        print("[startup] warming Ollama models (granite4.1:3b + 8b)...",
              flush=True)
        try:
            import httpx as _httpx
            base = os.environ.get(
                "OLLAMA_BASE_URL",
                os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            )
            if not base.startswith("http"):
                base = "http://" + base
            keep_alive = os.environ.get("OLLAMA_KEEP_ALIVE", "24h")
            num_ctx = int(os.environ.get("RIPRAP_MELLEA_NUM_CTX", "4096"))
            for tag in (os.environ.get("RIPRAP_OLLAMA_3B_TAG", "granite4.1:3b"),
                        os.environ.get("RIPRAP_OLLAMA_8B_TAG", "granite4.1:8b")):
                try:
                    r = _httpx.post(
                        base.rstrip("/") + "/api/generate",
                        json={
                            "model": tag,
                            "prompt": "hi",
                            "stream": False,
                            "keep_alive": keep_alive,
                            "options": {"num_ctx": num_ctx, "num_predict": 1},
                        },
                        timeout=180,
                    )
                    if r.status_code == 200:
                        load_s = r.json().get("load_duration", 0) / 1e9
                        print(f"[startup]   {tag} loaded "
                              f"(load_duration={load_s:.1f}s, "
                              f"keep_alive={keep_alive}, num_ctx={num_ctx})",
                              flush=True)
                    else:
                        print(f"[startup]   {tag} warm failed "
                              f"({r.status_code})", flush=True)
                except Exception as warm_err:
                    print(f"[startup]   {tag} warm failed: {warm_err}",
                          flush=True)
        except Exception as e:
            print(f"[startup] LLM warm skipped: {e}", flush=True)
    print("[startup] pre-importing terratorch + tsfm_public + transformers...", flush=True)
    try:
        import sklearn  # noqa: F401  prime sklearn first
        import terratorch  # noqa: F401
        import tsfm_public  # noqa: F401

        # Transformers does lazy-loading via __getattr__; touching
        # PreTrainedModel forces the lazy-init to complete on the main
        # thread. Otherwise FSM worker threads race the lazy loader and
        # surface ModuleNotFoundError("Could not import module
        # 'PreTrainedModel'") under load.
        from transformers import PreTrainedModel  # noqa: F401

        # tsfm_public's TinyTimeMixerForPrediction import path triggers
        # the granite-tsfm side of the lazy chain — pre-warm here too.
        from tsfm_public import TinyTimeMixerForPrediction  # noqa: F401
        from tsfm_public.toolkit.get_model import get_model  # noqa: F401
    except Exception as e:
        print(f"[startup] heavy-EO pre-import skipped: {e}", flush=True)
    # Force-import every specialist module that does heavy ML at runtime
    # so its module-level deps probe + lazy transformers chain runs on
    # the main thread, deterministic order, before any FSM worker fans
    # out. Modules whose deps genuinely aren't installed will set their
    # own `_DEPS_OK = False` here and gracefully no-op at request time;
    # what we're avoiding is the "_DEPS_OK = False because of an import
    # race" failure mode that fired on the live PS-188 query.
    for mod_path in (
        "app.live.ttm_forecast",
        "app.live.ttm_battery_surge",
        "app.live.floodnet_forecast",
        "app.context.gliner_extract",
        "app.context.terramind_nyc",
        "app.context.eo_chip_cache",
        "app.flood_layers.prithvi_live",
    ):
        try:
            __import__(mod_path)
        except Exception as e:
            print(f"[startup] {mod_path} pre-import skipped: "
                  f"{type(e).__name__}: {e}", flush=True)
    # Warm the TerraMind specialist so first per-query call is just
    # the diffusion (~3 s), not model load (~30 s). No-ops if deps
    # are missing on this deployment.
    try:
        from app.context import terramind_synthesis
        terramind_synthesis.warm()
        print("[startup] TerraMind ready", flush=True)
    except Exception as e:
        print(f"[startup] TerraMind warm skipped: {e}", flush=True)


@app.get("/api/debug/eo")
def api_debug_eo():
    """Diagnostic for the EO toolchain (Phase 1 + Phase 4) on HF Spaces.

    Surfaces sys.path, PYTHONPATH, and per-module import status so we
    can tell whether terratorch is actually findable from inside the
    uvicorn process. Used to debug why the runtime --target install
    appears to succeed in the entrypoint but isn't visible to the
    FSM specialists at request time.
    """
    import os
    import sys
    import traceback
    from pathlib import Path

    out = {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "PYTHONPATH": os.environ.get("PYTHONPATH"),
        "PYTHONNOUSERSITE": os.environ.get("PYTHONNOUSERSITE"),
        "HOME": os.environ.get("HOME"),
        "sys.path": sys.path,
    }
    eo_dir = Path(os.environ.get("HOME", "/home/user")) / ".eo-pkgs"
    out["eo_dir"] = str(eo_dir)
    out["eo_dir_exists"] = eo_dir.exists()
    if eo_dir.exists():
        out["eo_dir_contents"] = sorted(p.name for p in eo_dir.iterdir())[:50]
    out["modules"] = {}
    for name in ("terratorch", "einops", "diffusers", "timm",
                 "rasterio", "planetary_computer", "pystac_client"):
        try:
            mod = __import__(name)
            out["modules"][name] = {"ok": True,
                                     "file": getattr(mod, "__file__", "?")}
        except Exception as e:
            out["modules"][name] = {"ok": False,
                                     "err": f"{type(e).__name__}: {e}",
                                     "tb": traceback.format_exc().splitlines()[-3:]}
    return JSONResponse(out)


@app.get("/api/backend")
async def api_backend():
    """Live LLM-backend descriptor for the UI's hardware badge.

    Returns the configured primary (vLLM/AMD or Ollama/local), plus a
    quick reachability ping so the badge can show whether the primary is
    actually answering or whether the Router is on the fallback path.
    """
    import httpx

    from app import llm
    info = llm.backend_info()
    reachable = None
    try:
        if info["primary"] in ("vllm", "mlx") and info["vllm_base_url"]:
            url = info["vllm_base_url"].rstrip("/") + "/models"
            async with httpx.AsyncClient(timeout=2.5) as client:
                r = await client.get(url, headers={"Authorization": "Bearer ping"})
            # vLLM and mlx_lm.server both return 200 on /v1/models when
            # reachable; vLLM may return 401 with --api-key set. Either
            # proves the server is up. Anything else = unreachable.
            reachable = r.status_code in (200, 401)
        else:
            url = info["ollama_base_url"].rstrip("/") + "/api/tags"
            async with httpx.AsyncClient(timeout=2.5) as client:
                r = await client.get(url)
            reachable = r.status_code == 200
    except Exception:
        reachable = False
    info["reachable"] = reachable
    info["effective_engine"] = (
        info["engine"] if reachable
        else (info.get("fallback_engine") or "offline")
    )
    return JSONResponse(info)


@app.get("/")
def index():
    """SvelteKit landing page (the new design-system UI)."""
    sk = SVELTEKIT_BUILD / "index.html"
    if sk.exists():
        return FileResponse(sk)
    return JSONResponse(
        {"error": "sveltekit build not present — run `cd web/sveltekit && npm run build`"},
        status_code=503,
    )


@app.get("/q/sample")
def q_sample_page():
    """The prerendered Red Hook demo briefing (no SSE)."""
    sk = SVELTEKIT_BUILD / "q" / "sample.html"
    if sk.exists():
        return FileResponse(sk)
    return JSONResponse({"error": "sveltekit build not present"}, status_code=503)


@app.get("/q/{query_id}")
def q_query_page(query_id: str):  # noqa: ARG001 — captured for the SPA router
    """Live briefing route. Served by the SvelteKit SPA fallback (200.html);
    the client opens an EventSource to /api/agent/stream."""
    sk = SVELTEKIT_BUILD / "200.html"
    if sk.exists():
        return FileResponse(sk)
    return JSONResponse({"error": "sveltekit build not present"}, status_code=503)


@app.get("/print/{query_id}")
def print_page(query_id: str):  # noqa: ARG001 — captured by the SPA router
    """Curated print artifact for a completed briefing. The client
    hydrates from localStorage (key riprap:print:<query_id>) and
    auto-fires window.print() — no backend round-trip."""
    sk = SVELTEKIT_BUILD / "200.html"
    if sk.exists():
        return FileResponse(sk)
    return JSONResponse({"error": "sveltekit build not present"}, status_code=503)


# Legacy custom-element bundle routes (/legacy, /single, /compare, /agent,
# /report, /register/*) were retired in v0.4.5 — the SvelteKit UI fully
# subsumes them. Static assets at /static/* still mount in case anything
# external embeds them, but the page-level routes are gone. Hitting them
# now returns the framework default 404.


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

    out_q: queue.Queue[dict] = queue.Queue()

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


def _run_compare(p, raw_query: str, out_q, i_addr) -> dict:
    """Run the compare intent: execute the full single_address specialist
    suite sequentially for each target, then merge the two paragraphs into
    one Markdown document clearly labelled PLACE A and PLACE B.

    Sequential execution is required because the FSM uses thread-local hooks
    (set_strict_mode, set_token_callback) — concurrent runs on the same
    thread would corrupt the hooks. See app/intents/single_address.py.

    Step events from each target are forwarded to out_q tagged with a
    `target_label` key so the trace UI can optionally group them, but the
    existing trace UI ignores unknown keys gracefully."""
    from app.intents import neighborhood as i_nbhd
    from app.planner import Plan

    addr_targets = [t for t in p.targets if t.get("type") in ("address", "nta")]
    if len(addr_targets) < 2:
        # Fallback: only one (or zero) address extracted — run as single_address
        return i_addr.run(p, raw_query, progress_q=out_q, strict=True)

    results = []
    for idx, target in enumerate(addr_targets[:2]):
        label = "PLACE A" if idx == 0 else "PLACE B"
        addr_text = target["text"]

        if out_q is not None:
            # Wrap out_q to tag step events with the target label so the
            # trace UI can optionally group them; token/mellea_attempt pass
            # through untagged so the SvelteKit briefing buffer works.
            _label = label
            _q = out_q
            class _TaggedQ:
                def put(self, ev):
                    if ev.get("kind") == "step":
                        _q.put({**ev, "target_label": _label})
                    else:
                        _q.put(ev)
            effective_q = _TaggedQ()
        else:
            effective_q = None

        if target.get("type") == "nta":
            sub_plan = Plan(
                intent="neighborhood",
                targets=[{"type": "nta", "text": addr_text}],
                specialists=p.specialists,
                rationale=p.rationale,
            )
            result = i_nbhd.run(sub_plan, addr_text, progress_q=effective_q, strict=True)
        else:
            sub_plan = Plan(
                intent="single_address",
                targets=[{"type": "address", "text": addr_text}],
                specialists=p.specialists,
                rationale=p.rationale,
            )
            result = i_addr.run(sub_plan, addr_text, progress_q=effective_q, strict=True)
        results.append((label, addr_text, result))

    # Merge: produce one paragraph with both place sections.
    parts = []
    for label, addr_text, res in results:
        para = (res.get("paragraph") or "").strip()
        parts.append(f"## {label}: {addr_text}\n\n{para}")
    merged_paragraph = "\n\n---\n\n".join(parts)

    # Combine Mellea metadata: sum attempts, union passed/failed.
    def _merge_mellea(a, b):
        def _lst(m, k): return m.get(k) or []
        return {
            "rerolls": (a.get("rerolls") or 0) + (b.get("rerolls") or 0),
            "n_attempts": (a.get("n_attempts") or 0) + (b.get("n_attempts") or 0),
            "requirements_passed": list(set(_lst(a, "requirements_passed")) & set(_lst(b, "requirements_passed"))),
            "requirements_failed": list(set(_lst(a, "requirements_failed") + _lst(b, "requirements_failed"))),
            "requirements_total": max(a.get("requirements_total") or 0, b.get("requirements_total") or 0),
        }

    mellea_a = results[0][2].get("mellea") or {}
    mellea_b = results[1][2].get("mellea") or {}

    # Spread Place A's full specialist state into the return dict so
    # adaptFinalToFindings can build evidence cards (TTM, TerraMind, Prithvi,
    # Sandy, etc.) from the higher-risk location.  Place B's live-state data
    # is available via targets[].state for future per-location card rendering.
    # Without this, _run_compare returned only paragraph/mellea/intent/targets
    # and all fine-tuned model cards were silently suppressed (state keys
    # missing → card builders returned null).
    out = {**results[0][2]}
    out.update({
        "paragraph": merged_paragraph,
        "mellea": _merge_mellea(mellea_a, mellea_b),
        "intent": "compare",
        "targets": [
            {"label": lbl, "address": addr, "state": res}
            for lbl, addr, res in results
        ],
        "tier": results[0][2].get("tier"),
    })
    return out


@app.get("/api/agent")
def api_agent(q: str):
    """Agentic endpoint: take a natural-language query, plan it via
    Granite 4.1, dispatch to the appropriate intent module, return the
    full result as JSON. The Plan is included so callers can see the
    agent's routing decision.

    All non-trivial reconciliation (single_address / neighborhood /
    development_check) routes through Mellea-validated rejection
    sampling against four grounding requirements. live_now stays on
    streaming reconcile because outputs are short and the live signals
    have low hallucination surface."""
    from app.intents import development_check as i_dev
    from app.intents import live_now as i_live
    from app.intents import neighborhood as i_nbhd
    from app.intents import single_address as i_addr
    from app.planner import plan as run_planner
    tracker = emissions.Tracker()
    emissions.install(tracker)
    try:
        p = run_planner(q)
        if p.intent == "not_implemented":
            return JSONResponse({
                "paragraph": p.rationale,
                "mellea": {"rerolls": 0, "n_attempts": 0,
                           "requirements_passed": [], "requirements_failed": [],
                           "requirements_total": 0},
                "status": "not_implemented",
                "emissions": tracker.summarize(),
            })
        if p.intent == "compare":
            out = _run_compare(p, q, None, i_addr)
        elif p.intent == "development_check":
            out = i_dev.run(p, q, strict=True)
        elif p.intent == "neighborhood":
            out = i_nbhd.run(p, q, strict=True)
        elif p.intent == "live_now":
            out = i_live.run(p, q)
        else:
            out = i_addr.run(p, q, strict=True)
        out["emissions"] = tracker.summarize()
        return JSONResponse(out)
    finally:
        emissions.install(None)


@app.get("/api/agent/stream")
async def api_agent_stream(q: str):
    """SSE: emit `plan` once the planner finishes, then a `step` event per
    finalized specialist, then `final` with the full result. The intent
    runs in a thread; we marshal events through a queue."""
    import asyncio
    import queue
    out_q: queue.Queue[dict] = queue.Queue()

    tracker = emissions.Tracker()

    def runner():
        emissions.install(tracker)
        try:
            import threading as _th
            from app import llm as _llm

            def _warmup_llm():
                try:
                    _llm.chat(
                        model="granite-8b",
                        messages=[{"role": "user", "content": "hi"}],
                        options={"num_predict": 1, "temperature": 0},
                        stream=False,
                    )
                except Exception:
                    pass
            _th.Thread(target=_warmup_llm, daemon=True, name="riprap-warmup").start()

            from app.intents import development_check as i_dev
            from app.intents import live_now as i_live
            from app.intents import neighborhood as i_nbhd
            from app.intents import single_address as i_addr
            from app.planner import plan as run_planner

            def _on_plan_token(delta: str):
                out_q.put({"kind": "plan_token", "delta": delta})
            p = run_planner(q, on_token=_on_plan_token)
            out_q.put({"kind": "plan",
                       "intent": p.intent,
                       "targets": p.targets,
                       "specialists": p.specialists,
                       "rationale": p.rationale})
            if p.intent == "not_implemented":
                final = {
                    "paragraph": p.rationale,
                    "mellea": {"rerolls": 0, "n_attempts": 0,
                               "requirements_passed": [],
                               "requirements_failed": [],
                               "requirements_total": 0},
                    "status": "not_implemented",
                }
            elif p.intent == "compare":
                final = _run_compare(p, q, out_q, i_addr)
            elif p.intent == "development_check":
                final = i_dev.run(p, q, progress_q=out_q, strict=True)
            elif p.intent == "neighborhood":
                final = i_nbhd.run(p, q, progress_q=out_q, strict=True)
            elif p.intent == "live_now":
                final = i_live.run(p, q, progress_q=out_q)
            else:
                final = i_addr.run(p, q, progress_q=out_q, strict=True)
            final["emissions"] = tracker.summarize()
            out_q.put({"kind": "final", **final})
        except Exception as e:
            out_q.put({"kind": "error", "err": str(e)})
        finally:
            emissions.install(None)
            out_q.put({"kind": "_done"})

    async def event_stream():
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, runner)
        yield f"event: hello\ndata: {json.dumps({'query': q})}\n\n"

        # Stone-boundary envelope: track current Stone so we can wrap
        # contiguous step events in stone_start / stone_done. step
        # events whose name maps to None (geocode, rag, gliner) flow
        # through without opening a Stone — those are orientation /
        # ancillary, not part of any data-Stone group.
        current_stone: str | None = None
        stone_step_count: dict[str, int] = {}

        def _open(stone: str) -> str:
            stone_step_count[stone] = 0
            payload = {**_STONE_META.get(stone, {"name": stone})}
            return f"event: stone_start\ndata: {json.dumps(payload)}\n\n"

        def _close(stone: str) -> str:
            payload = {
                **_STONE_META.get(stone, {"name": stone}),
                "n_steps": stone_step_count.get(stone, 0),
            }
            return f"event: stone_done\ndata: {json.dumps(payload)}\n\n"

        while True:
            try:
                ev = await asyncio.to_thread(out_q.get, True, 1.0)
            except Exception:
                # No event for 1 s — send an SSE comment so the HF Space
                # proxy doesn't close the idle connection (proxy idle timeout
                # is ~15-20 s; the reconciler's vLLM call can take longer).
                yield ": keepalive\n\n"
                continue
            kind = ev.get("kind")
            if kind == "_done":
                break

            # First reconcile token implies the data-Stones are done
            # and the Capstone has begun, even if the FSM step event
            # for reconcile hasn't fired yet (it fires AFTER the
            # generation finishes). Open Capstone here so the UI
            # shows it lighting up while tokens stream.
            if kind == "token" and current_stone != "Capstone":
                if current_stone is not None:
                    yield _close(current_stone)
                current_stone = "Capstone"
                yield _open(current_stone)

            if kind == "step":
                step_name = ev.get("step") or ""
                stone = _STEP_TO_STONE.get(step_name)
                if stone is not None:
                    if stone != current_stone:
                        if current_stone is not None:
                            yield _close(current_stone)
                        current_stone = stone
                        yield _open(current_stone)
                    stone_step_count[stone] = (
                        stone_step_count.get(stone, 0) + 1)

            # `final` arrives after the Capstone has produced its
            # paragraph. Close the Capstone before forwarding final
            # so the trace cleanly reads: ... stone_done(Capstone),
            # final, done.
            if kind == "final" and current_stone is not None:
                yield _close(current_stone)
                current_stone = None

            yield f"event: {kind}\ndata: {json.dumps(ev, default=str)}\n\n"

        # Pipeline ended without a final (error / abort) — close any
        # still-open Stone so the client doesn't render an unbounded
        # parent row.
        if current_stone is not None:
            yield _close(current_stone)
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/agent/plan")
def api_agent_plan(q: str):
    """Just the plan, no execution. Useful for showing the agent's routing
    decision before running specialists."""
    from app.planner import plan as run_planner
    p = run_planner(q)
    return JSONResponse({
        "intent":      p.intent,
        "targets":     p.targets,
        "specialists": p.specialists,
        "rationale":   p.rationale,
    })


@app.get("/api/layers/nta")
def layer_nta(code: str):
    """Return the NTA polygon for a given NTA code as GeoJSON (EPSG:4326)."""
    from app.areas import nta as nta_mod
    g = nta_mod.load()
    sub = g[g["nta2020"] == code][["nta2020", "ntaname", "boroname", "geometry"]]
    if sub.empty:
        return JSONResponse({"type": "FeatureCollection", "features": []}, status_code=404)
    return JSONResponse(_json.loads(sub.to_json()),
                        headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/layers/sandy_clipped")
def layer_sandy_clipped(code: str):
    """Sandy inundation polygons clipped to an NTA bbox + simplified.
    Used by the agent map for neighborhood / development_check intents."""
    from app.areas import nta as nta_mod
    from app.flood_layers import sandy_inundation
    poly = nta_mod.polygon_for(code)
    if poly is None:
        return JSONResponse({"type": "FeatureCollection", "features": []})
    bounds = poly.bounds
    cx, cy = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
    # bbox half-extent in metres ~ half the polygon span × 111 km/deg
    half_m = max((bounds[2] - bounds[0]), (bounds[3] - bounds[1])) / 2 * 111_000
    return JSONResponse(_clip_simplify(sandy_inundation.load(), cy, cx, half_m * 1.2),
                        headers={"Cache-Control": "public, max-age=600"})


@app.get("/api/layers/dep_clipped")
def layer_dep_clipped(code: str, scenario: str = "dep_extreme_2080"):
    """DEP scenario polygons clipped to an NTA bbox + simplified."""
    from app.areas import nta as nta_mod
    from app.flood_layers import dep_stormwater
    poly = nta_mod.polygon_for(code)
    if poly is None:
        return JSONResponse({"type": "FeatureCollection", "features": []})
    bounds = poly.bounds
    cx, cy = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
    half_m = max((bounds[2] - bounds[0]), (bounds[3] - bounds[1])) / 2 * 111_000
    return JSONResponse(_clip_simplify(dep_stormwater.load(scenario), cy, cx, half_m * 1.2,
                                        props_keep={"Flooding_Category"}),
                        headers={"Cache-Control": "public, max-age=600"})


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


@app.get("/api/layers/ida_hwm")
def layer_ida_hwm(lat: float, lon: float, r: float = 1500):
    """USGS Hurricane Ida 2021 high-water marks within radius_m of (lat, lon).
    Returns GeoJSON FeatureCollection of Point features. No geopandas needed —
    HWMs are already points so haversine filter is sufficient."""
    from app.flood_layers import ida_hwm as _ida
    features = []
    for f in _ida._load():
        flon, flat = f["geometry"]["coordinates"]
        d = _ida._haversine_m(lat, lon, flat, flon)
        if d <= r:
            p = f["properties"]
            features.append({
                "type": "Feature",
                "geometry": f["geometry"],
                "properties": {
                    "hwm_id": p.get("hwm_id"),
                    "site_description": p.get("site_description"),
                    "elev_ft": p.get("elev_ft"),
                    "height_above_gnd_ft": p.get("height_above_gnd"),
                    "hwm_quality": p.get("hwm_quality"),
                    "waterbody": p.get("waterbody"),
                    "distance_m": round(d, 0),
                },
            })
    return JSONResponse({"type": "FeatureCollection", "features": features},
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
