"""FEMA OpenFEMA: aggregated NFIP claims by NY census tract.

Property-level NFIP records are off-limits per project policy. We only
pull tract-level aggregates. The OpenFEMA endpoint streams large
result sets via CSV; we use the v2 dataset list as the smoke test
since the actual claims download is multi-GB."""

import json
import sys
import urllib.request

from _runner import cli, write_cache  # noqa: E402

URL = "https://www.fema.gov/api/open/v2/FimaNfipClaims?$top=1&$filter=state%20eq%20'NY'"


def probe():
    with urllib.request.urlopen(URL, timeout=20) as r:
        d = json.loads(r.read())
    claims = d.get("FimaNfipClaims", [])
    if not claims:
        return False, f"no NY claims sample (response keys: {list(d.keys())})", None
    sample_keys = sorted(list(claims[0].keys()))[:6]
    write_cache("openfema", {"sample_keys": sample_keys,
                              "metadata": d.get("metadata", {})})
    return True, f"NY sample row, keys[:6]={sample_keys}", d


if __name__ == "__main__":
    sys.exit(cli("openfema", probe))
