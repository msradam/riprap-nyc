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
            # prithvi_nyc_phase14.yaml uses GenericNonGeoSegmentationDataModule
            # which omits test_transform (→ None). IBM inference.py:run_model()
            # calls it on a 3D image dict; patch to match the IBM base contract.
            if getattr(getattr(m, 'datamodule', None),
                       'test_transform', None) is None:
                import albumentations as A
                import torch as _torch
                from albumentations.pytorch import ToTensorV2
                m.datamodule.test_transform = A.Compose([ToTensorV2()])
                _old = m.datamodule.aug

                # IBM's inference.py:188 calls
                # `datamodule.aug({'image': tensor})['image']` —
                # passing a dict and indexing the result. The previous
                # patch wrapped a kornia AugmentationSequential here,
                # which doesn't natively accept dict input and tripped
                # `'list' object has no attribute 'view'` deep inside
                # kornia's internal storage on first inference. Drop
                # kornia entirely and use a hand-rolled dict-aware
                # normalizer — fewer moving parts, identical math.
                class _DictNormalize:
                    def __init__(self, mean, std):
                        self.mean = _torch.as_tensor(mean).view(-1, 1, 1).float()
                        self.std = _torch.as_tensor(std).view(-1, 1, 1).float()

                    def __call__(self, sample):
                        if isinstance(sample, dict):
                            img = sample["image"]
                            mean = self.mean.to(img.device)
                            std = self.std.to(img.device)
                            return {**sample, "image": (img - mean) / std}
                        mean = self.mean.to(sample.device)
                        std = self.std.to(sample.device)
                        return (sample - mean) / std

                # `_old.means` / `_old.stds` come from the yaml as
                # Python lists — calling `.view()` on them is what
                # tripped the original `'list' object has no attribute
                # 'view'`. _DictNormalize handles the conversion via
                # torch.as_tensor internally; just pass the raw values
                # whatever their type.
                m.datamodule.aug = _DictNormalize(_old.means, _old.stds)
                log.info("prithvi: patched v2 datamodule transforms "
                         "for IBM inference.py compat (dict-aware Normalize)")
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
    m, _run_model = _load_prithvi()
    chip = _decode_array(payload.s2, payload.shape, "float32")
    # Sen1Floods11 expects [1, 6, 1, H, W]
    if chip.ndim == 3:
        chip = chip[None, :, None, :, :]
    elif chip.ndim == 4:
        chip = chip[:, :, None, :, :]   # (1, C, H, W) → (1, C, 1, H, W)

    # Bypass IBM's run_model entirely: it's a sliding-window helper
    # designed for full-scene inference, and its dependence on
    # datamodule.test_transform / datamodule.aug producing a specific
    # tensor shape kept tripping us up on the v2 fine-tune (yaml-typed
    # means / stds, dict-input vs tensor-input contract). Our chip is
    # already exactly model resolution and on-device — just normalise,
    # forward, argmax. Same math, no version-skew surface.
    import torch as _torch
    chip_t = _torch.from_numpy(chip).float()
    chip_t = _to_device(chip_t)

    # Means / stds from prithvi_nyc_phase14.yaml (the v2 training
    # config). Same six bands in the same order as the chip
    # (BLUE, GREEN, RED, NARROW_NIR, SWIR_1, SWIR_2).
    means_t = _torch.tensor(
        [0.107, 0.107, 0.115, 0.265, 0.235, 0.155],
        device=chip_t.device, dtype=chip_t.dtype,
    ).view(1, 6, 1, 1, 1)
    stds_t = _torch.tensor(
        [0.082, 0.075, 0.085, 0.115, 0.11, 0.1],
        device=chip_t.device, dtype=chip_t.dtype,
    ).view(1, 6, 1, 1, 1)
    x = (chip_t - means_t) / stds_t

    with _torch.no_grad():
        out = m.model(x)
        logits = out.output if hasattr(out, "output") else out

    # logits shape (B, num_classes, H, W) for segmentation. Argmax →
    # (B, H, W) class indices.
    pred = logits.argmax(dim=1).squeeze(0).cpu().numpy().astype("uint8")
    pct_full = float(100.0 * pred.mean())
    # Center-disk fraction (500 m at 10 m/px → 50 px radius from chip center).
    h, w = pred.shape
    yy, xx = np.indices(pred.shape)
    cy, cx = h // 2, w // 2
    dist = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    mask = dist <= min(50, min(h, w) // 4)
    pct_500m = float(100.0 * pred[mask].mean()) if mask.any() else pct_full
    # Pass the raw prediction raster back so HF can vectorise it into
    # GeoJSON for the map layer using the chip-georef it already has
    # locally (ref_da from _build_chip). uint8 is small enough for a
    # base64 round-trip (~50 KB at 224x224).
    pred_b64 = base64.b64encode(pred.tobytes()).decode("ascii")
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
        "pred_b64": pred_b64,
        "pred_shape": [int(h), int(w)],
    }


# ---- TerraMind (lulc / buildings / synthesis) -------------------------------

_TERRAMIND_REPO = "msradam/TerraMind-NYC-Adapters"
_TERRAMIND_SPECS = {
    "lulc":      {"subdir": "lulc_nyc",      "num_classes": 5,
                   "labels": ["Trees", "Cropland", "Built", "Bare", "Water"]},
    "buildings": {"subdir": "buildings_nyc", "num_classes": 2,
                   "labels": ["Background", "Building"]},
    # Synthesis is the IBM/NASA base TerraMind generative path
    # (DEM -> LULC), not a NYC fine-tune. Listed here so the same
    # /v1/terramind dispatch handles it.
    "synthesis": {"subdir": None, "num_classes": None,
                   "labels": ["Water", "Trees", "Grass", "Flooded vegetation",
                              "Crops", "Scrub/Shrub", "Built", "Bare ground",
                              "Snow/Ice", "Clouds"]},
}
_TERRAMIND_SYNTH_TIMESTEPS = int(os.environ.get(
    "RIPRAP_TERRAMIND_SYNTH_TIMESTEPS", "10"))


def _load_terramind_synthesis():
    """Load the IBM/NASA base TerraMind v1 generative path
    (DEM -> LULC) once. Different machinery from the LoRA adapters:
    pulled via terratorch's FULL_MODEL_REGISTRY rather than
    SemanticSegmentationTask + LoRA injection."""
    key = "terramind_synthesis"
    if key in _INSTANCES:
        return _INSTANCES[key]
    with _LOCKS.get(key, _LOCKS.get("terramind_lulc")):
        if key in _INSTANCES:
            return _INSTANCES[key]
        log.info("terramind/synthesis: cold load (v1 base generate)")
        import terratorch.models.backbones.terramind.model.terramind_register  # noqa
        from terratorch.registry import FULL_MODEL_REGISTRY
        m = FULL_MODEL_REGISTRY.build(
            "terratorch_terramind_v1_base_generate",
            modalities=["DEM"],
            output_modalities=["LULC"],
            pretrained=True,
            timesteps=_TERRAMIND_SYNTH_TIMESTEPS,
        )
        try:
            import torch
            if _DEVICE == "cuda" and torch.cuda.is_available():
                m = m.to("cuda")
        except Exception:
            log.exception("terramind/synthesis: cuda move failed")
        m.eval()
        _INSTANCES[key] = m
        log.info("terramind/synthesis: ready")
        return m


def _load_terramind(adapter: str):
    if adapter == "synthesis":
        return _load_terramind_synthesis()
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
    # All modality fields optional — `synthesis` adapter only needs DEM,
    # while lulc / buildings need at minimum S2L2A.
    s2: str | None = None
    s2_shape: list[int] | None = None
    s1: str | None = None
    s1_shape: list[int] | None = None
    dem: str | None = None
    dem_shape: list[int] | None = None


def _build_chip_tensor(np_arr, n_timesteps: int = 4):
    """Normalize any incoming chip shape into TerraMind's expected
    (B, C, T, H, W). The HF Space's eo_chip_cache hands us a chip that
    is already (B, C, T, H, W) 5-D — pass through. Older callers that
    send a single-timestep (C, H, W) get expanded to T=4 by repetition;
    a (C, T, H, W) gets just the batch dim added."""
    import torch
    t = torch.from_numpy(np_arr).float()
    if t.ndim == 5:
        return t                               # (B, C, T, H, W)
    if t.ndim == 4:
        return t.unsqueeze(0)                  # (C, T, H, W) -> (1, C, T, H, W)
    if t.ndim == 3:
        t = t.unsqueeze(1)                     # (C, H, W)    -> (C, 1, H, W)
        if t.shape[1] == 1:
            t = t.repeat(1, n_timesteps, 1, 1) # repeat single timestep
        return t.unsqueeze(0)                  # add batch dim
    raise ValueError(f"unexpected chip shape {tuple(t.shape)}")


def _terramind_synthesis_inference(payload: TerramindIn) -> dict[str, Any]:
    """DEM -> LULC generative path. Different machinery from the LoRA
    adapters: model is the v1 base generate stack pulled from
    terratorch's FULL_MODEL_REGISTRY, takes a single 4-D (B, 1, H, W)
    DEM tensor, and emits a class-logit raster keyed by the ESRI
    2020 LULC tokenizer codebook."""
    t0 = time.time()
    log.info("terramind/synthesis: payload dem=%s dem_shape=%s s2=%s",
             "set" if payload.dem else "None",
             payload.dem_shape,
             "set" if payload.s2 else "None")
    if not payload.dem or not payload.dem_shape:
        log.warning("terramind/synthesis: missing dem (dem=%s, shape=%s)",
                    bool(payload.dem), payload.dem_shape)
        raise HTTPException(status_code=400,
                            detail="synthesis requires `dem` + `dem_shape`")
    model = _load_terramind_synthesis()
    dem_np = _decode_array(payload.dem, payload.dem_shape)

    import numpy as np
    import torch
    dem_t = torch.from_numpy(dem_np).float()
    # The v1 base generative encoder unpacks `B, C, H, W = x.shape` —
    # 4-D required. DEM has C=1, so canonical shape is (1, 1, H, W).
    # Verified empirically against terratorch_terramind_v1_base_generate.
    if dem_t.ndim == 2:
        dem_t = dem_t.unsqueeze(0).unsqueeze(0)   # (H, W)    -> (1, 1, H, W)
    elif dem_t.ndim == 3:
        dem_t = dem_t.unsqueeze(0)                # (1, H, W) -> (1, 1, H, W)
    elif dem_t.ndim != 4:
        raise HTTPException(status_code=400,
                            detail=f"unexpected DEM shape {tuple(dem_t.shape)}; "
                                   f"expected 4-D (B, C, H, W)")
    dem_t = _to_device(dem_t)

    spec = _TERRAMIND_SPECS["synthesis"]
    with torch.no_grad():
        out = model({"DEM": dem_t},
                    timesteps=_TERRAMIND_SYNTH_TIMESTEPS,
                    verbose=False)
    lulc = out["LULC"]
    if hasattr(lulc, "detach"):
        lulc = lulc.detach().cpu().numpy()
    if lulc.ndim == 4:
        lulc = lulc[0]                      # (n_classes, H, W)
    class_idx = lulc.argmax(axis=0)         # (H, W) per-pixel class
    unique, counts = np.unique(class_idx, return_counts=True)
    total = float(class_idx.size) or 1.0
    fractions: dict[str, float] = {}
    for u, c in zip(unique, counts):
        u = int(u)
        label = spec["labels"][u] if 0 <= u < len(spec["labels"]) else f"class_{u}"
        fractions[label] = round(100.0 * c / total, 2)
    ordered = dict(sorted(fractions.items(),
                           key=lambda kv: kv[1], reverse=True))
    dominant_class = next(iter(ordered)) if ordered else "unknown"
    dominant_pct = ordered.get(dominant_class, 0.0)
    pred_u8 = class_idx.astype("uint8")
    pred_b64 = base64.b64encode(pred_u8.tobytes()).decode("ascii")
    return {
        "ok": True,
        "adapter": "synthesis",
        "elapsed_s": round(time.time() - t0, 2),
        "device": _DEVICE,
        "synthetic_modality": True,
        "tim_chain": ["DEM", "LULC_synthetic"],
        "diffusion_steps": _TERRAMIND_SYNTH_TIMESTEPS,
        "class_fractions": ordered,
        "dominant_class": dominant_class,
        "dominant_pct": dominant_pct,
        "n_classes_observed": len(ordered),
        "shape": list(lulc.shape),
        "n_pixels": int(class_idx.size),
        "label_schema": "ESRI 2020-2022 Land Cover (tentative — TerraMind "
                         "tokenizer source confirms ESRI but not exact "
                         "label-to-index mapping)",
        "pred_b64": pred_b64,
        "pred_shape": [int(s) for s in pred_u8.shape],
        "class_labels": _TERRAMIND_SPECS["synthesis"]["labels"],
    }


def _terramind_inference(payload: TerramindIn) -> dict[str, Any]:
    if payload.adapter not in _TERRAMIND_SPECS:
        raise HTTPException(status_code=400,
                            detail=f"unknown adapter {payload.adapter!r}")
    if payload.adapter == "synthesis":
        return _terramind_synthesis_inference(payload)
    t0 = time.time()
    task = _load_terramind(payload.adapter)
    spec = _TERRAMIND_SPECS[payload.adapter]

    if not payload.s2 or not payload.s2_shape:
        raise HTTPException(status_code=400,
                            detail=f"adapter {payload.adapter!r} requires "
                                   f"`s2` + `s2_shape`")
    s2 = _decode_array(payload.s2, payload.s2_shape)
    chips = {"S2L2A": _to_device(_build_chip_tensor(s2))}
    if payload.s1 and payload.s1_shape:
        s1 = _decode_array(payload.s1, payload.s1_shape)
        chips["S1RTC"] = _to_device(_build_chip_tensor(s1))
    if payload.dem and payload.dem_shape:
        dem = _decode_array(payload.dem, payload.dem_shape)
        chips["DEM"] = _to_device(_build_chip_tensor(dem))

    import torch

    def _forward(x):
        out = task.model(x)
        return out.output if hasattr(out, "output") else out

    # Call the model directly — same shape contract as the
    # training-time inference at
    # experiments/18_terramind_nyc_lora/shared/inference_ensemble.py:
    # the canonical chip is already the model's native 224×224 input
    # in (B, C, T, H, W) form, so terratorch's `tiled_inference` is
    # unnecessary and was the cause of the "Expected size 12 but got
    # size 2" 5-D handling regression we hit on the L4 deploy.
    # Tile only when the chip is bigger than the model resolution.
    s2_t = chips["S2L2A"]
    h_chip, w_chip = int(s2_t.shape[-2]), int(s2_t.shape[-1])
    with torch.no_grad():
        if h_chip == 224 and w_chip == 224:
            logits = _forward(chips)
        else:
            from terratorch.tasks.tiled_inference import tiled_inference

            def _forward_tile(x, **_extra):
                return _forward(x)

            logits = tiled_inference(
                _forward_tile, chips, out_channels=spec["num_classes"],
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

    # Buildings: connected-component count (parity with local
    # _summarize_buildings). The card subhead reads this — without it,
    # the UI shows "0 distinct components".
    n_components = None
    if payload.adapter == "buildings":
        try:
            from scipy.ndimage import label
            _, n_components = label((pred == 1).astype("uint8"))
            n_components = int(n_components)
        except Exception:
            log.debug("terramind/buildings: scipy.ndimage unavailable")

    # Pass the per-pixel argmax raster back so HF can vectorise it.
    pred_b64 = base64.b64encode(pred.tobytes()).decode("ascii")
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
        # Buildings-specific stat (None when not the buildings adapter).
        "pct_buildings": round(100.0 * float((pred == 1).sum()) / n, 2)
                         if payload.adapter == "buildings" else None,
        "n_building_components": n_components,
        "pred_b64": pred_b64,
        "pred_shape": [int(s) for s in pred.shape],
        "class_labels": spec["labels"],
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

# Last error per route, kept on the in-memory map so /v1/diag can
# expose it without forcing the operator to grep container logs.
_LAST_ERR: dict[str, dict[str, Any]] = {}


def _safe_route(stage: str, fn, payload):
    """Wrap a route body so an uncaught exception becomes a structured
    `{"ok": False, "err": "...", "stage": "..."}` JSON response with
    HTTP 200 instead of FastAPI's opaque "Internal Server Error" body.

    The proxy on :7860 forwards this body untouched, so the FSM
    specialist surfaces the real reason in the trace card. Logs the
    full traceback to stderr so operators can still root-cause from
    the Space's runtime logs."""
    try:
        return fn(payload)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        import traceback
        tb = traceback.format_exc()
        log.error("route %s failed: %s\n%s", stage, e, tb)
        info = {
            "ok": False,
            "err": f"{type(e).__name__}: {e}",
            "stage": stage,
            "ts": time.time(),
        }
        _LAST_ERR[stage] = {**info, "traceback_tail": tb.splitlines()[-3:]}
        return info


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log.info("riprap-models starting on device=%s auth=%s",
             _DEVICE, "yes" if _AUTH_TOKEN else "no")
    # Pre-load the heavy models so the first user request doesn't
    # collide with a cold-load on the same GPU as vLLM. Each warm
    # is best-effort: a single model failing must not block the
    # service from starting (others may still serve).
    if os.environ.get("RIPRAP_MODELS_WARM_AT_STARTUP", "1").lower() in ("1", "true", "yes"):
        for stage, fn in (
            ("warm/prithvi", _load_prithvi),
            ("warm/terramind_synthesis", _load_terramind_synthesis),
            ("warm/terramind_lulc", lambda: _load_terramind("lulc")),
            ("warm/terramind_buildings", lambda: _load_terramind("buildings")),
            ("warm/embed", _load_embed),
            ("warm/gliner", _load_gliner),
        ):
            try:
                fn()
                log.info("startup %s ok", stage)
            except Exception as e:  # noqa: BLE001
                import traceback
                tb = traceback.format_exc()
                log.exception("startup %s failed: %s", stage, e)
                _LAST_ERR[stage] = {
                    "ok": False,
                    "err": f"{type(e).__name__}: {e}",
                    "stage": stage,
                    "traceback_tail": tb.splitlines()[-5:],
                }
    yield
    log.info("riprap-models stopping")


app = FastAPI(title="riprap-models", version="0.5.1", lifespan=lifespan)


@app.get("/healthz")
def healthz():
    return {"ok": True, "device": _DEVICE,
             "models_loaded": sorted(_INSTANCES.keys()),
             "last_errors": _LAST_ERR}


@app.get("/v1/diag", dependencies=[Depends(_require_auth)])
def diag():
    """Operator-only diagnostic snapshot — what's loaded, last
    per-stage error (with a 3-line traceback tail), and CUDA
    visibility. The proxy forwards this through the catch-all so
    operators can hit it from outside the Space."""
    cuda = {"available": False, "devices": []}
    try:
        import torch
        cuda["available"] = bool(torch.cuda.is_available())
        if cuda["available"]:
            cuda["devices"] = [{
                "name": torch.cuda.get_device_name(i),
                "mem_total_mb": torch.cuda.get_device_properties(i).total_memory // (1024 * 1024),
                "mem_alloc_mb": torch.cuda.memory_allocated(i) // (1024 * 1024),
            } for i in range(torch.cuda.device_count())]
    except Exception as e:  # noqa: BLE001
        cuda["err"] = f"{type(e).__name__}: {e}"
    return {
        "device": _DEVICE,
        "models_loaded": sorted(_INSTANCES.keys()),
        "last_errors": _LAST_ERR,
        "cuda": cuda,
    }


@app.post("/v1/prithvi-pluvial", dependencies=[Depends(_require_auth)])
def prithvi_pluvial_route(payload: PrithviIn):
    return _safe_route("prithvi-pluvial", _prithvi_pluvial, payload)


@app.post("/v1/terramind", dependencies=[Depends(_require_auth)])
def terramind_route(payload: TerramindIn):
    return _safe_route(f"terramind/{payload.adapter}",
                       _terramind_inference, payload)


@app.post("/v1/ttm-forecast", dependencies=[Depends(_require_auth)])
def ttm_forecast_route(payload: TtmIn):
    return _safe_route("ttm-forecast", _ttm_forecast, payload)


@app.post("/v1/granite-embed", dependencies=[Depends(_require_auth)])
def granite_embed_route(payload: EmbedIn):
    return _safe_route("granite-embed", _granite_embed, payload)


@app.post("/v1/gliner-extract", dependencies=[Depends(_require_auth)])
def gliner_extract_route(payload: GlinerIn):
    return _safe_route("gliner-extract", _gliner_extract, payload)
