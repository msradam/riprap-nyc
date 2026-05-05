"""Run every smoke test, print one summary line per test, exit non-zero
if any failed."""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(HERE))
    spec.loader.exec_module(mod)
    return mod


TESTS = ["smoke_stac", "smoke_nyc_opendata", "smoke_usgs_nwis",
         "smoke_noaa_tides", "smoke_noaa_nwps", "smoke_nws",
         "smoke_openfema", "smoke_hf_hub"]


def main() -> int:
    fails = 0
    for name in TESTS:
        try:
            mod = load(name)
        except Exception as e:
            print(f"FAIL  {name}  (import error: {e})")
            fails += 1
            continue
        rc = mod.cli(name.replace("smoke_", ""), mod.probe)
        if rc:
            fails += 1
    print(f"\n{len(TESTS) - fails}/{len(TESTS)} passed")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
