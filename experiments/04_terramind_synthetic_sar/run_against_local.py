"""Phase 4 end-to-end harness: real S1 -> TerraMind -> Phase 1 head ->
reconciler call against local Ollama.

Picks one of the three NYC test addresses, walks the full chain, and
prints both the synthesized-water % and the briefing the local
Ollama-backed reconciler produces against the synthetic doc. The
reconciler narration must use the "generated a plausible scene"
framing — never "imaged the scene".

Skips automatically when STAC's S1 collection is unavailable (PC
flakes). When that happens the chain plumbing is still validated
via the run_terramind_generate.py + run_segmentation_on_synthetic.py
zeros-input path.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fetch_s1grd_chip import fetch as fetch_s1  # noqa: E402
from run_segmentation_on_synthetic import segment  # noqa: E402
from run_terramind_generate import generate_s2_from_s1  # noqa: E402

from experiments.shared import backends, trace_render  # noqa: E402

ADDRS = {
    "brighton": (40.5780, -73.9617),
    "hollis":   (40.7115, -73.7681),
    "hunts":    (40.8155, -73.8830),
}

USER_PROMPT = (
    "Write a single sentence describing the synthetic-modality water "
    "observation, citing [terramind_synthetic]. Use the careful framing "
    "'generated a plausible Sentinel-2 scene from the radar context' — "
    "never 'imaged the scene'. Do not invent any value not in the doc."
)


def _make_doc(s1_meta, gen, seg) -> dict[str, str]:
    body = [
        "Source: TerraMind 1.0 base any-to-any generation, S1GRD -> "
        "S2L2A chain, then Prithvi-EO 2.0 Sen1Floods11 segmentation on "
        "the synthesis. Synthetic modality — model produces plausible "
        "scenes from radar context, not reconstructions.",
        f"S1 GRD scene id: {s1_meta.get('item_id')}",
        f"S1 acquisition date: {s1_meta.get('item_datetime', '')[:10]}",
        f"diffusion_steps: {gen.diffusion_steps}",
        f"diffusion_seed: {gen.seed}",
        "synthetic_modality: true",
        "tim_chain: S1GRD -> S2L2A_synthetic",
        f"% water within 500 m of address: "
        f"{seg.pct_water_within_500m:.2f}",
        f"% water across 5 km synthesized chip: {seg.pct_water_full:.2f}",
    ]
    return {"role": "document terramind_synthetic", "content": "\n".join(body)}


def _run_for_address(label: str, lat: float, lon: float, *,
                     start: str, end: str, steps: int, seed: int) -> dict:
    print(trace_render.banner(f"Phase 4 chain · {label} ({lat}, {lon})"))

    # 1. Real S1 GRD chip
    try:
        t0 = time.time()
        s1 = fetch_s1(lat, lon, search_start=start, search_end=end)
        t_fetch = time.time() - t0
        print(f"S1 fetch:          {t_fetch:.2f}s  scene={s1.item_id}")
    except Exception as e:
        return {"label": label, "stage": "stac_s1",
                "error": f"{type(e).__name__}: {e}"}

    # 2. TerraMind synthesis (S1 -> S2L2A)
    import rasterio
    with rasterio.open(s1.out_path) as src:
        s1_arr = src.read().astype("float32")
    t0 = time.time()
    gen = generate_s2_from_s1(s1_chip=s1_arr, steps=steps, seed=seed,
                               chip_shape=(224, 224))
    print(f"TerraMind synth:   {gen.elapsed_s:.2f}s  -> {gen.out_npy_path}")

    # 3. Phase 1 segmentation head on synthesized S2
    t0 = time.time()
    seg = segment(gen.out_npy_path)
    print(f"Phase 1 seg:       {seg.elapsed_s:.2f}s  "
          f"%water_500m={seg.pct_water_within_500m:.2f}  "
          f"%water_chip={seg.pct_water_full:.2f}")

    # 4. Reconciler call against local Ollama
    s1_meta_dict = {"item_id": s1.item_id,
                    "item_datetime": s1.item_datetime}
    doc = _make_doc(s1_meta_dict, gen, seg)
    print(f"\ndoc body:\n{doc['content']}\n")

    backends.configure(backend="ollama")
    t0 = time.time()
    try:
        messages = [
            doc,
            {"role": "system", "content": (
                "Cite [terramind_synthetic] at least once. Use the "
                "honesty framing 'generated a plausible Sentinel-2 "
                "scene from the radar context'. Never claim "
                "reconstruction or 'imaged'."
            )},
            {"role": "user", "content": USER_PROMPT},
        ]
        resp = backends.chat(model="granite4.1:8b", messages=messages,
                             options={"temperature": 0,
                                      "num_predict": 200,
                                      "num_ctx": 4096})
        narration = resp["message"]["content"].strip()
    except Exception as e:
        narration = f"<reconcile error: {type(e).__name__}: {e}>"
    print(trace_render.banner(f"Reconciler ({time.time() - t0:.2f}s)"))
    print(narration)

    return {
        "label": label, "lat": lat, "lon": lon,
        "s1_scene": s1.item_id,
        "s1_date": s1.item_datetime,
        "diffusion_steps": gen.diffusion_steps,
        "diffusion_seed": gen.seed,
        "synth_elapsed_s": gen.elapsed_s,
        "seg_elapsed_s": seg.elapsed_s,
        "pct_water_500m": seg.pct_water_within_500m,
        "pct_water_chip": seg.pct_water_full,
        "narration": narration,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--address", choices=list(ADDRS) + ["all"], default="brighton")
    ap.add_argument("--start", default="2024-09-01")
    ap.add_argument("--end",   default="2024-09-30")
    ap.add_argument("--steps", type=int, default=10)
    ap.add_argument("--seed",  type=int, default=42)
    args = ap.parse_args()

    targets = (list(ADDRS.items()) if args.address == "all"
               else [(args.address, ADDRS[args.address])])
    out = []
    for label, (lat, lon) in targets:
        out.append(_run_for_address(label, lat, lon,
                                    start=args.start, end=args.end,
                                    steps=args.steps, seed=args.seed))
    summary = Path(__file__).parent / ".cache" / "run_against_local.json"
    summary.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
