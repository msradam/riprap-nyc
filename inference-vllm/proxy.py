"""Riprap vLLM Space — bearer-auth proxy on port 7860.

Forwards /v1/chat/completions and /v1/completions to vLLM on
localhost:8000 (which exposes the OpenAI-compatible surface
natively), and forwards specialist endpoints to riprap-models on
localhost:7861.

Same auth shape as the Ollama-backed riprap-inference Space — both
UI Spaces (lablab + msradam/riprap) carry the shared bearer in
RIPRAP_LLM_API_KEY.

GPU power
---------
A background sampler reads `nvmlDeviceGetPowerUsage` every 100 ms
into a ring buffer. Each forwarded POST records the wall-clock
window of the upstream call and reports:

    X-GPU-Power-W      mean draw (W) across the window
    X-GPU-Energy-J     energy (J) over the window
    X-GPU-Duration-S   forwarded-call duration in seconds

The `/v1/power` GET also exposes the instantaneous reading for
clients that prefer to bracket their own work with two samples
(used by the LLM client path where LiteLLM hides response headers).

Reading from NVML costs <1 ms per sample; the ring buffer holds 60 s
of 100 ms samples (600 entries). Sampler degrades to a no-op if NVML
init fails (unlikely on an L4 Space, but possible on CPU-only sims).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

log = logging.getLogger("riprap.proxy")

VLLM_URL = "http://127.0.0.1:8000"
MODELS_URL = "http://127.0.0.1:7861"

PROXY_TOKEN = os.environ.get("RIPRAP_PROXY_TOKEN", "")

app = FastAPI(title="Riprap vLLM Proxy")


# ---------------------------------------------------------------------------
# GPU power sampler
# ---------------------------------------------------------------------------

# Ring buffer of (unix_ts, power_w) samples. 600 entries × 100 ms = 60 s
# of history, which covers the longest single inference call we'd see
# (vLLM cold-compile is ~120 s but that surfaces as multiple shorter
# reads from inside vLLM's loop, not as a single forwarded POST).
_SAMPLES: deque[tuple[float, float]] = deque(maxlen=600)
_SAMPLER_TASK: asyncio.Task | None = None
_NVML_OK: bool = False
_NVML_HANDLE = None
_NVML_ERR: str | None = None


def _init_nvml() -> None:
    """Best-effort NVML init. On failure we record the error string and
    leave _NVML_OK=False — the proxy still serves traffic, just without
    real power data."""
    global _NVML_OK, _NVML_HANDLE, _NVML_ERR
    try:
        import pynvml
        pynvml.nvmlInit()
        # Single-GPU L4 Space — device 0 is the L4. If a future deploy
        # uses multi-GPU we'd average across handles, but that's not
        # the current shape.
        _NVML_HANDLE = pynvml.nvmlDeviceGetHandleByIndex(0)
        # Probe once to confirm power query works.
        pynvml.nvmlDeviceGetPowerUsage(_NVML_HANDLE)
        _NVML_OK = True
        log.info("NVML initialized for GPU 0")
    except Exception as e:  # noqa: BLE001
        _NVML_ERR = f"{type(e).__name__}: {e}"
        _NVML_OK = False
        log.warning("NVML init failed (%s); power data will be unavailable",
                    _NVML_ERR)


def _read_power_w() -> float | None:
    """Instantaneous package power in watts. None if NVML is dead."""
    if not _NVML_OK:
        return None
    try:
        import pynvml
        # nvmlDeviceGetPowerUsage returns milliwatts.
        mw = pynvml.nvmlDeviceGetPowerUsage(_NVML_HANDLE)
        return mw / 1000.0
    except Exception:
        return None


async def _power_sampler() -> None:
    """Background loop, 100 ms cadence. Cheap (~1 ms NVML query)."""
    while True:
        p = _read_power_w()
        if p is not None:
            _SAMPLES.append((time.time(), p))
        await asyncio.sleep(0.1)


def _avg_power_over(t0: float, t1: float) -> float | None:
    """Mean of samples in the [t0, t1] window. Returns None when no
    samples landed in the window (callers fall back to a single
    instantaneous read)."""
    if not _SAMPLES:
        return None
    bucket = [p for ts, p in _SAMPLES if t0 <= ts <= t1]
    if not bucket:
        # Window may be too short / sampler hadn't ticked yet — return
        # the most recent reading we have as the next-best signal.
        return _SAMPLES[-1][1] if _SAMPLES else None
    return sum(bucket) / len(bucket)


@app.on_event("startup")
async def _startup() -> None:
    _init_nvml()
    if _NVML_OK:
        global _SAMPLER_TASK
        _SAMPLER_TASK = asyncio.create_task(_power_sampler())


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _SAMPLER_TASK is not None:
        _SAMPLER_TASK.cancel()
    if _NVML_OK:
        try:
            import pynvml
            pynvml.nvmlShutdown()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Auth + routing
# ---------------------------------------------------------------------------


def _check_auth(request: Request) -> None:
    if not PROXY_TOKEN:
        raise HTTPException(503, "RIPRAP_PROXY_TOKEN not set on the inference Space")
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    if auth.removeprefix("Bearer ").strip() != PROXY_TOKEN:
        raise HTTPException(401, "invalid bearer token")


@app.get("/")
def root():
    return {"service": "riprap-vllm", "ok": True,
            "nvml": _NVML_OK,
            "nvml_err": None if _NVML_OK else _NVML_ERR}


@app.get("/healthz")
async def healthz():
    out = {"proxy": "ok", "nvml": "ok" if _NVML_OK else f"err: {_NVML_ERR}"}
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.get(f"{VLLM_URL}/health")
            out["vllm"] = "ok" if r.status_code == 200 else f"http_{r.status_code}"
        except Exception as e:
            out["vllm"] = f"err: {type(e).__name__}"
        try:
            r = await client.get(f"{MODELS_URL}/healthz")
            if r.status_code == 200:
                out["riprap_models"] = "ok"
                # Bubble up the loaded-model list + last-error map so
                # operators can diagnose without hitting /v1/diag.
                try:
                    body = r.json()
                    out["riprap_models_loaded"] = body.get("models_loaded")
                    out["riprap_models_last_errors"] = body.get("last_errors")
                except Exception:
                    pass
            else:
                out["riprap_models"] = f"http_{r.status_code}"
        except Exception as e:
            out["riprap_models"] = f"err: {type(e).__name__}"
    return out


@app.get("/v1/diag", include_in_schema=False)
async def diag(request: Request) -> Response:
    """Forward to riprap-models /v1/diag (auth-required).
    Operator-only diagnostic snapshot — what's loaded, last per-stage
    error with traceback tail, and CUDA memory state per device."""
    _check_auth(request)
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{MODELS_URL}/v1/diag")
        except Exception as e:
            return JSONResponse({"ok": False,
                                 "err": f"upstream: {type(e).__name__}: {e}"},
                                status_code=503)
        return Response(content=r.content,
                        status_code=r.status_code,
                        media_type=r.headers.get("content-type", "application/json"))


@app.get("/v1/power")
async def power(request: Request) -> Response:
    """Instantaneous and recent-window GPU power (W).

    Used by the LLM client path: LiteLLM doesn't surface response
    headers, so the client samples /v1/power before/after its
    chat.completions call to bracket the energy reading. The recent
    1-second average smooths over the 100 ms sampler cadence.
    """
    _check_auth(request)
    if not _NVML_OK:
        return JSONResponse(
            {"ok": False, "err": _NVML_ERR or "NVML unavailable"},
            status_code=503,
        )
    now = time.time()
    inst = _read_power_w()
    avg_1s = _avg_power_over(now - 1.0, now) if _SAMPLES else None
    avg_5s = _avg_power_over(now - 5.0, now) if _SAMPLES else None
    return JSONResponse({
        "ok": True,
        "ts": now,
        "power_w": inst,
        "power_w_avg_1s": avg_1s,
        "power_w_avg_5s": avg_5s,
        "samples_held": len(_SAMPLES),
        "device": "NVIDIA L4",
    })


# ---------------------------------------------------------------------------
# Forwarding
# ---------------------------------------------------------------------------


async def _stream_passthrough(upstream: httpx.Response,
                              add_headers: dict[str, str]) -> AsyncIterator[bytes]:
    # Streaming responses can't carry headers added after the first byte —
    # we set them on the StreamingResponse before yielding. add_headers
    # is captured by reference in the caller via a closure.
    async for chunk in upstream.aiter_raw():
        yield chunk


async def _proxy_post(upstream_base: str, path: str, request: Request,
                      *, timeout: float = 300.0) -> Response:
    body = await request.body()
    headers = {
        "content-type": request.headers.get("content-type", "application/json"),
        "accept": request.headers.get("accept", "*/*"),
    }
    is_stream = b'"stream":true' in body or b'"stream": true' in body
    client = httpx.AsyncClient(timeout=timeout)
    upstream_req = client.build_request(
        "POST", f"{upstream_base}{path}", content=body, headers=headers
    )

    t0 = time.time()
    upstream = await client.send(upstream_req, stream=is_stream)

    if is_stream:
        # We can't measure end-of-stream wallclock without consuming the
        # body, but the client sees per-call duration on its side. For
        # streaming we record headers describing only the start power
        # snapshot — useful as a sanity signal, not a true energy.
        snap = _read_power_w()
        hdrs = {
            "x-gpu-power-w": f"{snap:.2f}" if snap is not None else "",
            "x-gpu-stream": "1",
        }
        return StreamingResponse(
            _stream_passthrough(upstream, hdrs),
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "text/event-stream"),
            headers=hdrs,
            background=upstream.aclose,
        )

    content = await upstream.aread()
    await upstream.aclose()
    await client.aclose()
    t1 = time.time()
    duration_s = max(t1 - t0, 0.0)

    extra_headers: dict[str, str] = {}
    if _NVML_OK:
        avg_w = _avg_power_over(t0, t1)
        if avg_w is not None:
            energy_j = avg_w * duration_s
            extra_headers = {
                "x-gpu-power-w": f"{avg_w:.3f}",
                "x-gpu-energy-j": f"{energy_j:.3f}",
                "x-gpu-duration-s": f"{duration_s:.3f}",
                "x-gpu-device": "NVIDIA L4",
            }

    media_type = upstream.headers.get("content-type", "application/json")
    response_headers = dict(extra_headers)
    return Response(
        content=content,
        status_code=upstream.status_code,
        media_type=media_type,
        headers=response_headers,
    )


# vLLM (OpenAI-compat) routes
@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    _check_auth(request)
    return await _proxy_post(VLLM_URL, "/v1/chat/completions", request)


@app.post("/v1/completions")
async def completions(request: Request) -> Response:
    _check_auth(request)
    return await _proxy_post(VLLM_URL, "/v1/completions", request)


@app.post("/v1/embeddings")
async def embeddings(request: Request) -> Response:
    """Routed to riprap-models's granite-embed (vLLM doesn't serve our
    embedding model)."""
    _check_auth(request)
    return await _proxy_post(MODELS_URL, "/v1/granite-embed", request)


@app.get("/v1/models")
async def models(request: Request) -> Response:
    _check_auth(request)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{VLLM_URL}/v1/models")
        return Response(content=r.content, status_code=r.status_code,
                        media_type=r.headers.get("content-type", "application/json"))


# riprap-models specialist routes
@app.post("/v1/prithvi-pluvial")
async def prithvi_pluvial(request: Request) -> Response:
    _check_auth(request)
    return await _proxy_post(MODELS_URL, "/v1/prithvi-pluvial", request)


@app.post("/v1/terramind")
async def terramind(request: Request) -> Response:
    _check_auth(request)
    return await _proxy_post(MODELS_URL, "/v1/terramind", request)


@app.post("/v1/ttm-forecast")
async def ttm_forecast(request: Request) -> Response:
    _check_auth(request)
    return await _proxy_post(MODELS_URL, "/v1/ttm-forecast", request)


@app.post("/v1/gliner-extract")
async def gliner_extract(request: Request) -> Response:
    _check_auth(request)
    return await _proxy_post(MODELS_URL, "/v1/gliner-extract", request)


@app.api_route("/v1/{path:path}", methods=["POST"])
async def catch_all(path: str, request: Request) -> Response:
    _check_auth(request)
    return await _proxy_post(MODELS_URL, f"/v1/{path}", request)
