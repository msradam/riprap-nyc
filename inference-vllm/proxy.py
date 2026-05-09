"""Riprap vLLM Space — bearer-auth proxy on port 7860.

Forwards /v1/chat/completions and /v1/completions to vLLM on
localhost:8000 (which exposes the OpenAI-compatible surface
natively), and forwards specialist endpoints to riprap-models on
localhost:7861.

Same auth shape as the Ollama-backed riprap-inference Space — both
UI Spaces (lablab + msradam/riprap) carry the shared bearer in
RIPRAP_LLM_API_KEY.
"""
from __future__ import annotations

import os
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

VLLM_URL = "http://127.0.0.1:8000"
MODELS_URL = "http://127.0.0.1:7861"

PROXY_TOKEN = os.environ.get("RIPRAP_PROXY_TOKEN", "")

app = FastAPI(title="Riprap vLLM Proxy")


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
    return {"service": "riprap-vllm", "ok": True}


@app.get("/healthz")
async def healthz():
    out = {"proxy": "ok"}
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.get(f"{VLLM_URL}/health")
            out["vllm"] = "ok" if r.status_code == 200 else f"http_{r.status_code}"
        except Exception as e:
            out["vllm"] = f"err: {type(e).__name__}"
        try:
            r = await client.get(f"{MODELS_URL}/healthz")
            out["riprap_models"] = "ok" if r.status_code == 200 else f"http_{r.status_code}"
        except Exception as e:
            out["riprap_models"] = f"err: {type(e).__name__}"
    return out


async def _stream_passthrough(upstream: httpx.Response) -> AsyncIterator[bytes]:
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
    upstream = await client.send(upstream_req, stream=is_stream)

    if is_stream:
        return StreamingResponse(
            _stream_passthrough(upstream),
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "text/event-stream"),
            background=upstream.aclose,
        )
    content = await upstream.aread()
    await upstream.aclose()
    await client.aclose()
    return Response(
        content=content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
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
