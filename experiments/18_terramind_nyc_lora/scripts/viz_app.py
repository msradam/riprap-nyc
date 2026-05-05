"""Gradio visualizer for the three TerraMind-NYC LoRA adapters.

Loads cached test-set chips (ImpactMesh format from Phase 2/3) and runs
all three adapters on a chosen chip. Shows: Sentinel-2 RGB input,
LULC-NYC prediction, TiM-NYC prediction, Buildings-NYC prediction, and
the ground-truth LULC mask for reference.

Run inside the terramind container:
    cd /workspace/phase18
    python3 scripts/viz_app.py

Then SSH-forward 7860 from your Mac:
    ssh -L 7860:localhost:7860 root@<droplet-ip>
And open http://localhost:7860/
"""
from __future__ import annotations

import sys
from pathlib import Path

import gradio as gr
import numpy as np
import torch
import yaml
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
from inference_ensemble import TerraMindNYCEnsemble  # noqa: E402
from train_lora import build_datamodule  # noqa: E402


# Color palettes
LULC_COLORS = np.array([
    [200, 90, 80],     # 0 impervious / urban
    [100, 200, 110],   # 1 vegetation
    [70, 130, 220],    # 2 water
    [240, 220, 150],   # 3 bare / cropland
    [50, 50, 80],      # 4 building (LULC scope)
], dtype=np.uint8)

BUILDINGS_COLORS = np.array([
    [60, 60, 80],      # 0 non-building
    [255, 200, 60],    # 1 building
], dtype=np.uint8)


def render_rgb(s2: torch.Tensor) -> Image.Image:
    """Render an S2L2A chip as an RGB PIL image (B04/B03/B02 = R/G/B)."""
    # s2: [12, 4, H, W] (12 bands, 4 timesteps)
    t0 = s2[:, 0].numpy()  # use first timestep
    rgb = t0[[3, 2, 1]]    # bands B04, B03, B02
    p98 = max(np.percentile(rgb, 98), 1.0)
    rgb = (rgb / p98 * 255).clip(0, 255).astype(np.uint8)
    rgb = rgb.transpose(1, 2, 0)
    return Image.fromarray(rgb)


def colorize(pred: torch.Tensor, palette: np.ndarray) -> Image.Image:
    arr = pred.numpy().astype(np.int64)
    arr = np.clip(arr, 0, len(palette) - 1)
    return Image.fromarray(palette[arr])


# ---- Setup -----------------------------------------------------------------

print("Loading inference ensemble...", flush=True)
ENS = TerraMindNYCEnsemble(
    Path(__file__).resolve().parent.parent / "adapters")
ENS.discover()

print("Loading test data...", flush=True)
ROOT = Path(__file__).resolve().parent.parent
cfg = yaml.safe_load((ROOT / "adapters/lulc_nyc/config.yaml").read_text())
dm = build_datamodule(cfg["data"])
dm.setup("test")

# Pre-cache the first test batch so every click is fast.
print("Caching test batch...", flush=True)
TEST_BATCH = next(iter(dm.test_dataloader()))
N_CHIPS = TEST_BATCH["mask"].shape[0]
print(f"Cached {N_CHIPS} chips. Ready.", flush=True)


def run(chip_idx: int):
    chip_idx = int(chip_idx)
    s2 = TEST_BATCH["image"]["S2L2A"][chip_idx]
    s1 = TEST_BATCH["image"]["S1RTC"][chip_idx]
    dem = TEST_BATCH["image"]["DEM"][chip_idx]
    gt_mask = TEST_BATCH["mask"][chip_idx]

    rgb = render_rgb(s2)
    out = ENS.infer(s2l2a=s2, s1rtc=s1, dem=dem,
                    tasks=["lulc_nyc", "tim_nyc", "buildings_nyc"])

    lulc = colorize(out["lulc_nyc"], LULC_COLORS)
    tim = colorize(out["tim_nyc"], LULC_COLORS)
    bld = colorize(out["buildings_nyc"], BUILDINGS_COLORS)
    gt = colorize(gt_mask.clamp(0, 4), LULC_COLORS)

    summary = (
        f"Chip {chip_idx} of {N_CHIPS - 1} from the held-out NYC test split.\n"
        f"Each adapter: 1 forward pass through TerraMind 1.0 base + the "
        f"task-specific LoRA + decoder.\n"
        f"Encoder shared across all three adapters; only the per-task "
        f"overlay differs."
    )
    return rgb, lulc, tim, bld, gt, summary


with gr.Blocks(title="TerraMind-NYC Adapters Viz") as demo:
    gr.Markdown("# TerraMind-NYC LoRA Adapters")
    gr.Markdown(
        "Three LoRA adapters specializing IBM-ESA's TerraMind 1.0 base on "
        "New York City Earth-observation tasks. Test mIoU 0.5866 / 0.6023 / "
        "0.5518 across NYC 5-class land cover, the same task with "
        "Thinking-in-Modalities, and binary NYC building footprints. "
        "Apache 2.0. Fine-tuned on AMD Instinct MI300X via AMD Developer Cloud. "
        "[`msradam/TerraMind-NYC-Adapters`](https://huggingface.co/msradam/TerraMind-NYC-Adapters)"
    )

    with gr.Row():
        chip_slider = gr.Slider(0, N_CHIPS - 1, value=0, step=1,
                                label="Test chip index")
        run_btn = gr.Button("Run all three adapters",
                            variant="primary")

    with gr.Row():
        rgb_out = gr.Image(label="Sentinel-2 RGB input (B04/B03/B02)",
                           type="pil", height=320)
        gt_out = gr.Image(label="Ground truth (5-class NYC LULC)",
                          type="pil", height=320)

    with gr.Row():
        lulc_out = gr.Image(label="LULC-NYC LoRA — 5-class land cover",
                            type="pil", height=320)
        tim_out = gr.Image(label="TiM-NYC LoRA — same + Thinking-in-Modalities",
                           type="pil", height=320)

    with gr.Row():
        bld_out = gr.Image(label="Buildings-NYC LoRA — binary footprints",
                           type="pil", height=320)
        info_out = gr.Markdown()

    gr.Markdown(
        "**LULC palette:** red = impervious / urban, green = vegetation, "
        "blue = water, yellow = bare, dark = building. "
        "**Buildings palette:** orange = building, dark = non-building."
    )

    run_btn.click(run, inputs=[chip_slider],
                  outputs=[rgb_out, lulc_out, tim_out, bld_out, gt_out, info_out])
    demo.load(run, inputs=[chip_slider],
              outputs=[rgb_out, lulc_out, tim_out, bld_out, gt_out, info_out])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
