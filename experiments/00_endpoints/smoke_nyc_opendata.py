"""NYC Open Data Socrata: hit one row each from 311 (erm2-nwe9), PLUTO
(64uk-42ks), Sandy Inundation Zone (5xsi-dfpx)."""

import json
import sys
import urllib.request

from _runner import cli, write_cache  # noqa: E402

DATASETS = {
    "311":   "https://data.cityofnewyork.us/resource/erm2-nwe9.json?$limit=1",
    "pluto": "https://data.cityofnewyork.us/resource/64uk-42ks.json?$limit=1",
    "sandy": "https://data.cityofnewyork.us/resource/5xsi-dfpx.json?$limit=1",
}


def probe():
    out = {}
    for name, url in DATASETS.items():
        with urllib.request.urlopen(url, timeout=15) as r:
            rows = json.loads(r.read())
        if not rows:
            return False, f"{name}: empty result", None
        out[name] = list(rows[0].keys())[:5]
    write_cache("nyc_opendata", out)
    return True, ", ".join(f"{k}={len(v)}cols" for k, v in out.items()), out


if __name__ == "__main__":
    sys.exit(cli("nyc_opendata", probe))
