"""NWS API: active alerts for NY."""

import json
import sys
import urllib.request

from _runner import cli, write_cache  # noqa: E402

URL = "https://api.weather.gov/alerts/active?area=NY"


def probe():
    req = urllib.request.Request(URL,
        headers={"User-Agent": "riprap-experiments (dev) msrahmanadam@gmail.com",
                 "Accept": "application/geo+json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    feats = d.get("features", [])
    titles = [f["properties"].get("event") for f in feats[:5]]
    write_cache("nws_alerts", {"n_active": len(feats), "first_5_events": titles})
    return True, f"{len(feats)} active alerts; first 5: {titles}", d


if __name__ == "__main__":
    sys.exit(cli("nws", probe))
