"""Riprap web UI — FastAPI + SSE streaming of the Burr FSM trace.

Run: uvicorn web.main:app --reload --port 8000
"""
from __future__ import annotations

import json
import os
import re
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import (  # noqa: E402
    FileResponse,
    JSONResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app import emissions  # noqa: E402
from app.context import floodnet  # noqa: E402
from app.flood_layers import dep_stormwater, sandy_inundation  # noqa: E402
from app.fsm import iter_steps  # noqa: E402
from riprap.core.json_safe import to_json_safe as _to_json_safe  # noqa: E402
from riprap.core.pebbles import load_registry as _load_pebbles  # noqa: E402
from riprap.core.stones import load_stones as _load_stones  # noqa: E402

# Deployment dir (default deployments/nyc; override via RIPRAP_DEPLOYMENT).
# Stones + pebbles load once at import time.
_env_deployment = os.environ.get("RIPRAP_DEPLOYMENT")
_DEPLOYMENT = (
    Path(_env_deployment) if _env_deployment
    else Path(__file__).resolve().parent.parent / "deployments" / "nyc"
)
_STONES = _load_stones(_DEPLOYMENT)
_PEBBLES = _load_pebbles(_DEPLOYMENT)

# Pretty-printed Stone metadata the frontend renders as parent-row labels.
# Sourced from deployments/<name>/stones.yaml.
_STONE_META: dict[str, dict] = {
    s.name: {"name": s.name, "tagline": s.tagline, "description": s.description}
    for s in _STONES.all()
}

# Map FSM trace step name -> Stone display name.
#
# Built in two layers:
#   1. From the pebble registry — every pebble contributes (pebble.id ->
#      Stone.name) automatically. Add new pebble manifests, this map grows
#      itself. No code edits needed.
#   2. Explicit overrides for FSM steps that DON'T have manifests yet
#      (NTA aggregates, asset-class exposures, terramind synthesis, the
#      eo_chip cluster, reconciler variants) and for legacy trace aliases
#      (ida_hwm_2021 -> ida_hwm pebble, prithvi_eo_v2 -> prithvi_water, etc.).
#
# Steps not present in this map don't open a Stone boundary — they're
# orientation / policy infrastructure shared across Stones (geocode,
# rag_granite_embedding, gliner_extract, nta_resolve and friends).
def _stone_display(stone_id: str) -> str:
    return _STONES.get(stone_id).name


_STEP_TO_STONE: dict[str, str] = {
    pebble.id: _stone_display(pebble.stone) for pebble in _PEBBLES.all()
}
# Legacy trace-name aliases (the FSM still emits these older labels for
# some steps). Each maps to the same stone as its modern pebble id.
_STEP_TO_STONE.update({
    "sandy_inundation":  _stone_display("cornerstone"),
    "ida_hwm_2021":      _stone_display("cornerstone"),
    "prithvi_eo_v2":     _stone_display("cornerstone"),
    "microtopo_lidar":   _stone_display("cornerstone"),
    "dep_stormwater":    _stone_display("cornerstone"),
    "prithvi_eo_live":   _stone_display("touchstone"),
})
# FSM steps that don't have manifests yet (chip-dependent cluster, NTA
# aggregates, asset-class exposures, terramind synthesis, reconciler).
# These shrink as more pebbles get ported.
_STEP_TO_STONE.update({
    "sandy_nta":                  _stone_display("cornerstone"),
    "dep_extreme_2080_nta":       _stone_display("cornerstone"),
    "dep_moderate_2050_nta":      _stone_display("cornerstone"),
    "dep_moderate_current_nta":   _stone_display("cornerstone"),
    "microtopo_nta":              _stone_display("cornerstone"),
    "nyc311_nta":                 _stone_display("touchstone"),
    "mta_entrance_exposure":      _stone_display("keystone"),
    "nycha_development_exposure": _stone_display("keystone"),
    "doe_school_exposure":        _stone_display("keystone"),
    "doh_hospital_exposure":      _stone_display("keystone"),
    "terramind_synthesis":        _stone_display("keystone"),
    "eo_chip_fetch":              _stone_display("keystone"),
    "terramind_buildings":        _stone_display("keystone"),
    "terramind_lulc":             _stone_display("touchstone"),
    "reconcile_granite41":        _stone_display("capstone"),
    "mellea_reconcile_address":   _stone_display("capstone"),
    "reconcile_neighborhood":     _stone_display("capstone"),
    "reconcile_development":      _stone_display("capstone"),
    "reconcile_live_now":         _stone_display("capstone"),
})

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
SVELTEKIT_BUILD = ROOT / "sveltekit" / "build"

app = FastAPI(title="Riprap")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# SvelteKit static build (adapter-static). Serves the new design-system UI
# from / and /q/<query>. The legacy custom-element pages remain at
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


@app.get("/api/debug/vllm-direct")
def api_debug_vllm_direct():
    """Direct diagnostic: calls vLLM with a reconciler-style request,
    bypassing LiteLLM Router, to surface the raw HTTP status and error."""

    import httpx

    vllm_base = os.environ.get("RIPRAP_LLM_BASE_URL", "").rstrip("/")
    vllm_key = os.environ.get("RIPRAP_LLM_API_KEY", "") or "EMPTY"
    if not vllm_base:
        return JSONResponse({"error": "RIPRAP_LLM_BASE_URL not set"}, status_code=400)

    model_name = os.environ.get("RIPRAP_LLM_VLLM_8B_NAME", "granite4.1:3b")

    # Two payloads: minimal (sanity check) and full-load (context overflow test).
    # Generate a realistic 14-doc payload that approximates what the reconciler sends.
    _FILLER_DOC = (
        "Source: NYC OEM Sandy 2012 inundation. "
        "This location is within the Sandy 2012 inundation zone, "
        "which experienced flood depths of 1–4 ft. "
        "FEMA Flood Zone AE. BFE 12 ft NAVD88."
    )
    full_docs = [
        {"doc_id": f"doc_{i}", "text": f"[doc_{i}] " + _FILLER_DOC}
        for i in range(14)
    ]
    _LONG_SYSTEM = (
        "Write a flood-exposure briefing for an NYC address. "
        "Use ONLY the facts in the provided documents. "
        "Every sentence that contains a number MUST include a citation tag. "
        "Output the four sections: Status, History, Forecast, and Risk. "
        "Valid document IDs: " + ", ".join(f"doc_{i}" for i in range(14)) + "."
    ) * 3  # ~500 tokens

    payloads = {
        "minimal": {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You are a flood risk analyst."},
                {"role": "user", "content": "Write the cited paragraph now."},
            ],
            "max_tokens": 64,
            "temperature": 0,
            "stream": False,
            "chat_template_kwargs": {"documents": [
                {"doc_id": "noaa_tides", "text": "Tide: 4.14 ft MLLW."},
                {"doc_id": "microtopo", "text": "Elevation: 1.37 m."},
            ]},
        },
        "full_load": {
            "model": model_name,
            "messages": [
                {"role": "system", "content": _LONG_SYSTEM},
                {"role": "user", "content": "Write the cited paragraph now."},
            ],
            "max_tokens": 512,
            "temperature": 0,
            "stream": False,
            "chat_template_kwargs": {"documents": full_docs},
        },
    }
    results = {}
    for name, payload in payloads.items():
        try:
            with httpx.Client(timeout=30.0) as c:
                r = c.post(
                    f"{vllm_base}/chat/completions",
                    headers={"Authorization": f"Bearer {vllm_key}",
                             "Content-Type": "application/json"},
                    json=payload,
                )
            try:
                body = r.json()
            except Exception:
                body = r.text[:300]
            results[name] = {"status": r.status_code, "body_snippet": str(body)[:400]}
        except Exception as e:
            results[name] = {"error": str(e)}

    return JSONResponse({
        "model": model_name,
        "vllm_base": vllm_base,
        "results": results,
    })


def _stones_pebbles_for_deployment(deployment_name: str | None):
    """Resolve (stones_registry, pebble_registry) for a deployment name.

    None → the server's boot-time deployment (back-compat). A bare name
    like 'boston' resolves to `deployments/boston/` regardless of which
    deployment the server booted with — this is what makes per-query
    routing reach the UI scaffold.
    """
    from pathlib import Path
    if not deployment_name:
        return _STONES, _PEBBLES
    from riprap.core.pebbles.deployments import deployment_by_name as _dep_by_name  # noqa: PLC0415
    dep = _dep_by_name(deployment_name)
    if dep is None:
        # Try treating as a path / fallback to boot deployment so the UI
        # never gets a 500 from a malformed query param.
        p = Path(deployment_name)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent / deployment_name
        if not p.exists():
            return _STONES, _PEBBLES
        stones_root = p
    else:
        stones_root = dep.root
    return _load_stones(stones_root), _load_pebbles(stones_root)


@app.get("/api/pebbles")
def api_pebbles(deployment: str | None = None):
    """Return a deployment's stones + pebbles for evidence-card rendering.

    With per-query routing, the frontend MUST pass `?deployment=<name>`
    once the SSE stream resolves the deployment for a given query —
    otherwise the UI renders the server's boot-time scaffold (which
    e.g. lists NYC pebbles for a Boston run, the exact bug the user
    reported via the screenshot).

    Per-pebble payload is the manifest minus implementation guts (config /
    shaper / trace_summary / spatial.crs) — just the parts the UI needs to
    draw a card and show provenance.
    """
    stones_reg, pebble_reg = _stones_pebbles_for_deployment(deployment)
    stones = [
        {
            "id": s.id,
            "name": s.name,
            "tagline": s.tagline,
            "description": s.description,
            "order": s.order,
        }
        for s in stones_reg.all()
    ]
    pebbles = []
    for p in pebble_reg.all():
        m = p.manifest
        pebbles.append({
            "id": m.id,
            "type": m.type,
            "title": m.title,
            "stone": m.stone,
            "tier": m.tier,
            "display": {
                "order": m.display.order,
                "kind": m.display.kind,
                "variant": m.display.variant,
                "map_layer": m.display.map_layer,
                "icon": m.display.icon,
            },
            "narration": {
                "short": m.narration.short,
                "template": m.narration.template,
            },
            "provenance": {
                "source_name": m.provenance.source_name,
                "source_url": m.provenance.source_url,
                "license": m.provenance.license,
                "citation": m.provenance.citation,
                "doc_id": m.provenance.doc_id,
                "last_updated": (
                    m.provenance.last_updated.isoformat()
                    if m.provenance.last_updated else None
                ),
            },
            "fallback": {
                "on_offline": m.fallback.on_offline,
                "message": m.fallback.message,
            },
        })
    pebbles.sort(
        key=lambda x: (
            stones_reg.get(x["stone"]).order if x["stone"] in stones_reg else 99,
            x["display"]["order"] if x["display"]["order"] is not None else 999,
            x["id"],
        )
    )
    return JSONResponse({"stones": stones, "pebbles": pebbles})


@app.get("/api/deployment")
def api_deployment(deployment: str | None = None):
    """Active-deployment descriptor for the UI shell.

    Returns the city + hazard names the chrome renders in the header
    chip + browser title. Pulled from each deployment's `stones.yaml`
    `deployment:` block (with sensible defaults derived from the
    deployment directory name when the block is absent).

    Without `?deployment`, returns the server's boot-time deployment
    (back-compat). With `?deployment=<name>` (e.g. `boston`), returns
    that deployment's descriptor — what the per-query header chip
    consumes once the SSE stream resolves the deployment for a query.
    """
    if not deployment:
        return JSONResponse({
            "name": _DEPLOYMENT.name,
            "city": _STONES.city,
            "hazard": _STONES.hazard,
        })
    stones_reg, _ = _stones_pebbles_for_deployment(deployment)
    return JSONResponse({
        "name": deployment,
        "city": stones_reg.city,
        "hazard": stones_reg.hazard,
    })


@app.post("/api/print")
async def api_print(request: Request) -> Response:
    """Render a completed briefing to PDF.

    Accepts the briefing JSON in the request body (the same shape the
    SSE stream emits as its final `final` event). Returns the PDF as
    `application/pdf` with a sensible filename. The document carries a
    SHA-256 hash on its stamp page that two reviewers comparing the
    same briefing can verify by.

    Requires WeasyPrint's system deps (pango + cairo) on the host:
      macOS:  brew install pango
      Linux:  apt-get install libpango-1.0-0 libpangoft2-1.0-0

    Returns 503 with a structured error body when the deps are missing
    so the UI can surface a helpful "PDF rendering unavailable" toast
    instead of a stack trace.
    """
    from app.print_pdf import PdfRenderFailed, render_briefing_pdf  # noqa: PLC0415

    try:
        payload = await request.json()
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "expected a JSON object body"}, status_code=400)

    # Annotate with active deployment so the cover-page chip reads
    # consistently with the web view, even if the client didn't post it.
    payload.setdefault("deployment", {
        "name": _DEPLOYMENT.name,
        "city": _STONES.city,
        "hazard": _STONES.hazard,
    })

    try:
        pdf_bytes = render_briefing_pdf(payload)
    except PdfRenderFailed as e:
        return JSONResponse(
            {"error": "pdf_unavailable", "detail": str(e)},
            status_code=503,
        )

    # Filename: <city>-<slug-of-address>.pdf. Browsers honor
    # Content-Disposition: attachment + the filename hint, while still
    # letting users preview in a new tab.
    addr = (payload.get("query") or payload.get("address") or "briefing")
    slug = re.sub(r"[^a-z0-9]+", "-", str(addr).lower()).strip("-")[:60] or "briefing"
    fname = f"riprap-{slug}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{fname}"',
            # Don't cache user-specific renders.
            "Cache-Control": "no-store",
        },
    )


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
    """Legacy `/q/sample` route — used to serve a prerendered Red Hook
    demo briefing whose citations + numbers were fabricated. That violated
    the Plain Writing Act voice the rest of the surface now commits to,
    so the synthetic page was removed (see commit history). Redirect
    to a real anchor address that runs an actual briefing through the
    normal pipeline; CityPicker on the landing offers the same instant-
    click affordance for each shipped city.
    """
    from fastapi.responses import RedirectResponse  # noqa: PLC0415
    return RedirectResponse(
        url="/q/189%20Atlantic%20Avenue%2C%20Brooklyn%2C%20NY",
        status_code=308,
    )


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
            # Bind loop vars on the instance, not via closure (closure would
            # late-bind across iterations).
            class _TaggedQ:
                def __init__(self, q, lab):
                    self._q = q
                    self._label = lab
                def put(self, ev):
                    if ev.get("kind") == "step":
                        self._q.put({**ev, "target_label": self._label})
                    else:
                        self._q.put(ev)
            effective_q = _TaggedQ(out_q, label)
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
    full result as JSON.

    Two runtime paths:
      RIPRAP_USE_BURR_APP=1 (default) — runs the new manifest-driven
        Burr Application (intake → 4 stones in parallel → capstone).
        See `riprap/core/burr/app.py`.
      RIPRAP_USE_BURR_APP=0 — falls back to the legacy intent dispatch
        (app/intents/single_address.py etc.). Use during migration
        validation if a regression appears.
    """
    use_burr = os.environ.get("RIPRAP_USE_BURR_APP", "1").lower() in ("1", "true", "yes")
    tracker = emissions.Tracker()
    emissions.install(tracker)
    try:
        if use_burr:
            from riprap.core.burr.app import run as burr_run
            out = burr_run(q)
        else:
            from app.intents import development_check as i_dev
            from app.intents import live_now as i_live
            from app.intents import neighborhood as i_nbhd
            from app.intents import single_address as i_addr
            from app.planner import plan as run_planner
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
        return JSONResponse(_to_json_safe(out))
    finally:
        emissions.install(None)


def _run_burr_single_address(plan, query: str, out_q) -> dict:
    """SSE-streaming single_address path through the new Burr Application.

    Mirrors `app.intents.single_address.run`'s contract:
      - pushes {kind: step | token | mellea_attempt} to `out_q`
      - returns a final dict with `intent`, `plan`, and all pebble values
        + the cited paragraph.

    The threadlocal token / mellea-attempt callbacks installed here are
    snapshotted by `iter_steps_from_plan`'s worker thread, so reconcile
    streams Granite tokens out live exactly like the legacy path.
    """
    from app.fsm import (
        set_mellea_attempt_callback,
        set_planned_specialists,
        set_planner_intent,
        set_strict_mode,
        set_token_callback,
        set_user_query,
    )
    from riprap.core.burr.app import iter_steps_from_plan

    set_strict_mode(True)
    set_planned_specialists(plan.specialists or [])
    set_user_query(query)
    set_planner_intent(plan.intent)

    def _on_token(delta: str, attempt_idx: int = 0):
        out_q.put({"kind": "token", "delta": delta,
                   "attempt": attempt_idx + 1})

    def _on_mellea_attempt(attempt_idx, passed, failed):
        out_q.put({"kind": "mellea_attempt",
                   "attempt": attempt_idx,
                   "passed": passed, "failed": failed})

    set_token_callback(_on_token)
    set_mellea_attempt_callback(_on_mellea_attempt)

    first_target = ""
    if plan.targets:
        t0 = plan.targets[0]
        first_target = t0.get("text") or t0.get("address") or ""

    plan_dict = {
        "intent": plan.intent, "targets": plan.targets,
        "specialists": plan.specialists, "rationale": plan.rationale,
    }

    try:
        final = None
        for ev in iter_steps_from_plan(query, plan_dict, plan.intent, first_target):
            if ev["kind"] == "step":
                out_q.put({"kind": "step", **ev})
            else:
                final = ev
        out = {**(final or {}), "trace": []}
    finally:
        set_token_callback(None)
        set_mellea_attempt_callback(None)
        set_strict_mode(False)
        set_planned_specialists(None)
        set_user_query(None)
        set_planner_intent(None)

    out["intent"] = "single_address"
    out["plan"] = plan_dict
    return out


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
            from app.intents import development_check as i_dev
            from app.intents import live_now as i_live
            from app.intents import neighborhood as i_nbhd
            from app.intents import single_address as i_addr
            from app.planner import plan as run_planner

            def _on_plan_token(delta: str):
                out_q.put({"kind": "plan_token", "delta": delta})
            p = run_planner(q, on_token=_on_plan_token)

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
                # single_address path. RIPRAP_USE_BURR_APP=1 (default)
                # routes through the new manifest-driven Burr Application
                # with parallel Stone fan-out. Falls back to the legacy
                # linear FSM via the intent module when the flag is off.
                if os.environ.get("RIPRAP_USE_BURR_APP", "1").lower() in ("1", "true", "yes"):
                    final = _run_burr_single_address(p, q, out_q)
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
                # Per-query routing handshake — when the pipeline
                # resolves the deployment, push it to the UI so the
                # header chip + pebble scaffold can pivot off the
                # deployment that actually fanned out, not whatever
                # the server booted with.
                if step_name == "select_deployment":
                    result = ev.get("result") or {}
                    dep_name = result.get("deployment")
                    yield (
                        "event: deployment\n"
                        f"data: {json.dumps({'name': dep_name, 'city': result.get('city'), 'state': result.get('state')})}\n\n"
                    )
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
