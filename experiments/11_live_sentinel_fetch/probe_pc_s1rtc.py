"""Probe live Sentinel-1 RTC fetch via Microsoft Planetary Computer.

Sentinel-1 RTC (radiometric terrain corrected) is the SAR product our
TerraMind-NYC model was trained on. Earth Search only hosts Sentinel-1
GRD (raw slant-range, no CRS), which would require us to process the
RTC step ourselves — non-trivial.

Microsoft PC hosts `sentinel-1-rtc` as a STAC collection. Has been
flaky in our prior tests (May 3 evening showed >50% timeout rate).
Re-probing here.

Sovereignty disclosure: PC requires a one-time URL signing per asset,
sponsored by Microsoft. Same Copernicus license on the data. Less
sovereign than Earth Search; less authoritative than ESA CDSE.

Usage:
    python3 probe_pc_s1rtc.py --lat 40.7484 --lon -73.9857
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_USE_HEAD", "NO")

PC = "https://planetarycomputer.microsoft.com/api/stac/v1/"
S1_RTC = "sentinel-1-rtc"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=40.7484)
    ap.add_argument("--lon", type=float, default=-73.9857)
    ap.add_argument("--max-age-days", type=int, default=30)
    args = ap.parse_args()

    from pystac_client import Client
    import planetary_computer as pc
    import rasterio
    from rasterio.warp import transform as warp_transform
    from rasterio.windows import from_bounds

    print(f"[probe] PC STAC: {PC}", flush=True)
    print(f"[probe] lat,lon = ({args.lat}, {args.lon})", flush=True)

    today = datetime.utcnow().date()
    earliest = (today - timedelta(days=args.max_age_days)).isoformat()
    d = 0.01
    bbox = (args.lon - d, args.lat - d, args.lon + d, args.lat + d)

    t0 = time.time()
    err = None
    item = None
    for attempt in range(4):
        try:
            client = Client.open(PC)
            items = list(client.search(
                collections=[S1_RTC],
                bbox=bbox,
                datetime=f"{earliest}/{today.isoformat()}",
                max_items=10,
            ).items())
            if items:
                items.sort(key=lambda i: i.properties["datetime"], reverse=True)
                item = items[0]
                break
            err = f"no S1-RTC items in last {args.max_age_days} days"
        except Exception as e:
            err = f"PC search attempt {attempt+1}: {e}"
            print(f"[probe] {err}", flush=True)
            time.sleep(2 + 3 * attempt)

    if not item:
        print(f"[probe] FAIL: {err}", flush=True)
        return 1

    s1_dt = datetime.fromisoformat(item.properties["datetime"].replace("Z", "+00:00"))
    age = (today - s1_dt.date()).days
    print(f"[probe] S1-RTC product: {item.id}", flush=True)
    print(f"[probe] acquired: {item.properties['datetime']} ({age} days ago)",
          flush=True)
    print(f"[probe] PC search wall-clock: {time.time()-t0:.2f}s", flush=True)

    # Sign + read VV chip window
    t = time.time()
    try:
        signed = pc.sign(item.assets["vv"].href)
        with rasterio.open(signed) as src:
            print(f"[probe] CRS: {src.crs}, shape: {src.shape}", flush=True)
            HALF = 1280  # ~2.56 km
            xs, ys = warp_transform(
                "EPSG:4326", src.crs,
                [args.lon - HALF/85_000.0, args.lon + HALF/85_000.0],
                [args.lat - HALF/111_000.0, args.lat + HALF/111_000.0],
            )
            window = from_bounds(xs[0], ys[0], xs[1], ys[1], src.transform)
            chip = src.read(1, window=window, boundless=True, fill_value=0,
                            out_shape=(256, 256))
            print(f"[probe] vv chip read: {time.time()-t:.2f}s, "
                  f"shape={chip.shape}, dtype={chip.dtype}, "
                  f"nz_pct={(chip > 0).mean()*100:.1f}%, "
                  f"mean={float(chip.mean()):.4f}", flush=True)
    except Exception as e:
        print(f"[probe] vv chip read FAIL: {e}", flush=True)
        return 1

    print(f"\n[probe] === Result ===", flush=True)
    print(json.dumps({
        "ok": True,
        "source": "microsoft_planetary_computer",
        "collection": S1_RTC,
        "product_id": item.id,
        "s1_acquired_iso": item.properties["datetime"],
        "s1_age_days": age,
        "elapsed_s": round(time.time() - t0, 2),
        "license": "ESA Copernicus License (free for any use, attribution required)",
        "host": "Microsoft Planetary Computer (URL-signed, free)",
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
