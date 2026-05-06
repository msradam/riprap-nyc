"""Riprap Models — GPU inference microservice.

Runs on the AMD MI300X droplet alongside vLLM, exposes one HTTP
endpoint per model class consumed by the Riprap FastAPI app's
specialists. The local app routes through this service when
RIPRAP_ML_BACKEND=remote (or =auto with the service reachable),
keeping all GPU-accelerable forward passes on the MI300X — Granite
4.1 (LLM), Prithvi-NYC-Pluvial (segmentation), TerraMind LULC +
Buildings + Synthesis (LoRA), Granite TTM r2 (forecasts), Granite
Embedding 278M (RAG), and GLiNER (typed extraction).

Authoritative bearer-token auth same as vLLM. Same env-var shape so
the same secret can be reused across both services on a Space.

Service contract (mirrors app/inference.py):

  GET   /healthz                        → {ok: true, models_loaded: [...]}
  POST  /v1/prithvi-pluvial             → see _prithvi_pluvial below
  POST  /v1/terramind                   → adapter dispatch (lulc/buildings/synth)
  POST  /v1/ttm-forecast                → model dispatch (zero_shot_battery, ...)
  POST  /v1/granite-embed               → batch text → 768-d vectors
  POST  /v1/gliner-extract              → text + labels → typed entities

Model loading is lazy + cached per-process. The first call to a given
model pays the cold-load cost (~5-30 s); subsequent calls reuse the
in-memory instance. ROCm device binding goes through torch's CUDA
shim — `cuda` is the ROCm device when running on a ROCm-built torch.
"""
from __future__ import annotations

import base64
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

log = logging.getLogger("riprap.models")
logging.basicConfig(
    level=os.environ.get("RIPRAP_MODELS_LOG", "INFO").upper(),
    format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
)

# Auth — same shape as vLLM. Set RIPRAP_MODELS_API_KEY in the
# `docker run` env. When empty, the service runs unauthenticated
# (only sane for localhost-only deployments).
_AUTH_TOKEN = os.environ.get("RIPRAP_MODELS_API_KEY", "")

# Device. ROCm-built torch reports CUDA-style symbols; "cuda" maps to
# the first ROCm device on the MI300X.
_DEVICE = os.environ.get("RIPRAP_MODELS_DEVICE", "cuda")


def _require_auth(authorization: str | None = Header(default=None)) -> None:
    if not _AUTH_TOKEN:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if authorization[7:].strip() != _AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid bearer token")


# ---- Lazy model singletons --------------------------------------------------
#
# Each model has a `_load_<name>()` that returns the in-memory instance
# (locking on a per-model threading.Lock so concurrent first-call
# requests don't double-load). Callers grab via `_get_<name>()`.

_LOCKS = {
    "prithvi": threading.Lock(),
    "terramind_lulc": threading.Lock(),
    "terramind_buildings": threading.Lock(),
    "terramind_synth": threading.Lock(),
    "ttm": threading.Lock(),
    "granite_embed": threading.Lock(),
    "gliner": threading.Lock(),
}
_INSTANCES: dict[str, Any] = {}


def _decode_array(b64: str, shape: list[int], dtype: str = "float32") -> np.ndarray:
    raw = base64.b64decode(b64)
    return np.frombuffer(raw, dtype=dtype).reshape(shape)


def _to_device(t):
    """Move a torch tensor to the configured device. No-op for CPU."""
    if _DEVICE == "cpu":
        return t
    try:
        import torch
        if torch.cuda.is_available():
            return t.to("cuda")
    except Exception as e:
        log.warning("device move skipped: %s", e)
    return t


# ---- Prithvi-NYC-Pluvial v2 -------------------------------------------------

def _load_prithvi():
    if "prithvi" in _INSTANCES:
        return _INSTANCES["prithvi"]
    with _LOCKS["prithvi"]:
        if "prithvi" in _INSTANCES:
            return _INSTANCES["prithvi"]
        log.info("prithvi: cold load (msradam/Prithvi-EO-2.0-NYC-Pluvial)")
        import importlib.util

        from huggingface_hub import hf_hub_download
        from terratorch.cli_tools import LightningInferenceModel

        BASE_REPO = "ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11"
        V2_REPO = "msradam/Prithvi-EO-2.0-NYC-Pluvial"

        # Use the IBM-NASA base config + v2 ckpt. Mirrors
        # app/flood_layers/prithvi_live.py:_ensure_model().
        base_config = hf_hub_download(BASE_REPO, "config.yaml")
        inference_py = hf_hub_download(BASE_REPO, "inference.py")

        v2_yaml = None
        v2_ckpt = None
        for name in ("prithvi_nyc_phase14.yaml", "config.yaml"):
            try:
                v2_yaml = hf_hub_download(V2_REPO, name); break
            except Exception:
                continue
        for name in ("prithvi_nyc_pluvial_v2.ckpt", "best_val_loss.ckpt", "model.ckpt"):
            try:
                v2_ckpt = hf_hub_download(V2_REPO, name); break
            except Exception:
                continue
        if v2_yaml and v2_ckpt:
            log.info("prithvi: building from v2 yaml=%s ckpt=%s", v2_yaml, v2_ckpt)
            m = LightningInferenceModel.from_config(v2_yaml, v2_ckpt)
        else:
            log.info("prithvi: v2 unavailable, falling back to base")
            base_ckpt = hf_hub_download(
                BASE_REPO, "Prithvi-EO-V2-300M-TL-Sen1Floods11.pt")
            m = LightningInferenceModel.from_config(base_config, base_ckpt)
        m.model.eval()
        try:
            import torch
            if _DEVICE == "cuda" and torch.cuda.is_available():
                m.model.cuda()
        except Exception:
            log.exception("prithvi: cuda move failed; staying on cpu")

        spec = importlib.util.spec_from_file_location("_prithvi_inference",
                                                       inference_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _INSTANCES["prithvi"] = (m, mod.run_model)
        log.info("prithvi: ready")
        return _INSTANCES["prithvi"]


class PrithviIn(BaseModel):
    s2: str
    shape: list[int]
    scene_id: str | None = None
    scene_datetime: str | None = None
    cloud_cover: float | None = None


def _prithvi_pluvial(payload: PrithviIn) -> dict[str, Any]:
    t0 = time.time()
    m, run_model = _load_prithvi()
    chip = _decode_array(payload.s2, payload.shape, "float32")
    # Sen1Floods11 expects [1, 6, 1, H, W]
    if chip.ndim == 3:
        chip = chip[None, :, None, :, :]
    pred_t = run_model(chip, None, None, m.model, m.datamodule, chip.shape[-1])
    pred = pred_t[0].cpu().numpy().astype("uint8")
    pct_full = float(100.0 * pred.mean())
    # Center-disk fraction (500 m at 10 m/px → 50 px radius from chip center).
    h, w = pred.shape
    yy, xx = np.indices(pred.shape)
    cy, cx = h // 2, w // 2
    dist = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    mask = dist <= min(50, min(h, w) // 4)
    pct_500m = float(100.0 * pred[mask].mean()) if mask.any() else pct_full
    return {
        "ok": True,
        "elapsed_s": round(time.time() - t0, 2),
        "device": _DEVICE,
        "pct_water_within_500m": round(pct_500m, 3),
        "pct_water_full": round(pct_full, 3),
        "scene_id": payload.scene_id,
        "scene_datetime": payload.scene_datetime,
        "cloud_cover": payload.cloud_cover,
        "shape": [int(h), int(w)],
    }


# ---- TerraMind (lulc / buildings / synthesis) -------------------------------

_TERRAMIND_REPO = "msradam/TerraMind-NYC-Adapters"
_TERRAMIND_SPECS = {
    "lulc":      {"subdir": "lulc_nyc",      "num_classes": 5,
                   "labels": ["Trees", "Cropland", "Built", "Bare", "Water"]},
    "buildings": {"subdir": "buildings_nyc", "num_classes": 2,
                   "labels": ["Background", "Building"]},
}


def _load_terramind(adapter: str):
    key = f"terramind_{adapter}"
    if key in _INSTANCES:
        return _INSTANCES[key]
    with _LOCKS.get(key, _LOCKS.get("terramind_lulc")):
        if key in _INSTANCES:
            return _INSTANCES[key]
        log.info("terramind/%s: cold load", adapter)
        from huggingface_hub import snapshot_download
        from peft import LoraConfig, inject_adapter_in_model
        from safetensors.torch import load_file
        from terratorch.tasks import SemanticSegmentationTask

        spec = _TERRAMIND_SPECS[adapter]
        adapter_root = snapshot_download(
            _TERRAMIND_REPO, allow_patterns=[f"{spec['subdir']}/*"])
        task = SemanticSegmentationTask(
            model_factory="EncoderDecoderFactory",
            model_args=dict(
                backbone="terramind_v1_base",
                backbone_pretrained=True,
                backbone_modalities=["S2L2A", "S1RTC", "DEM"],
                backbone_use_temporal=True,
                backbone_temporal_pooling="concat",
                backbone_temporal_n_timestamps=4,
                necks=[
                    {"name": "SelectIndices", "indices": [2, 5, 8, 11]},
                    {"name": "ReshapeTokensToImage", "remove_cls_token": False},
                    {"name": "LearnedInterpolateToPyramidal"},
                ],
                decoder="UNetDecoder",
                decoder_channels=[512, 256, 128, 64],
                head_dropout=0.1,
                num_classes=spec["num_classes"],
            ),
            loss="ce", lr=1e-4, freeze_backbone=False, freeze_decoder=False,
        )
        inject_adapter_in_model(LoraConfig(
            r=16, lora_alpha=32, lora_dropout=0.05,
            target_modules=["attn.qkv", "attn.proj"], bias="none",
        ), task.model.encoder)
        adapter_dir = f"{adapter_root}/{spec['subdir']}"
        lora = load_file(f"{adapter_dir}/adapter_model.safetensors")
        head = load_file(f"{adapter_dir}/decoder_head.safetensors")
        task.model.encoder.load_state_dict(
            {k.removeprefix("encoder."): v for k, v in lora.items()
             if k.startswith("encoder.")}, strict=False)
        for sub in ("decoder", "neck", "head", "aux_heads"):
            ss = {k[len(sub) + 1:]: v for k, v in head.items()
                   if k.startswith(sub + ".")}
            if ss and hasattr(task.model, sub):
                getattr(task.model, sub).load_state_dict(ss, strict=False)
        try:
            import torch
            if _DEVICE == "cuda" and torch.cuda.is_available():
                task = task.to("cuda")
        except Exception:
            log.exception("terramind: cuda move failed")
        task.eval()
        _INSTANCES[key] = task
        log.info("terramind/%s: ready", adapter)
        return task


class TerramindIn(BaseModel):
    adapter: str  # "lulc" | "buildings" | "synthesis"
    s2: str
    s2_shape: list[int]
    s1: str | None = None
    s1_shape: list[int] | None = None
    dem: str | None = None
    dem_shape: list[int] | None = None


def _build_chip_tensor(np_arr, n_timesteps: int = 4):
    import torch
    t = torch.from_numpy(np_arr).float().unsqueeze(1)  # add T dim
    if t.shape[1] == 1:
        t = t.repeat(1, n_timesteps, 1, 1)
    return t.unsqueeze(0)  # add batch


def _terramind_inference(payload: TerramindIn) -> dict[str, Any]:
    t0 = time.time()
    if payload.adapter not in _TERRAMIND_SPECS:
        raise HTTPException(status_code=400,
                            detail=f"unknown adapter {payload.adapter!r}")
    task = _load_terramind(payload.adapter)
    spec = _TERRAMIND_SPECS[payload.adapter]

    s2 = _decode_array(payload.s2, payload.s2_shape)
    chips = {"S2L2A": _to_device(_build_chip_tensor(s2))}
    if payload.s1 and payload.s1_shape:
        s1 = _decode_array(payload.s1, payload.s1_shape)
        chips["S1RTC"] = _to_device(_build_chip_tensor(s1))
    if payload.dem and payload.dem_shape:
        dem = _decode_array(payload.dem, payload.dem_shape)
        chips["DEM"] = _to_device(_build_chip_tensor(dem))

    import torch
    from terratorch.tasks.tiled_inference import tiled_inference

    def _forward(x, **_extra):
        out = task.model(x)
        return out.output if hasattr(out, "output") else out
    with torch.no_grad():
        logits = tiled_inference(
            _forward, chips, out_channels=spec["num_classes"],
            h_crop=224, w_crop=224, h_stride=128, w_stride=128,
            average_patches=True, blend_overlaps=True, padding="reflect",
        )
    pred = logits.argmax(dim=1).squeeze(0).cpu().numpy().astype("uint8")
    n = max(int(pred.size), 1)
    fractions = {
        spec["labels"][i]: round(100.0 * float((pred == i).sum()) / n, 2)
        for i in range(spec["num_classes"])
    }
    fractions = {k: v for k, v in fractions.items() if v > 0}
    dom_idx = int(max(range(spec["num_classes"]),
                      key=lambda i: int((pred == i).sum())))
    return {
        "ok": True,
        "adapter": payload.adapter,
        "elapsed_s": round(time.time() - t0, 2),
        "device": _DEVICE,
        "shape": list(pred.shape),
        "n_pixels": int(pred.size),
        "class_fractions": fractions,
        "dominant_class": spec["labels"][dom_idx],
        "dominant_pct": fractions.get(spec["labels"][dom_idx], 0.0),
        # Buildings-specific stat (NaN-safe; 0 when not the buildings adapter).
        "pct_buildings": round(100.0 * float((pred == 1).sum()) / n, 2)
                         if payload.adapter == "buildings" else None,
    }


# ---- Granite TTM r2 ---------------------------------------------------------

_TTM_MODELS = {
    "zero_shot_battery": "ibm-granite/granite-timeseries-ttm-r2",
    "fine_tune_battery": "msradam/Granite-TTM-r2-Battery-Surge",
    "weekly_311":        "ibm-granite/granite-timeseries-ttm-r2",
    "floodnet_recurrence": "ibm-granite/granite-timeseries-ttm-r2",
}


def _load_ttm(model_key: str):
    key = f"ttm:{model_key}"
    if key in _INSTANCES:
        return _INSTANCES[key]
    with _LOCKS["ttm"]:
        if key in _INSTANCES:
            return _INSTANCES[key]
        log.info("ttm/%s: cold load", model_key)
        if model_key == "fine_tune_battery":
            from huggingface_hub import snapshot_download
            from tsfm_public import TinyTimeMixerForPrediction
            local_dir = snapshot_download(_TTM_MODELS[model_key])
            m = TinyTimeMixerForPrediction.from_pretrained(local_dir).eval()
        else:
            from tsfm_public.toolkit.get_model import get_model
            # Caller passes (context_length, prediction_length) — for the
            # zero-shot & 311 & FloodNet specialists we let the toolkit
            # pick the best matching pretrained config. Cache one per
            # model_key to avoid duplicate loads.
            m = get_model(_TTM_MODELS[model_key],
                          context_length=512, prediction_length=96).eval()
        try:
            import torch
            if _DEVICE == "cuda" and torch.cuda.is_available():
                m = m.to("cuda")
        except Exception:
            log.exception("ttm: cuda move failed")
        _INSTANCES[key] = m
        log.info("ttm/%s: ready", model_key)
        return m


class TtmIn(BaseModel):
    model: str   # zero_shot_battery | fine_tune_battery | weekly_311 | floodnet_recurrence
    history: list[float]
    context_length: int
    prediction_length: int
    cadence: str = "h"


def _ttm_forecast(payload: TtmIn) -> dict[str, Any]:
    t0 = time.time()
    if payload.model not in _TTM_MODELS:
        raise HTTPException(status_code=400,
                            detail=f"unknown model {payload.model!r}")
    m = _load_ttm(payload.model)
    import torch
    series = np.array(payload.history, dtype="float32")
    if len(series) < payload.context_length:
        # Front-pad with the leading value so the model gets the right
        # shape — caller-side fills are NaN-clean already, so this only
        # extends a series whose history is shorter than context.
        pad = np.full(payload.context_length - len(series), series[0]
                      if len(series) else 0.0, dtype="float32")
        series = np.concatenate([pad, series])
    series = series[-payload.context_length:]
    x = torch.from_numpy(series).float().unsqueeze(0).unsqueeze(-1)
    x = _to_device(x)
    with torch.no_grad():
        out = m(past_values=x)
    fc = out.prediction_outputs.squeeze(-1).squeeze(0).cpu().numpy()
    peak_idx = int(np.argmax(np.abs(fc)))
    return {
        "ok": True,
        "model": payload.model,
        "elapsed_s": round(time.time() - t0, 2),
        "device": _DEVICE,
        "context_length": payload.context_length,
        "prediction_length": payload.prediction_length,
        "cadence": payload.cadence,
        "forecast": [round(float(v), 6) for v in fc.tolist()],
        "peak_index": peak_idx,
        "peak_value": round(float(fc[peak_idx]), 6),
    }


# ---- Granite Embedding 278M -------------------------------------------------

_EMBED_REPO = "ibm-granite/granite-embedding-278m-multilingual"


def _load_embed():
    if "granite_embed" in _INSTANCES:
        return _INSTANCES["granite_embed"]
    with _LOCKS["granite_embed"]:
        if "granite_embed" in _INSTANCES:
            return _INSTANCES["granite_embed"]
        log.info("granite-embed: cold load")
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(_EMBED_REPO,
                                 device="cuda" if _DEVICE == "cuda" else "cpu")
        _INSTANCES["granite_embed"] = m
        log.info("granite-embed: ready")
        return m


class EmbedIn(BaseModel):
    texts: list[str]


def _granite_embed(payload: EmbedIn) -> dict[str, Any]:
    t0 = time.time()
    m = _load_embed()
    vecs = m.encode(payload.texts, normalize_embeddings=True,
                     show_progress_bar=False)
    return {
        "ok": True,
        "elapsed_s": round(time.time() - t0, 2),
        "device": _DEVICE,
        "n": len(payload.texts),
        "dim": int(vecs.shape[-1]) if hasattr(vecs, "shape") else len(vecs[0]),
        "vectors": [list(map(float, v)) for v in vecs],
    }


# ---- GLiNER ----------------------------------------------------------------

_GLINER_REPO = "urchade/gliner_medium-v2.1"


def _load_gliner():
    if "gliner" in _INSTANCES:
        return _INSTANCES["gliner"]
    with _LOCKS["gliner"]:
        if "gliner" in _INSTANCES:
            return _INSTANCES["gliner"]
        log.info("gliner: cold load")
        from gliner import GLiNER
        m = GLiNER.from_pretrained(_GLINER_REPO)
        try:
            import torch
            if _DEVICE == "cuda" and torch.cuda.is_available():
                m = m.to("cuda")
        except Exception:
            log.exception("gliner: cuda move failed")
        _INSTANCES["gliner"] = m
        log.info("gliner: ready")
        return m


class GlinerIn(BaseModel):
    text: str
    labels: list[str]


def _gliner_extract(payload: GlinerIn) -> dict[str, Any]:
    t0 = time.time()
    m = _load_gliner()
    ents = m.predict_entities(payload.text, payload.labels)
    return {
        "ok": True,
        "elapsed_s": round(time.time() - t0, 2),
        "device": _DEVICE,
        "entities": [
            {"label": e["label"], "text": e["text"],
             "start": int(e.get("start", 0)), "end": int(e.get("end", 0)),
             "score": float(e.get("score", 0))}
            for e in ents
        ],
    }


# ---- FastAPI app ------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    log.info("riprap-models starting on device=%s auth=%s",
             _DEVICE, "yes" if _AUTH_TOKEN else "no")
    yield
    log.info("riprap-models stopping")


app = FastAPI(title="riprap-models", version="0.4.5", lifespan=lifespan)


@app.get("/healthz")
def healthz():
    return {"ok": True, "device": _DEVICE,
             "models_loaded": sorted(_INSTANCES.keys())}


@app.post("/v1/prithvi-pluvial", dependencies=[Depends(_require_auth)])
def prithvi_pluvial_route(payload: PrithviIn):
    return _prithvi_pluvial(payload)


@app.post("/v1/terramind", dependencies=[Depends(_require_auth)])
def terramind_route(payload: TerramindIn):
    return _terramind_inference(payload)


@app.post("/v1/ttm-forecast", dependencies=[Depends(_require_auth)])
def ttm_forecast_route(payload: TtmIn):
    return _ttm_forecast(payload)


@app.post("/v1/granite-embed", dependencies=[Depends(_require_auth)])
def granite_embed_route(payload: EmbedIn):
    return _granite_embed(payload)


@app.post("/v1/gliner-extract", dependencies=[Depends(_require_auth)])
def gliner_extract_route(payload: GlinerIn):
    return _gliner_extract(payload)
