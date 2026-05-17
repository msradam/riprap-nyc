"""Verifies graceful offline behavior of model pebbles.

The user's stated regression target: with RunPod/inference offline, the
app must still run end-to-end and surface "inference offline" gracefully
rather than raising. This exercises the prithvi_live model pebble in
its offline path (driven by RIPRAP_PRITHVI_LIVE_ENABLE=0, which is the
fastest way to simulate the inference server being down without
mocking network layers).
"""
from __future__ import annotations


def test_prithvi_live_pebble_graceful_offline(monkeypatch):
    monkeypatch.setenv("RIPRAP_PRITHVI_LIVE_ENABLE", "0")
    # Reload the module so it picks up the new env at import time.
    import importlib  # noqa: PLC0415

    import app.flood_layers.prithvi_live as pl  # noqa: PLC0415
    importlib.reload(pl)

    from riprap.core.pebbles.bridge import fetch_pebble  # noqa: PLC0415
    value, _, err = fetch_pebble("prithvi_live", 40.71, -73.98)

    assert err is None  # the pebble adapter itself didn't error
    assert value is not None  # we got a value dict
    assert value.get("ok") is False  # but ok=False signals offline
    # `skipped` or `err` should explain why; either is acceptable.
    assert (value.get("skipped") or value.get("err"))
