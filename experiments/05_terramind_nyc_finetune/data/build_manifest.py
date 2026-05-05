"""Build a paired (S2L2A, S1GRD-RTC) STAC manifest for the NYC TerraMind
micro-fine-tune. No chip downloads — just URLs + bbox metadata.

Spec (from experiments/05_terramind_nyc_finetune/eval/eval_spec.md):
  - Spatial:   NYC 5-borough convex hull buffered ~5 km
  - Temporal:  2021-05-01 -> 2026-04-30
  - Modalities: S2L2A + S1GRD-RTC, paired (same date window)
  - Chips:     224x224 px (recorded as bbox; chipping happens at train)
  - Cap:       ~2000 paired chips for the micro fine-tune
  - Held-out:  5 cloudy NYC scenes from April 2026 (qualitative judges)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

import planetary_computer as pc
from pystac_client import Client

# NYC 5-borough convex hull buffered ~5 km (lon/lat bbox).
# bounds: w=-74.30, s=40.45, e=-73.65, n=40.95
NYC_BBOX = [-74.30, 40.45, -73.65, 40.95]
DATE_RANGE = "2021-05-01/2026-04-30"
HOLDOUT_RANGE = "2026-04-01/2026-04-30"

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/"
S2_COLL = "sentinel-2-l2a"
S1_COLL = "sentinel-1-rtc"

PAIR_WINDOW_DAYS = 3        # max delta between matched S2 / S1 dates
TARGET_PAIRS = 2000
HOLDOUT_TARGET = 5
HOLDOUT_MIN_CLOUD = 60      # "cloudy" = >=60% cloud cover

OUT_DIR = "/root/terramind_nyc"
TRAIN_OUT = os.path.join(OUT_DIR, "manifest_train.jsonl")
HOLDOUT_OUT = os.path.join(OUT_DIR, "manifest_holdout.jsonl")


def search(client, coll, bbox, datetime_range, query=None, limit=500):
    """Page in chunks of 250 to stay under the PC API time budget."""
    return client.search(
        collections=[coll],
        bbox=bbox,
        datetime=datetime_range,
        query=query,
        max_items=limit,
        limit=250,
    ).item_collection()


def parse_dt(item):
    return datetime.fromisoformat(item.properties["datetime"].replace("Z", "+00:00"))


def pair_items(s2_items, s1_items, window_days):
    """For each S2 scene, find the closest S1 scene within window_days."""
    s1_by_dt = sorted(((parse_dt(it), it) for it in s1_items), key=lambda x: x[0])
    pairs = []
    for s2 in s2_items:
        s2_dt = parse_dt(s2)
        best = None
        best_delta = None
        for s1_dt, s1 in s1_by_dt:
            delta = abs((s1_dt - s2_dt).days)
            if best is None or delta < best_delta:
                best = s1
                best_delta = delta
        if best is not None and best_delta <= window_days:
            pairs.append((s2, best, best_delta))
    return pairs


def signed_asset(item, key):
    a = item.assets.get(key)
    if a is None:
        return None
    return pc.sign(a.href)


def s2_band_urls(item):
    keys = ["B02", "B03", "B04", "B05", "B06", "B07",
            "B08", "B8A", "B11", "B12", "AOT", "SCL"]
    return {k: signed_asset(item, k) for k in keys}


def s1_band_urls(item):
    return {"vv": signed_asset(item, "vv"), "vh": signed_asset(item, "vh")}


def write_record(fh, s2, s1, delta_days, chip_size=224):
    rec = {
        "s2_id": s2.id,
        "s1_id": s1.id,
        "s2_datetime": s2.properties["datetime"],
        "s1_datetime": s1.properties["datetime"],
        "delta_days": delta_days,
        "bbox": s2.bbox,
        "cloud_cover": s2.properties.get("eo:cloud_cover"),
        "chip_size_px": chip_size,
        "s2_assets": s2_band_urls(s2),
        "s1_assets": s1_band_urls(s1),
    }
    fh.write(json.dumps(rec) + "\n")


def search_by_year(client, coll, bbox, year_ranges, query=None, per_year=600,
                   retries=3):
    """PC times out on multi-year searches; window per year. Retry per year."""
    import time
    out = []
    for r in year_ranges:
        items = []
        for attempt in range(retries):
            try:
                items = list(search(client, coll, bbox, r, query=query,
                                    limit=per_year))
                break
            except Exception as e:
                print(f"[manifest]   warn: {coll} {r} attempt {attempt+1}: {e}")
                time.sleep(2 + 3 * attempt)
        print(f"[manifest]   {coll} {r}: {len(items)} scenes")
        out.extend(items)
    return out


YEAR_RANGES = [
    "2021-05-01/2022-04-30",
    "2022-05-01/2023-04-30",
    "2023-05-01/2024-04-30",
    "2024-05-01/2025-04-30",
    "2025-05-01/2026-04-30",
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    client = Client.open(STAC_URL)

    print(f"[manifest] searching S2L2A bbox={NYC_BBOX}")
    s2 = search_by_year(client, S2_COLL, NYC_BBOX, YEAR_RANGES,
                        query={"eo:cloud_cover": {"lt": 30}}, per_year=500)
    print(f"[manifest]   got {len(s2)} S2 scenes total")

    print(f"[manifest] searching S1GRD-RTC bbox={NYC_BBOX}")
    s1 = search_by_year(client, S1_COLL, NYC_BBOX, YEAR_RANGES, per_year=500)
    print(f"[manifest]   got {len(s1)} S1 scenes total")

    print(f"[manifest] pairing within {PAIR_WINDOW_DAYS} days...")
    pairs = pair_items(list(s2), list(s1), PAIR_WINDOW_DAYS)
    print(f"[manifest]   {len(pairs)} paired scenes")

    pairs = pairs[:TARGET_PAIRS]
    with open(TRAIN_OUT, "w") as fh:
        for p in pairs:
            write_record(fh, *p)
    print(f"[manifest] wrote {len(pairs)} -> {TRAIN_OUT}")

    # Held-out cloudy April 2026 set (retry-wrapped)
    print(f"[manifest] searching held-out cloudy S2 {HOLDOUT_RANGE} cc>={HOLDOUT_MIN_CLOUD}")
    cloudy = search_by_year(
        client, S2_COLL, NYC_BBOX, [HOLDOUT_RANGE],
        query={"eo:cloud_cover": {"gte": HOLDOUT_MIN_CLOUD}}, per_year=50)
    s1_holdout = search_by_year(
        client, S1_COLL, NYC_BBOX, [HOLDOUT_RANGE], per_year=200)
    holdout_pairs = pair_items(list(cloudy), list(s1_holdout), PAIR_WINDOW_DAYS)
    holdout_pairs = holdout_pairs[:HOLDOUT_TARGET]
    with open(HOLDOUT_OUT, "w") as fh:
        for p in holdout_pairs:
            write_record(fh, *p)
    print(f"[manifest] wrote {len(holdout_pairs)} held-out -> {HOLDOUT_OUT}")

    # Estimate GPU-hours
    n = len(pairs)
    # micro.py converged in ~30 steps on synthetic; real fine-tune target
    # was ~3 epochs over n chips at batch 8 on MI300X (~3 chips/sec for
    # full encoder unfreeze). 3 epochs * n / 3 = n seconds at bs=1.
    # With bs=8 effective: 3 * n / (3*8) sec ~= n/8 sec total.
    est_sec = 3 * n / 8 * 1.5  # 1.5x overhead for I/O + val
    print(f"[manifest] est wall-clock @ bs=8 / 3 epoch: {est_sec/3600:.2f} GPU-hours "
          f"(budget 30, alarm 25)")


if __name__ == "__main__":
    sys.exit(main())
