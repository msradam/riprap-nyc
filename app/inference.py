"""Remote-vs-local ML inference router.

Mirrors the call-surface shape of `app/llm.py` but for the non-LLM
heavy models (Prithvi, TerraMind, TTM, Granite Embedding, GLiNER).

The droplet runs a `riprap-models` FastAPI service alongside vLLM that
exposes an OpenAI-style endpoint per model class. When configured the
router POSTs the relevant payload there and returns the parsed response;
on connection error / 5xx / timeout it surfaces a typed exception that
caller modules catch and fall back to a local in-process model load.

Backend selection (env):

  RIPRAP_ML_BACKEND   = "remote" | "local" | "auto"  (default: auto)
                        - remote: use only the droplet, raise if it errors
                        - local : never call the droplet, always use the
                                  in-process model
                        - auto  : try remote first, fall back to local if
                                  remote is unreachable / errors out;
                                  same semantics as app/llm.py
  RIPRAP_ML_BASE_URL  = http://129.212.181.238:8002    (no trailing slash)
  RIPRAP_ML_API_KEY   = <bearer token>

The router is *transport*-only — it does not own model bytes, weights,
or framework imports. Each specialist that wants remote inference calls
into the helpers below and provides its own local fallback. That keeps
the dependency graph clean: the local code path keeps working when the
RIPRAP_ML_* env is unset (e.g. on first-light dev or in unit tests).
"""
from __future__ import annotations

import base64
import logging
import os
import time
from collections.abc import Iterable
from typing import Any

import httpx

from app import emissions

log = logging.getLogger("riprap.inference")

_BACKEND = os.environ.get("RIPRAP_ML_BACKEND", "auto").lower()
_BASE_URL = os.environ.get("RIPRAP_ML_BASE_URL", "").rstrip("/")
_API_KEY = os.environ.get("RIPRAP_ML_API_KEY", "")
_DEFAULT_TIMEOUT = float(os.environ.get("RIPRAP_ML_TIMEOUT_S", "60"))


class RemoteUnreachable(RuntimeError):
    """Raised when the remote inference service is unconfigured, down,
    times out, or returns 5xx. Callers catch this to fall through to a
    local model load. 4xx errors propagate as the generic exception so
    a caller bug doesn't get masked by a "fallback to local" path."""


def remote_enabled() -> bool:
    """True iff the router is configured to attempt remote calls.
    Returns False under explicit `local` mode or when the base URL is
    empty (the auto-default with no env config)."""
    if _BACKEND == "local":
        return False
    if not _BASE_URL:
        return False
    return True


def _client(timeout: float | None = None) -> httpx.Client:
    headers = {"User-Agent": "riprap-app/0.4.5"}
    if _API_KEY:
        headers["Authorization"] = f"Bearer {_API_KEY}"
    return httpx.Client(
        base_url=_BASE_URL,
        headers=headers,
        timeout=timeout if timeout is not None else _DEFAULT_TIMEOUT,
    )


def _post(path: str, payload: dict[str, Any], timeout: float | None = None) -> dict:
    """POST {payload} as JSON to the remote service's `path`. Returns the
    parsed JSON body. Raises RemoteUnreachable on transport errors;
    raises HTTPStatusError on 4xx so caller bugs surface."""
    if not remote_enabled():
        raise RemoteUnreachable("remote ML backend not configured "
                                "(RIPRAP_ML_BASE_URL empty or BACKEND=local)")
    t0 = time.monotonic()
    try:
        with _client(timeout) as c:
            r = c.post(path, json=payload)
    except (httpx.ConnectError, httpx.ReadError, httpx.WriteError,
             httpx.TimeoutException, httpx.RemoteProtocolError) as e:
        raise RemoteUnreachable(f"{type(e).__name__}: {e}") from e
    if r.status_code >= 500:
        raise RemoteUnreachable(f"HTTP {r.status_code} from {path}: {r.text[:200]}")
    r.raise_for_status()
    duration_s = time.monotonic() - t0
    # The remote ML service runs alongside vLLM on the AMD MI300X
    # droplet; attribute the wallclock to that hardware. Local-fallback
    # paths don't reach this function — they go straight to in-process
    # model loads in the specialist module, which we don't track.
    emissions.active().record_ml(
        endpoint=path,
        backend="riprap-models",
        hardware="amd_mi300x",
        duration_s=duration_s,
    )
    return r.json()


def _serialize_array(arr) -> str:
    """numpy/torch tensor → base64-encoded float32 raw bytes for transport.
    Each remote handler decodes to (shape, dtype=float32) and reconstructs.
    Reasonable round-trip for chips up to a few MB; large rasters should
    use compressed numpy-savez instead — TODO when a model needs > 8 MB."""
    import numpy as np
    np_arr = arr if isinstance(arr, np.ndarray) else _to_numpy(arr)
    np_arr = np_arr.astype("float32", copy=False)
    return base64.b64encode(np_arr.tobytes()).decode("ascii")


def _to_numpy(t):
    """Best-effort tensor → numpy. Accepts torch.Tensor or numpy already."""
    try:
        import torch
        if isinstance(t, torch.Tensor):
            return t.detach().cpu().numpy()
    except ImportError:
        pass
    import numpy as np
    return np.asarray(t)


def _deserialize_array(b64: str, shape: list[int]):
    """Inverse of _serialize_array — bytes → numpy float32 with given shape."""
    import numpy as np
    raw = base64.b64decode(b64)
    return np.frombuffer(raw, dtype="float32").reshape(shape)


# ---- Public router entry points -------------------------------------------

def healthcheck(timeout: float = 3.0) -> bool:
    """Quick reachability probe. True if the service responds 200 to GET
    /healthz within `timeout` seconds. Used by /api/backend so the UI can
    show whether the remote ML backend is currently live."""
    if not remote_enabled():
        return False
    try:
        with _client(timeout) as c:
            r = c.get("/healthz")
        return r.status_code == 200
    except Exception:
        return False


def backend_info() -> dict[str, Any]:
    """Snapshot for /api/backend — what the UI should advertise."""
    return {
        "backend": _BACKEND,
        "base_url": _BASE_URL or None,
        "remote_enabled": remote_enabled(),
        "reachable": healthcheck() if remote_enabled() else False,
    }


def prithvi_pluvial(s2_chip, *, scene_id: str | None = None,
                     scene_datetime: str | None = None,
                     cloud_cover: float | None = None,
                     timeout: float | None = None) -> dict[str, Any]:
    """Remote forward pass through Prithvi-NYC-Pluvial v2.
    Input: 6-band Sentinel-2 chip (numpy or torch, shape [6, H, W]).
    Output: { ok, pct_water_within_500m, pct_water_full, scene_id, ... }.
    Raises RemoteUnreachable if the service is down."""
    arr = _to_numpy(s2_chip)
    return _post("/v1/prithvi-pluvial", {
        "s2": _serialize_array(arr),
        "shape": list(arr.shape),
        "scene_id": scene_id,
        "scene_datetime": scene_datetime,
        "cloud_cover": cloud_cover,
    }, timeout=timeout)


def terramind(adapter: str, s2l2a=None, s1rtc=None, dem=None, *,
               timeout: float | None = None) -> dict[str, Any]:
    """Remote forward through TerraMind-NYC-Adapters (LULC or Buildings)
    or the v1 base generative path (synthesis). `adapter` is one of:
    lulc, buildings, synthesis. Each modality is a numpy array, torch
    tensor, or None — `synthesis` only needs DEM; the LoRA adapters
    need at minimum S2L2A."""
    payload: dict[str, Any] = {"adapter": adapter}
    if s2l2a is not None:
        s2_np = _to_numpy(s2l2a)
        payload["s2"] = _serialize_array(s2_np)
        payload["s2_shape"] = list(s2_np.shape)
    if s1rtc is not None:
        s1_np = _to_numpy(s1rtc)
        payload["s1"] = _serialize_array(s1_np)
        payload["s1_shape"] = list(s1_np.shape)
    if dem is not None:
        dem_np = _to_numpy(dem)
        payload["dem"] = _serialize_array(dem_np)
        payload["dem_shape"] = list(dem_np.shape)
    return _post("/v1/terramind", payload, timeout=timeout)


def ttm_forecast(model: str, history: Iterable[float], *,
                  context_length: int, prediction_length: int,
                  cadence: str = "h",
                  timeout: float | None = None) -> dict[str, Any]:
    """Remote Granite TTM r2 forecast.
    `model` is one of: zero_shot_battery, fine_tune_battery, weekly_311,
    floodnet_recurrence — the service decides which checkpoint to use.
    `history` is a 1-D iterable of floats (the time series); `cadence`
    is for the service's labelling (h / d / w / 6m). Output shape is
    `{ ok, forecast: [...], peak_index, peak_value }`."""
    series = list(map(float, history))
    return _post("/v1/ttm-forecast", {
        "model": model,
        "history": series,
        "context_length": context_length,
        "prediction_length": prediction_length,
        "cadence": cadence,
    }, timeout=timeout)


def granite_embed(texts: list[str], *,
                   timeout: float | None = None) -> dict[str, Any]:
    """Remote Granite Embedding 278M batch encode.
    Output: { ok, vectors: [[float, ...], ...] }. Vector dimension fixed
    at 768 (granite-embedding-278m-multilingual)."""
    return _post("/v1/granite-embed", {"texts": list(texts)}, timeout=timeout)


def gliner_extract(text: str, labels: list[str], *,
                    timeout: float | None = None) -> dict[str, Any]:
    """Remote GLiNER typed-entity extraction.
    Output: { ok, entities: [{label, text, start, end, score}, ...] }."""
    return _post("/v1/gliner-extract", {
        "text": text, "labels": list(labels),
    }, timeout=timeout)
