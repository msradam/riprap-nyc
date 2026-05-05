"""TerraMind-NYC inference ensemble: one base, hot-swap adapters.

This is what Riprap's FSM specialist nodes consume. Loads the TerraMind
1.0 base model once into memory, then swaps a single active adapter
(LULC / TiM / Buildings) per task call. Per ADR-007 we don't merge
adapters — sequential swap is simpler and matches our deployment shape.

Usage:
    from shared.inference_ensemble import TerraMindNYCEnsemble

    ens = TerraMindNYCEnsemble(adapters_root="adapters/")
    out = ens.infer(s2l2a_chip, s1rtc_chip, dem_chip, tasks=["lulc", "buildings"])
    # {"lulc": [5, 224, 224] long, "buildings": [2, 224, 224] long, ...}

The first call materializes the base; subsequent task switches reuse it.
The adapter swap is ~50 ms per task per call, dominated by file I/O the
first time and a state-dict overwrite afterwards.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import torch
import yaml
from peft import LoraConfig, inject_adapter_in_model
from safetensors.torch import load_file

sys.path.insert(0, str(Path(__file__).parent))
from train_lora import build_task  # noqa: E402


@dataclass
class AdapterSlot:
    name: str
    config: dict
    lora_state: dict = field(default_factory=dict)
    head_state: dict = field(default_factory=dict)
    task: object | None = None       # lazy-built Lightning task
    num_classes: int = 0


class TerraMindNYCEnsemble:
    """One TerraMind base per num_classes group, N adapters total.

    Per-adapter num_classes differs (LULC=5, Buildings=2) so each
    adapter gets its own Lightning task with the right segmentation
    head shape. Tasks are lazy-built on first set_adapter call. The
    base TerraMind weights are duplicated across tasks (acceptable on
    MI300X with 192 GB; if memory-constrained, group tasks by
    num_classes and share encoder via PEFT adapter switching within a
    group).
    """

    def __init__(self, adapters_root: Path | str = "adapters/",
                 device: str | None = None):
        self.adapters_root = Path(adapters_root)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._adapters: dict[str, AdapterSlot] = {}
        self._active_adapter: str | None = None

    # ---- adapter discovery + caching --------------------------------------

    def discover(self) -> list[str]:
        """Scan adapters_root and cache LoRA + decoder weights into RAM."""
        names = []
        for cfg_path in sorted(self.adapters_root.glob("*/config.yaml")):
            cfg = yaml.safe_load(cfg_path.read_text())
            output_dir = (Path(cfg.get("output_dir", cfg_path.parent / "output"))
                          .resolve())
            adapter_path = cfg_path.parent / "output"
            if not (adapter_path / "adapter_model.safetensors").exists():
                # Fall back to absolute output_dir from config (e.g. droplet path).
                adapter_path = output_dir
            if not (adapter_path / "adapter_model.safetensors").exists():
                continue
            slot = AdapterSlot(
                name=cfg.get("task_name", cfg_path.parent.name),
                config=cfg,
                lora_state=load_file(adapter_path / "adapter_model.safetensors"),
                head_state=load_file(adapter_path / "decoder_head.safetensors"),
                num_classes=cfg["num_classes"],
            )
            self._adapters[slot.name] = slot
            names.append(slot.name)
        return names

    # ---- swap + inference -------------------------------------------------

    def _build_slot_task(self, slot: AdapterSlot):
        """Build a Lightning task for this adapter, restore weights."""
        if slot.task is not None:
            return
        task = build_task(slot.config).to(self.device).eval()
        model = task.model

        enc_state = {k.removeprefix("encoder."): v.to(self.device)
                     for k, v in slot.lora_state.items()
                     if k.startswith("encoder.")}
        model.encoder.load_state_dict(enc_state, strict=False)

        head_grouped: dict[str, dict] = {}
        for k, v in slot.head_state.items():
            sub, _, rest = k.partition(".")
            head_grouped.setdefault(sub, {})[rest] = v.to(self.device)
        for sub, state in head_grouped.items():
            m = getattr(model, sub, None)
            if m is None:
                continue
            m.load_state_dict(state, strict=False)
        slot.task = task

    def set_adapter(self, name: str):
        if name == self._active_adapter:
            return
        if name not in self._adapters:
            raise KeyError(f"adapter {name!r} not loaded; "
                           f"available: {list(self._adapters)}")
        self._build_slot_task(self._adapters[name])
        self._active_adapter = name

    @property
    def _task(self):
        """Convenience accessor for the currently active adapter's task."""
        if self._active_adapter is None:
            return None
        return self._adapters[self._active_adapter].task

    @torch.no_grad()
    def infer(self, *, s2l2a: torch.Tensor,
              s1rtc: torch.Tensor | None = None,
              dem: torch.Tensor | None = None,
              tasks: list[str]) -> dict[str, torch.Tensor]:
        """Run multiple tasks against the same input chip.

        Each tensor: [C, T, H, W] (temporal mode) or [C, H, W] (static).
        Outputs: dict {task_name: argmax-class map [H, W] long}.
        """
        out = {}
        # Add a batch dim if the user passed unbatched input.
        def _b(t):
            if t is None:
                return None
            return t.unsqueeze(0) if t.dim() in (3, 4) else t

        x = {"S2L2A": _b(s2l2a).to(self.device)}
        if s1rtc is not None:
            x["S1RTC"] = _b(s1rtc).to(self.device)
        if dem is not None:
            x["DEM"] = _b(dem).to(self.device)

        for task_name in tasks:
            self.set_adapter(task_name)
            res = self._task.model(x)
            logits = res.output if hasattr(res, "output") else res
            preds = logits.argmax(dim=1).squeeze(0).cpu()
            out[task_name] = preds
        return out

    def memory_estimate_gb(self) -> float:
        n_built = sum(1 for s in self._adapters.values() if s.task is not None)
        # Each task is ~168 M params @ fp32 = ~672 MB, fp16 = ~336 MB.
        return n_built * 0.336

    # ---- diagnostics ------------------------------------------------------

    def info(self) -> dict:
        return {
            "device": self.device,
            "loaded_adapters": list(self._adapters),
            "active_adapter": self._active_adapter,
            "base_built": self._task is not None,
        }


if __name__ == "__main__":
    # Smoke check.
    ens = TerraMindNYCEnsemble("adapters/")
    names = ens.discover()
    print(f"Discovered adapters: {names}")
    if not names:
        sys.exit("No adapters found. Train at least one before using the "
                 "ensemble.")
    print(ens.info())
