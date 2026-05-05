"""NOAA Tides & Currents: last 6h water level at The Battery (8518750)."""

import json
import sys
import urllib.request

from _runner import cli, write_cache  # noqa: E402

URL = ("https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
       "?date=latest&station=8518750&product=water_level&datum=MLLW"
       "&time_zone=lst&units=english&format=json")


def probe():
    with urllib.request.urlopen(URL, timeout=15) as r:
        d = json.loads(r.read())
    data = d.get("data") or []
    if not data:
        return False, f"empty response: {d}", None
    last = data[-1]
    write_cache("noaa_tides", {"station": "8518750", "last": last,
                                "n_obs": len(data)})
    return True, f"Battery latest v={last.get('v')}ft @ {last.get('t')}", d


if __name__ == "__main__":
    sys.exit(cli("noaa_tides", probe))
