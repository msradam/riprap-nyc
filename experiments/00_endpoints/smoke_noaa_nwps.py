"""NOAA National Water Prediction Service: list reaches in NY county."""

import json
import sys
import urllib.request

from _runner import cli, write_cache  # noqa: E402

# Bbox of mid-Atlantic states (NYC has no in-bbox NWPS gauges; NWPS
# covers the Hudson tributaries inland). The `srid=EPSG_4326` query
# param is required even though the bbox is geographic — without it,
# the endpoint returns an empty array silently.
URL = ("https://api.water.noaa.gov/nwps/v1/gauges?srid=EPSG_4326"
       "&bbox.xmin=-78&bbox.xmax=-72&bbox.ymin=40&bbox.ymax=45")


def probe():
    req = urllib.request.Request(URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read())
    gauges = d.get("gauges") or d.get("features") or []
    if not gauges:
        # Endpoint may have moved; record the response so we can debug.
        write_cache("noaa_nwps_unexpected", d)
        return False, f"no gauges in NYC bbox: keys={list(d.keys())}", None
    write_cache("noaa_nwps", {"n_gauges": len(gauges),
                              "first_keys": list(gauges[0].keys())[:8]})
    return True, f"{len(gauges)} gauges", d


if __name__ == "__main__":
    sys.exit(cli("noaa_nwps", probe))
