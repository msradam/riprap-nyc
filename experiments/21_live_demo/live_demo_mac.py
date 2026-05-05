"""Mac-local version of the Riprap NYC live-data demo.

Differences from the droplet version:
  - Pulls Prithvi v2 ckpt from huggingface.co/msradam/Prithvi-EO-2.0-NYC-Pluvial
    (cached after first run).
  - Pulls TTM Battery weights from huggingface.co/msradam/Granite-TTM-r2-Battery-Surge.
  - Targets `mps` (Apple Silicon) automatically; falls back to `cpu`.

Run:
    cd /Users/amsrahman/hackathons/riprap-nyc
    .venv/bin/python experiments/21_live_demo/live_demo_mac.py
Then open http://localhost:7860
"""
from __future__ import annotations

import io
import time
from datetime import datetime, timedelta, date
from pathlib import Path

import gradio as gr
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import requests
import torch
from PIL import Image
from huggingface_hub import hf_hub_download
from pystac_client import Client
from rasterio.warp import transform as warp_transform
from rasterio.windows import from_bounds


DEVICE = ("mps" if torch.backends.mps.is_available()
          else "cuda" if torch.cuda.is_available()
          else "cpu")
print(f"[device] using {DEVICE}", flush=True)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

NYC_NEIGHBORHOODS = {
    "Coney Island Boardwalk (Brooklyn)":     (40.5723, -73.9656),
    "Hollis (Queens)":                       (40.7100, -73.7600),
    "Red Hook (Brooklyn)":                   (40.6770, -74.0096),
    "Astoria / Steinway (Queens)":           (40.7731, -73.9171),
    "The Battery (lower Manhattan)":         (40.7037, -74.0146),
    "Lower East Side (Manhattan)":           (40.7156, -73.9858),
    "Howard Beach (Queens)":                 (40.6571, -73.8447),
    "Canarsie (Brooklyn)":                   (40.6356, -73.9019),
    "Mott Haven (Bronx)":                    (40.8082, -73.9243),
}

# Model repos
PRITHVI_REPO = "msradam/Prithvi-EO-2.0-NYC-Pluvial"
PRITHVI_CKPT_FILE = "prithvi_nyc_pluvial_v2.ckpt"
TTM_REPO = "msradam/Granite-TTM-r2-Battery-Surge"

# Imagery + normalization
PRITHVI_BANDS = ["B02", "B03", "B04", "B8A", "B11", "B12"]
EARTH_SEARCH_ASSET = {"B02": "blue", "B03": "green", "B04": "red",
                      "B8A": "nir08", "B11": "swir16", "B12": "swir22"}
PRITHVI_MEANS = np.array(
    [1086.45, 1063.0, 985.95, 2316.61, 2080.98, 1454.81], dtype=np.float32)
PRITHVI_STDS = np.array(
    [1141.95, 1170.10, 1287.78, 1369.24, 1374.77, 1318.21], dtype=np.float32)

NOAA_API = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
NOAA_STATION = "8518750"
TTM_CONTEXT = 1024
TTM_HORIZON = 96


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def load_prithvi():
    print(f"[prithvi] downloading ckpt from {PRITHVI_REPO}...", flush=True)
    ckpt_path = hf_hub_download(repo_id=PRITHVI_REPO,
                                filename=PRITHVI_CKPT_FILE)
    print(f"[prithvi] ckpt at {ckpt_path}", flush=True)
    from terratorch.tasks import SemanticSegmentationTask
    task = SemanticSegmentationTask.load_from_checkpoint(
        ckpt_path, map_location=DEVICE)
    task.eval()
    return task


def load_ttm():
    print(f"[ttm] downloading weights from {TTM_REPO}...", flush=True)
    from tsfm_public import TinyTimeMixerForPrediction
    model = TinyTimeMixerForPrediction.from_pretrained(TTM_REPO)
    model = model.to(DEVICE).eval()
    return model


# ---------------------------------------------------------------------------
# Prithvi: live S2 fetch + inference
# ---------------------------------------------------------------------------

def fetch_s2_chip(lat: float, lon: float, days_back: int = 30,
                  max_cloud: int = 30, chip_px: int = 224):
    client = Client.open("https://earth-search.aws.element84.com/v1")
    end = date.today()
    start = end - timedelta(days=days_back)
    d = 0.01
    bbox = (lon - d, lat - d, lon + d, lat + d)
    items = list(client.search(
        collections=["sentinel-2-l2a"], bbox=bbox,
        datetime=f"{start.isoformat()}/{end.isoformat()}",
        query={"eo:cloud_cover": {"lt": max_cloud}},
        max_items=20).items())
    if not items:
        return None, {"error": f"no S2 acquisitions found in last {days_back} days"}
    items.sort(key=lambda i: i.properties["datetime"], reverse=True)
    item = items[0]

    HALF_M = chip_px / 2 * 10
    cb = (lon - HALF_M / 85_000.0, lat - HALF_M / 111_000.0,
          lon + HALF_M / 85_000.0, lat + HALF_M / 111_000.0)
    bands = []
    for b in PRITHVI_BANDS:
        href = item.assets[EARTH_SEARCH_ASSET[b]].href
        with rasterio.open(href) as src:
            xs, ys = warp_transform("EPSG:4326", src.crs,
                                    [cb[0], cb[2]], [cb[1], cb[3]])
            window = from_bounds(xs[0], ys[0], xs[1], ys[1], src.transform)
            data = src.read(1, window=window, boundless=True, fill_value=0,
                            out_shape=(chip_px, chip_px))
        bands.append(data.astype(np.float32))
    return np.stack(bands), {
        "scene_id": item.id,
        "acquisition": item.properties["datetime"][:10],
        "cloud_cover_pct": round(float(item.properties.get("eo:cloud_cover", -1)), 1),
    }


def render_rgb(chip: np.ndarray) -> Image.Image:
    rgb = chip[[2, 1, 0]]
    p98 = max(np.percentile(rgb, 98), 1.0)
    rgb = (rgb / p98 * 255).clip(0, 255).astype(np.uint8).transpose(1, 2, 0)
    return Image.fromarray(rgb)


def overlay_flood(rgb: Image.Image, mask: np.ndarray,
                  alpha: float = 0.55) -> Image.Image:
    rgb_np = np.array(rgb).astype(np.float32)
    blue = np.array([60, 130, 220], dtype=np.float32)
    overlay = rgb_np.copy()
    m = mask.astype(bool)
    overlay[m] = rgb_np[m] * (1 - alpha) + blue * alpha
    return Image.fromarray(overlay.clip(0, 255).astype(np.uint8))


def run_prithvi(neighborhood: str, days_back: int):
    if PRITHVI_TASK is None:
        return None, None, "Prithvi model not loaded; see server logs."
    lat, lon = NYC_NEIGHBORHOODS[neighborhood]
    chip, meta = fetch_s2_chip(lat, lon, days_back=days_back)
    if chip is None:
        return None, None, f"FETCH FAILED: {meta.get('error')}"

    rgb = render_rgb(chip)
    norm = (chip - PRITHVI_MEANS[:, None, None]) / PRITHVI_STDS[:, None, None]
    x = torch.from_numpy(norm).float().unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        out = PRITHVI_TASK.model(x)
        logits = out.output if hasattr(out, "output") else out
        pred = logits.argmax(dim=1).squeeze(0).cpu().numpy().astype(np.uint8)

    overlay = overlay_flood(rgb, pred, alpha=0.55)
    flood_pct = 100 * pred.mean()
    summary = (
        f"**Live Sentinel-2 inference for {neighborhood}** "
        f"(lat {lat:.4f}, lon {lon:.4f})\n\n"
        f"- Scene: `{meta['scene_id']}`\n"
        f"- Acquisition: {meta['acquisition']}\n"
        f"- Cloud cover: {meta['cloud_cover_pct']}%\n"
        f"- Predicted flood pixels: **{flood_pct:.2f}%** of chip "
        f"({pred.sum():,} of {pred.size:,} pixels)\n\n"
        f"Model: `{PRITHVI_REPO}` v2 (Lovász-Softmax + copy-paste aug). "
        f"Test flood IoU 0.5979. Running on `{DEVICE}`."
    )
    return rgb, overlay, summary


# ---------------------------------------------------------------------------
# TTM: live NOAA fetch + 96 h forecast
# ---------------------------------------------------------------------------

def fetch_noaa_window(hours_back: int = 1100) -> pd.DataFrame:
    end_d = datetime.utcnow().date()
    n_days = (hours_back // 24) + 3

    def call_chunk(product, s, e, interval=None):
        params = {
            "station": NOAA_STATION,
            "begin_date": s.strftime("%Y%m%d"),
            "end_date":   e.strftime("%Y%m%d"),
            "product": product, "datum": "MLLW", "units": "metric",
            "time_zone": "gmt", "format": "json",
            "application": "riprap-nyc-mac-demo",
        }
        if interval:
            params["interval"] = interval
        for attempt in range(3):
            try:
                r = requests.get(NOAA_API, params=params, timeout=60)
                r.raise_for_status()
                d = r.json()
                key = "data" if "data" in d else "predictions"
                if key not in d:
                    return pd.DataFrame()
                df = pd.DataFrame(d[key])
                df["timestamp"] = pd.to_datetime(df["t"])
                df["value"] = pd.to_numeric(df["v"], errors="coerce")
                return df[["timestamp", "value"]].dropna()
            except Exception as e:
                print(f"  ! NOAA {product} {s}..{e} attempt {attempt+1}: {e}",
                      flush=True)
                time.sleep(2 ** attempt)
        return pd.DataFrame()

    def collect(product, interval=None, chunk_days=30):
        chunks = []
        cur_end = end_d
        while cur_end > end_d - timedelta(days=n_days):
            cur_start = max(cur_end - timedelta(days=chunk_days),
                            end_d - timedelta(days=n_days))
            df = call_chunk(product, cur_start, cur_end, interval)
            if not df.empty:
                chunks.append(df)
            cur_end = cur_start - timedelta(days=1)
        return (pd.concat(chunks, ignore_index=True) if chunks
                else pd.DataFrame())

    wl = collect("water_level", interval=None, chunk_days=30)
    pr = collect("predictions", interval="h", chunk_days=30)
    if wl.empty or pr.empty:
        raise RuntimeError("NOAA fetch returned empty; API may be down")
    wl["hour"] = wl["timestamp"].dt.floor("h")
    pr["hour"] = pr["timestamp"].dt.floor("h")
    pr_h = pr.groupby("hour")["value"].mean().reset_index().rename(
        columns={"value": "predicted"})
    wl_h = wl.groupby("hour")["value"].mean().reset_index().rename(
        columns={"value": "water_level"})
    df = wl_h.merge(pr_h, on="hour", how="inner")
    df["surge_residual_m"] = df["water_level"] - df["predicted"]
    return df.sort_values("hour").reset_index(drop=True)


def run_ttm():
    if TTM_MODEL is None:
        return None, "TTM model not loaded; see server logs."
    try:
        df = fetch_noaa_window(hours_back=TTM_CONTEXT + 50)
    except Exception as e:
        return None, f"NOAA fetch error: {e}"
    if len(df) < TTM_CONTEXT:
        return None, (f"NOAA returned only {len(df)} hours; need {TTM_CONTEXT}.")

    series = df["surge_residual_m"].values.astype(np.float32)
    context = series[-TTM_CONTEXT:]
    last_t = df["hour"].iloc[-1]

    x = torch.from_numpy(context).float().unsqueeze(0).unsqueeze(-1).to(DEVICE)
    with torch.no_grad():
        out = TTM_MODEL(past_values=x)
        forecast = out.prediction_outputs.squeeze().cpu().numpy()

    persist = np.full(TTM_HORIZON, context[-1])
    fcast_t = pd.date_range(last_t + pd.Timedelta(hours=1),
                            periods=TTM_HORIZON, freq="h")
    ctx_t = df["hour"].iloc[-min(168, TTM_CONTEXT):]
    ctx_v = context[-len(ctx_t):]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(ctx_t, ctx_v, color="#222", linewidth=1.6,
            label="observed (last 7 days)")
    ax.plot(fcast_t, forecast, color="#c4452b", linewidth=2.0,
            label="TTM r2 fine-tuned forecast (96 h)")
    ax.plot(fcast_t, persist, color="#888", linestyle="--", linewidth=1.2,
            label="persistence baseline")
    ax.axvline(last_t, color="#aaa", linestyle=":", linewidth=1)
    ax.set_ylabel("Surge residual at The Battery (m)")
    ax.set_title("NOAA Battery (NY) station 8518750, live surge nowcast")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b-%d %H:%M"))
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130)
    plt.close(fig)
    buf.seek(0)

    summary = (
        f"**Live NOAA Battery (NY) nowcast.**\n\n"
        f"- Last observed hour: `{last_t}` UTC\n"
        f"- Current surge residual: **{context[-1]:+.3f} m**\n"
        f"- 96 h forecast peak: **{forecast.max():+.3f} m** at "
        f"`{fcast_t[forecast.argmax()]}` UTC\n"
        f"- 96 h forecast min: **{forecast.min():+.3f} m**\n\n"
        f"Model: `{TTM_REPO}`. Test RMSE 0.157 m "
        f"(35% better than persistence). Running on `{DEVICE}`."
    )
    return Image.open(buf), summary


# ---------------------------------------------------------------------------
# Build models
# ---------------------------------------------------------------------------

print("=== Loading models ===", flush=True)
try:
    PRITHVI_TASK = load_prithvi()
    print("  Prithvi v2 loaded", flush=True)
except Exception as e:
    print(f"  Prithvi load failed: {e}", flush=True)
    PRITHVI_TASK = None

try:
    TTM_MODEL = load_ttm()
    print("  TTM Battery loaded", flush=True)
except Exception as e:
    print(f"  TTM load failed: {e}", flush=True)
    TTM_MODEL = None


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

with gr.Blocks(title="Riprap NYC, live demo (Mac)") as demo:
    gr.Markdown(
        f"# Riprap NYC live-data demo (running on `{DEVICE}`)\n"
        "Two NYC fine-tunes hitting live public APIs:\n"
        "- **Prithvi-EO 2.0 NYC Pluvial v2** running on a fresh Sentinel-2 chip "
        "from Element 84 Earth Search\n"
        "- **Granite TTM r2 Battery Surge** running on the last 1024 hours "
        "from NOAA station 8518750\n\n"
        "Both Apache 2.0, both fine-tuned on AMD Instinct MI300X via AMD Developer Cloud, "
        "both pulled fresh from "
        "[huggingface.co/msradam](https://huggingface.co/msradam)."
    )

    with gr.Tabs():
        with gr.Tab("Prithvi v2 — live S2 segmentation"):
            with gr.Row():
                hood = gr.Dropdown(
                    list(NYC_NEIGHBORHOODS), value=list(NYC_NEIGHBORHOODS)[0],
                    label="NYC neighborhood (uses live Sentinel-2)")
                days = gr.Slider(7, 90, value=30, step=1,
                                 label="Search window (days back)")
                run_p = gr.Button("Fetch + segment", variant="primary")
            with gr.Row():
                rgb_out = gr.Image(label="Sentinel-2 RGB (live)",
                                   type="pil", height=380)
                ovr_out = gr.Image(label="Predicted flood overlay (blue tint)",
                                   type="pil", height=380)
            sum_p = gr.Markdown()
            run_p.click(run_prithvi, inputs=[hood, days],
                        outputs=[rgb_out, ovr_out, sum_p])

        with gr.Tab("TTM Battery — live surge nowcast"):
            run_t = gr.Button("Pull NOAA + forecast 96 h", variant="primary")
            plot_out = gr.Image(label="Live surge residual + 96 h forecast",
                                type="pil", height=480)
            sum_t = gr.Markdown()
            run_t.click(run_ttm, inputs=None, outputs=[plot_out, sum_t])


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
