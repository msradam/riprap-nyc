"""Microsoft Planetary Computer STAC: Sentinel-2 L2A search over a
small NYC bbox. Verifies search works keylessly and that the result has
asset URLs we can sign with `planetary_computer.sign(item)`."""

import sys

from _runner import cli, write_cache  # noqa: E402


def probe():
    import planetary_computer as pc
    from pystac_client import Client

    client = Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=pc.sign_inplace,
    )
    # ~Brooklyn south shore bbox
    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=[-74.05, 40.55, -73.90, 40.65],
        datetime="2024-09-01/2024-09-30",
        query={"eo:cloud_cover": {"lt": 30}},
        max_items=3,
    )
    items = list(search.items())
    if not items:
        return False, "no items returned", None
    it = items[0]
    asset_keys = sorted(it.assets.keys())
    visual_url = it.assets.get("visual", it.assets[asset_keys[0]]).href
    write_cache("stac_first_item",
                {"id": it.id, "datetime": str(it.datetime),
                 "asset_keys": asset_keys, "visual_url": visual_url})
    return True, f"{len(items)} items, first={it.id}", it


if __name__ == "__main__":
    sys.exit(cli("stac", probe))
