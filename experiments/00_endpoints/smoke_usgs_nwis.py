"""USGS Water Services: Bronx River at NY Botanical Garden (01302020)."""

import json
import sys
import urllib.request

from _runner import cli, write_cache  # noqa: E402

URL = ("https://waterservices.usgs.gov/nwis/iv/?format=json"
       "&sites=01302020&parameterCd=00060,00065"
       "&period=P1D")


def probe():
    with urllib.request.urlopen(URL, timeout=20) as r:
        d = json.loads(r.read())
    series = d.get("value", {}).get("timeSeries", [])
    if not series:
        return False, "no time-series for 01302020", None
    name = series[0]["sourceInfo"]["siteName"]
    n = sum(len(s.get("values", [{}])[0].get("value", [])) for s in series)
    write_cache("usgs_nwis", {"siteName": name, "series": len(series),
                              "total_obs_24h": n})
    return True, f"{name} ({len(series)} series, {n} obs/24h)", d


if __name__ == "__main__":
    sys.exit(cli("usgs_nwis", probe))
