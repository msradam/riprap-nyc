"""TerraMind-NYC adapters — LULC and Buildings inference for NYC chips.

Wraps the Apache-2.0 [`msradam/TerraMind-NYC-Adapters`](https://huggingface.co/msradam/TerraMind-NYC-Adapters)
LoRA family fine-tuned on NYC EO chips (Sentinel-2 L2A + Sentinel-1 RTC
+ Copernicus DEM, temporal stack of 4) on AMD MI300X via AMD Developer
Cloud. Exposes two specialist entry points:

    lulc(s2l2a, s1rtc, dem)       -> 5-class macro NYC LULC mask
    buildings(s2l2a, s1rtc, dem)  -> binary NYC building footprint mask

The base TerraMind 1.0 weights are downloaded by terratorch on first
call; the LoRA adapter + UNet decoder weights come from the HF repo and
are cached to `~/.cache/huggingface/hub`.

CHIP-SIZE TRAP. TerraMind's positional embeddings don't generalise off
its training resolution (224×224). Calling `task.model({...})` on a
chip ≠ 224×224 produces silent garbage. We therefore wrap inference
with `terratorch.tasks.tiled_inference.tiled_inference`, which slides
a 224×224 crop window across the chip and stitches per-window logits.
This matches the patch in
`experiments/18_terramind_nyc_lora/shared/inference_ensemble.py` that
the plan flags as required for production.

Gated by RIPRAP_TERRAMIND_NYC_ENABLE — deployments without the deps
installed (HF Spaces' Py3.10 cone, plain Ollama dev VMs) silently no-op
through the same skipped-result shape every other heavy specialist
emits.

This module does NOT fetch its own S2/S1/DEM chips. C4 wires it into
the FSM with a shared chip cache so the LULC and Buildings calls
don't each refetch ~150 MB of imagery.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

log = logging.getLogger("riprap.terramind_nyc")

ENABLE = os.environ.get("RIPRAP_TERRAMIND_NYC_ENABLE", "1").lower() in ("1", "true", "yes")
DEVICE = os.environ.get("RIPRAP_TERRAMIND_NYC_DEVICE", "cpu")
ADAPTERS_REPO = "msradam/TerraMind-NYC-Adapters"

# Per-task config knobs the HF README's quick-start fixes for these
# adapters. Mirrored from experiments/18_terramind_nyc_lora/adapters/*/
# config.yaml so a single source of truth lives next to the inference
# code rather than being scraped from YAML at runtime.
ADAPTER_SPECS: dict[str, dict[str, Any]] = {
    "lulc": {
        "subdir": "lulc_nyc",
        "num_classes": 5,
        "class_labels": [
            "Trees / vegetation",
            "Cropland",
            "Built / impervious",
            "Bare ground",
            "Water",
        ],
    },
    "buildings": {
        "subdir": "buildings_nyc",
        "num_classes": 2,
        # The decoder emits class 0 = background, class 1 = building.
        "class_labels": ["Background", "Building footprint"],
    },
}

# Tile-window size — TerraMind's training resolution. Stride < window
# yields overlap (smooths seams from window-boundary classification
# noise); 96 px overlap matches the experiments/18 ensemble.
TILE_SIZE = 224
TILE_STRIDE = 128

# One-shot lazy-init guards. The base TerraMind weights are heavy
# (~1.6 GB) and we want to load them once across LULC and Buildings.
_INIT_LOCK = threading.Lock()
_BASE_LOADED = False
_ADAPTERS: dict[str, Any] = {}  # name -> built terratorch task on DEVICE


def _has_required_deps() -> tuple[bool, str | None]:
    """Probe the heavy-EO deps. Same shape as prithvi_live's check —
    a missing dep (terratorch / peft / safetensors / hf_hub) returns a
    clean `skipped: deps_unavailable` outcome instead of a noisy
    ModuleNotFoundError in the trace.

    On the HF Space, terratorch's import chain itself can raise
    RuntimeError("operator torchvision::nms does not exist") when the
    torchvision binary extension can't load against our CPU torch
    wheel. Treat that as 'unavailable' too — the local inference path
    is dead-on-arrival there."""
    missing: list[str] = []
    for name in ("terratorch", "peft", "safetensors", "huggingface_hub",
                 "torch", "yaml"):
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
        except Exception as e:
            # torchvision::nms RuntimeError, libcuda load failure, etc.
            log.warning("terramind_nyc: %s import raised %s; treating as "
                        "unavailable", name, type(e).__name__)
            missing.append(f"{name} ({type(e).__name__})")
    if missing:
        return False, ", ".join(missing)
    return True, None


_DEPS_OK, _DEPS_MISSING = _has_required_deps()


def _ensure_adapter(adapter_name: str):
    """Build the terratorch SemanticSegmentationTask, inject the LoRA
    scaffold, load the published Δ + decoder weights, return the task.

    Per-task tasks share the TerraMind base inside terratorch's model
    factory — calling SemanticSegmentationTask twice loads the base
    twice in fp32 (~3.3 GB resident on CPU). For a two-task family this
    is acceptable; we don't need the cross-task weight sharing the
    experiments/18 ensemble does. If memory becomes a problem, swap
    this for a single-task / hot-swap-adapter implementation.
    """
    if adapter_name not in ADAPTER_SPECS:
        raise KeyError(f"unknown adapter {adapter_name!r}; "
                       f"expected one of {list(ADAPTER_SPECS)}")
    if adapter_name in _ADAPTERS:
        return _ADAPTERS[adapter_name]

    with _INIT_LOCK:
        if adapter_name in _ADAPTERS:
            return _ADAPTERS[adapter_name]

        spec = ADAPTER_SPECS[adapter_name]
        log.info("terramind_nyc: building task for %s", adapter_name)

        from huggingface_hub import snapshot_download
        from peft import LoraConfig, inject_adapter_in_model
        from safetensors.torch import load_file
        from terratorch.tasks import SemanticSegmentationTask

        # 1. Pull the requested adapter subtree from the HF repo.
        adapter_root = snapshot_download(
            ADAPTERS_REPO,
            allow_patterns=[f"{spec['subdir']}/*"],
        )

        # 2. Build the standard terratorch task with the same model_args
        #    the published HF_README quick-start uses.
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

        # 3. Inject the LoRA scaffold the adapter weights were trained
        #    against. Same hyperparameters every adapter in this family
        #    used (see experiments/18 adapters/_template/config.yaml).
        inject_adapter_in_model(LoraConfig(
            r=16, lora_alpha=32, lora_dropout=0.05,
            target_modules=["attn.qkv", "attn.proj"], bias="none",
        ), task.model.encoder)

        # 4. Restore Δ matrices (encoder LoRA) and the decoder/neck/head
        #    weights from the safetensors bundle. The encoder.* prefix
        #    is stripped because the encoder state-dict is rooted at
        #    the encoder module, not the task.
        adapter_dir = f"{adapter_root}/{spec['subdir']}"
        lora_state = load_file(f"{adapter_dir}/adapter_model.safetensors")
        head_state = load_file(f"{adapter_dir}/decoder_head.safetensors")
        encoder_state = {
            k.removeprefix("encoder."): v
            for k, v in lora_state.items() if k.startswith("encoder.")
        }
        task.model.encoder.load_state_dict(encoder_state, strict=False)
        for sub in ("decoder", "neck", "head", "aux_heads"):
            sub_state = {
                k[len(sub) + 1:]: v
                for k, v in head_state.items() if k.startswith(sub + ".")
            }
            if sub_state and hasattr(task.model, sub):
                getattr(task.model, sub).load_state_dict(sub_state,
                                                          strict=False)

        # 5. Move to the configured device. CUDA only if the caller
        #    asked AND a CUDA device is actually available — silently
        #    fall back to CPU otherwise.
        target_device = DEVICE
        if target_device == "cuda":
            import torch
            if not torch.cuda.is_available():
                log.warning("terramind_nyc: CUDA unavailable, falling back to CPU")
                target_device = "cpu"
        task = task.to(target_device).eval()

        _ADAPTERS[adapter_name] = task
        log.info("terramind_nyc: %s ready on %s", adapter_name, target_device)
        return task


def _tiled_predict(task, modality_chips: dict, num_classes: int):
    """Run the task's encoder-decoder forward in 224×224 tiles, returning
    a (1, num_classes, H, W) logits tensor stitched from the windows.

    TerraMind's positional embeddings are tied to the 224×224 training
    resolution. terratorch's tiled_inference helper slides a window
    across the input modalities (it accepts a dict of per-modality
    tensors as long as all modalities share H×W), runs the model on
    each crop, and averages overlapping logits. Without it, larger
    chips return silent garbage; smaller chips error on the encoder
    ViT.
    """
    import torch
    from terratorch.tasks.tiled_inference import tiled_inference

    # tiled_inference invokes `model_forward(patch)` per tile. The task
    # model returns a ModelOutput-like with .output OR a plain tensor;
    # coerce to tensor either way.
    def _forward(x, **_extra):
        out = task.model(x)
        return out.output if hasattr(out, "output") else out

    with torch.no_grad():
        logits = tiled_inference(
            _forward,
            modality_chips,
            out_channels=num_classes,
            h_crop=TILE_SIZE,
            w_crop=TILE_SIZE,
            h_stride=TILE_STRIDE,
            w_stride=TILE_STRIDE,
            average_patches=True,
            blend_overlaps=True,
            padding="reflect",
        )
    return logits


def _summarize_lulc(pred, class_labels: list[str]) -> dict[str, Any]:
    """Per-class pixel fraction + dominant class from an integer mask."""
    import numpy as np
    pred_np = pred.detach().cpu().numpy() if hasattr(pred, "detach") else np.asarray(pred)
    flat = pred_np.reshape(-1)
    n = max(int(flat.size), 1)
    fractions: dict[str, float] = {}
    for idx, label in enumerate(class_labels):
        pct = 100.0 * float((flat == idx).sum()) / n
        if pct > 0:
            fractions[label] = round(pct, 2)
    dominant_idx = int(max(range(len(class_labels)),
                            key=lambda i: int((flat == i).sum())))
    return {
        "ok": True,
        "n_pixels": int(flat.size),
        "shape": list(pred_np.shape),
        "class_fractions": fractions,
        "dominant_class": class_labels[dominant_idx],
        "dominant_pct": fractions.get(class_labels[dominant_idx], 0.0),
    }


def _summarize_buildings(pred, class_labels: list[str]) -> dict[str, Any]:
    """Building-pixel coverage + simple connected-component count."""
    import numpy as np
    pred_np = pred.detach().cpu().numpy() if hasattr(pred, "detach") else np.asarray(pred)
    mask = (pred_np == 1).astype("uint8")
    n_total = max(int(mask.size), 1)
    pct_built = 100.0 * float(mask.sum()) / n_total
    # Connected-component count is a cheap signal of "how many distinct
    # buildings does this chip cover" — useful for the briefing without
    # paying for full polygonisation.
    n_components: int | None = None
    try:
        from scipy.ndimage import label
        _, n_components = label(mask)
    except Exception:  # scipy is optional in some HF Spaces build cones
        log.debug("terramind_nyc: scipy.ndimage unavailable; "
                  "skipping component count")
    return {
        "ok": True,
        "n_pixels": int(mask.size),
        "shape": list(mask.shape),
        "pct_buildings": round(pct_built, 2),
        "n_building_components": n_components,
        "class_labels": class_labels,
    }


def _try_remote(adapter_name: str, modality_chips: dict) -> dict | None:
    """POST to the riprap-models inference service if configured.

    Returns:
      - successful result dict on a 200/ok=True remote response
      - {"ok": False, "skipped": "<reason>"} when remote was attempted
        but failed (RemoteUnreachable, ok=False, or other error). The
        caller MUST NOT fall through to local terratorch in this case
        — local has been broken on the CPU-tier UI Spaces since the
        torchvision binary mismatch landed, and we'd rather show a
        clean "remote unreachable" reason than a noisy crash.
      - None ONLY when remote isn't configured at all (caller may
        legitimately try local then)."""
    try:
        from app import inference as _inf
        if not _inf.remote_enabled():
            return None
        s2 = modality_chips.get("S2L2A")
        s1 = modality_chips.get("S1RTC")
        dem = modality_chips.get("DEM")
        # The router serializes torch tensors to base64 numpy float32 —
        # the chip cache hands us [B, C, T, H, W]; keep that shape, the
        # service rebuilds the temporal stack on its end.
        result = _inf.terramind(adapter_name, s2, s1, dem)
        if not result.get("ok"):
            err = result.get("error") or result.get("err") or "unknown"
            return {"ok": False,
                    "skipped": f"remote terramind/{adapter_name} non-ok: {err}"}
        result.setdefault("adapter", adapter_name)
        result.setdefault("repo", ADAPTERS_REPO)
        result["compute"] = f"remote · {result.get('device', 'gpu')}"
        # Polygonize the prediction raster onto the chip's bounds so
        # the map can paint the LULC / buildings overlay. Bounds come
        # via the modality_chips dict — the eo_chip layer threads them
        # through. Best-effort; never raises into the FSM.
        bounds = modality_chips.get("bounds_4326") if modality_chips else None
        pred_b64 = result.get("pred_b64")
        pred_shape = result.get("pred_shape")
        class_labels = result.get("class_labels")
        if bounds and pred_b64 and pred_shape:
            try:
                from app.context._polygonize import (
                    polygonize_binary_mask,
                    polygonize_class_raster,
                )
                if adapter_name == "buildings":
                    polys = polygonize_binary_mask(
                        pred_b64, pred_shape, tuple(bounds),
                        label="building", fill_color="#D62728",
                        simplify_tolerance=2e-5,
                    )
                else:
                    polys = polygonize_class_raster(
                        pred_b64, pred_shape, class_labels, tuple(bounds),
                        simplify_tolerance=2e-5,
                    )
                result["polygons_geojson"] = polys
            except Exception:
                log.exception("terramind/%s: polygonize failed", adapter_name)
                result["polygons_geojson"] = None
        return result
    except _inf.RemoteUnreachable as e:
        log.info("terramind/%s: remote unreachable (%s)", adapter_name, e)
        return {"ok": False,
                "skipped": f"remote terramind/{adapter_name} unreachable: {e}"}
    except Exception as e:
        log.exception("terramind/%s: remote call failed", adapter_name)
        return {"ok": False,
                "skipped": f"remote terramind/{adapter_name} error: "
                           f"{type(e).__name__}: {e}"}


def _run(adapter_name: str, modality_chips: dict, summarizer):
    """Common boilerplate: gate, time, [remote attempt], load, tiled
    predict, summarize."""
    if not ENABLE:
        return {"ok": False,
                "skipped": "RIPRAP_TERRAMIND_NYC_ENABLE=0"}

    # v0.4.5 — try remote first. The remote service has its own deps,
    # so this path works even when local _DEPS_OK is False (the most
    # common HF Spaces case until terratorch + peft are baked in).
    remote = _try_remote(adapter_name, modality_chips or {})
    if remote is not None:
        return remote

    if not _DEPS_OK:
        return {"ok": False,
                "skipped": f"deps unavailable on this deployment: "
                           f"{_DEPS_MISSING}"}
    if not modality_chips:
        return {"ok": False, "err": "no modality chips supplied"}
    t0 = time.time()
    try:
        task = _ensure_adapter(adapter_name)
        spec = ADAPTER_SPECS[adapter_name]
        # Strip out bounds_4326 (auxiliary metadata, not a tensor) before
        # handing the dict to terratorch's tiled_inference, which iterates
        # all values as modalities.
        tensors_only = {k: v for k, v in modality_chips.items()
                        if k != "bounds_4326"}
        logits = _tiled_predict(task, tensors_only, spec["num_classes"])
        # logits: (B, C, H, W). Argmax to per-pixel class id.
        pred = logits.argmax(dim=1).squeeze(0)
        result = summarizer(pred, spec["class_labels"])
        result["elapsed_s"] = round(time.time() - t0, 2)
        result["adapter"] = adapter_name
        result["repo"] = ADAPTERS_REPO
        result["compute"] = "local"
        return result
    except Exception as e:
        msg = str(e)
        # Translate torchvision binary-extension failures into a clean
        # skip. terratorch + torchvision both ride a transitive
        # dep cone on the HF Space (sentence-transformers pulls torch
        # CPU; torchvision's C extension can't load against that wheel),
        # so a local _ensure_adapter() raises RuntimeError with this
        # signature when remote is also unreachable. Clean skip is the
        # honest demo outcome — same as terramind_synthesis.
        if "torchvision::nms" in msg or "torchvision_C" in msg:
            log.warning("terramind_nyc/%s: torchvision binary unavailable; "
                        "remote unreachable too; clean skip", adapter_name)
            return {"ok": False,
                    "skipped": "remote inference unreachable + local "
                               "torchvision binary unavailable on this "
                               "deployment",
                    "elapsed_s": round(time.time() - t0, 2)}
        log.exception("terramind_nyc.%s failed", adapter_name)
        return {"ok": False, "err": f"{type(e).__name__}: {e}",
                "elapsed_s": round(time.time() - t0, 2)}


def lulc(s2l2a, s1rtc=None, dem=None,
          bounds_4326: tuple[float, float, float, float] | None = None,
          ) -> dict[str, Any]:
    """5-class NYC macro land-cover.

    Inputs are torch tensors. The temporal models we trained expect
    [C, T, H, W] (preferred) or [C, H, W] (will be expanded to T=1).
    Pass S1 and DEM if you have them — the published adapter was
    trained on the full triplet and accuracy degrades when modalities
    are dropped.

    `bounds_4326` is `(minlon, minlat, maxlon, maxlat)` of the chip
    in WGS84; when provided, the LULC raster is polygonised onto the
    chip's geographic extent so the map can render an overlay.
    """
    chips = {"S2L2A": s2l2a}
    if bounds_4326 is not None:
        chips["bounds_4326"] = bounds_4326
    if s1rtc is not None:
        chips["S1RTC"] = s1rtc
    if dem is not None:
        chips["DEM"] = dem
    return _run("lulc", chips, _summarize_lulc)


def buildings(s2l2a, s1rtc=None, dem=None,
               bounds_4326: tuple[float, float, float, float] | None = None,
               ) -> dict[str, Any]:
    """Binary NYC building-footprint mask. Same input contract as lulc()."""
    chips = {"S2L2A": s2l2a}
    if bounds_4326 is not None:
        chips["bounds_4326"] = bounds_4326
    if s1rtc is not None:
        chips["S1RTC"] = s1rtc
    if dem is not None:
        chips["DEM"] = dem
    return _run("buildings", chips, _summarize_buildings)


def warm():
    """Optional pre-load — amortizes the first-query model build cost."""
    if not ENABLE or not _DEPS_OK:
        return
    try:
        for name in ADAPTER_SPECS:
            _ensure_adapter(name)
    except Exception:
        log.exception("terramind_nyc: warm() failed; specialists will no-op")
