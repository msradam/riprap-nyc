"""Pre-compute TWI (Topographic Wetness Index) and HAND (Height Above
Nearest Drainage) for the cached NYC DEM.

These are standard hydrology indices used by InfoWorks ICM, HEC-RAS,
and the Forest Service / USGS. They give the microtopo specialist new
per-address signal beyond elevation percentile + relief:

- **TWI** = ln(specific_catchment_area / tan(slope)). HIGH values mean
  a cell is saturation-prone (large upslope drainage area + low slope =
  water accumulates here).
- **HAND** = vertical distance from each cell to the nearest channel.
  LOW values (sub-meter) mean the address sits at or near drainage
  level — flood-vulnerable. HIGH values mean it's perched on dry ground.

Output: data/twi.tif and data/hand.tif, aligned with data/nyc_dem_30m.tif.

Run: python scripts/compute_hydrology_indices.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
DEM_PATH = ROOT / "data" / "nyc_dem_30m.tif"
TWI_OUT = ROOT / "data" / "twi.tif"
HAND_OUT = ROOT / "data" / "hand.tif"


def main() -> int:
    if not DEM_PATH.exists():
        print(f"missing {DEM_PATH}; run scripts/fetch_nyc_dem.py first",
              file=sys.stderr)
        return 1
    if TWI_OUT.exists() and HAND_OUT.exists():
        print(f"already exist: {TWI_OUT.name}, {HAND_OUT.name}", file=sys.stderr)
        return 0

    import whitebox_workflows as wbw
    wbe = wbw.WbEnvironment()
    wbe.verbose = True
    wbe.working_directory = str(ROOT / "data")

    print("loading DEM...", file=sys.stderr)
    dem = wbe.read_raster(str(DEM_PATH))

    # 1. Hydrologic conditioning — fill depressions so flow routes terminate
    #    at the boundary, not inside spurious sinks. Wang & Liu fill is fast.
    print("filling depressions (Wang & Liu)...", file=sys.stderr)
    dem_filled = wbe.fill_depressions_wang_and_liu(dem)

    # 2. D-infinity flow accumulation -> specific catchment area for TWI
    print("D-infinity flow accumulation...", file=sys.stderr)
    sca = wbe.dinf_flow_accum(dem_filled, out_type="specific contributing area",
                               log_transform=False)

    # 3. Slope (degrees) for TWI
    print("slope...", file=sys.stderr)
    slope = wbe.slope(dem_filled, units="degrees")

    # 4. TWI = ln(SCA / tan(slope))
    print("TWI...", file=sys.stderr)
    twi = wbe.wetness_index(sca, slope)
    wbe.write_raster(twi, str(TWI_OUT.name), compress=True)

    # 5. Streams: D8 flow accumulation + threshold to a stream raster
    print("D8 flow accumulation for stream extraction...", file=sys.stderr)
    d8_accum = wbe.d8_flow_accum(dem_filled, out_type="cells",
                                  log_transform=False)

    # Threshold the flow accumulation to identify channels — pick a value that
    # gives a reasonable drainage network density. For 30m DEM over NYC,
    # >1500 cells (~1.35 km²) is a reasonable channel-initiation threshold.
    print("extracting streams...", file=sys.stderr)
    streams = wbe.extract_streams(d8_accum, threshold=1500.0)

    # 6. HAND = vertical distance to nearest stream (along flow paths)
    print("HAND (elevation_above_stream)...", file=sys.stderr)
    hand = wbe.elevation_above_stream(dem_filled, streams)
    wbe.write_raster(hand, str(HAND_OUT.name), compress=True)

    print(f"\nwrote:\n  {TWI_OUT}  ({TWI_OUT.stat().st_size // 1024} KB)\n"
          f"  {HAND_OUT}  ({HAND_OUT.stat().st_size // 1024} KB)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
