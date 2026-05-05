"""Unit tests for the TerraMind-NYC adapter wrapper.

These tests don't actually load weights or run inference — they verify
the gate paths (ENABLE=0, missing deps), the public API surface, and
the result-dict shape so the FSM specialist can consume the output
without surprises. Real end-to-end smoke testing happens in commit 4
once the FSM action wires this in and a chip cache is available.
"""
from __future__ import annotations

import importlib
import os

import pytest


def _reload_with_env(**env):
    """Reimport the module with mutated environment so module-level
    constants (ENABLE, DEVICE) re-evaluate."""
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    import app.context.terramind_nyc as m
    return importlib.reload(m)


def test_module_imports_without_loading_weights():
    """Importing the module must not download or build the base model."""
    m = _reload_with_env()
    # Adapter cache empty by default.
    assert m._ADAPTERS == {}
    assert {"lulc", "buildings"} <= set(m.ADAPTER_SPECS)
    assert m.ADAPTERS_REPO == "msradam/TerraMind-NYC-Adapters"


def test_disabled_returns_skipped_outcome():
    m = _reload_with_env(RIPRAP_TERRAMIND_NYC_ENABLE="0")
    assert m.ENABLE is False
    out = m.lulc(None)
    assert out == {"ok": False, "skipped": "RIPRAP_TERRAMIND_NYC_ENABLE=0"}
    out = m.buildings(None, s1rtc=None, dem=None)
    assert out == {"ok": False, "skipped": "RIPRAP_TERRAMIND_NYC_ENABLE=0"}
    # Restore default for the rest of the suite.
    _reload_with_env(RIPRAP_TERRAMIND_NYC_ENABLE="1")


def test_unknown_adapter_raises_keyerror():
    m = _reload_with_env(RIPRAP_TERRAMIND_NYC_ENABLE="1")
    with pytest.raises(KeyError):
        m._ensure_adapter("nonsense")


def test_summarize_lulc_shape():
    """_summarize_lulc emits the dict shape the FSM doc-builder will
    consume — class fractions, dominant class, dominant pct, n_pixels."""
    import numpy as np
    m = _reload_with_env()
    pred = np.array([[0, 0, 0],
                     [2, 2, 2],
                     [4, 4, 4]])
    labels = ["Trees", "Cropland", "Built", "Bare", "Water"]
    out = m._summarize_lulc(pred, labels)
    assert out["ok"] is True
    assert out["n_pixels"] == 9
    assert out["shape"] == [3, 3]
    # Three classes appeared, equally; dominant is the FIRST in argmax tie.
    assert set(out["class_fractions"]) == {"Trees", "Built", "Water"}
    for v in out["class_fractions"].values():
        assert v == pytest.approx(33.33, abs=0.1)
    assert out["dominant_class"] in {"Trees", "Built", "Water"}
    assert out["dominant_pct"] > 0


def test_summarize_buildings_shape():
    import numpy as np
    m = _reload_with_env()
    pred = np.array([[0, 0, 1],
                     [0, 1, 1],
                     [0, 0, 0]])
    labels = ["Background", "Building footprint"]
    out = m._summarize_buildings(pred, labels)
    assert out["ok"] is True
    assert out["n_pixels"] == 9
    assert out["pct_buildings"] == pytest.approx(33.33, abs=0.1)
    assert out["class_labels"] == labels
    # scipy.ndimage may or may not be installed; the helper degrades
    # rather than raising. If it's installed, two diagonal/adjacent
    # building pixels should land in one connected component.
    assert out["n_building_components"] in {None, 1}


def test_public_api_signatures():
    m = _reload_with_env()
    import inspect
    for fn in (m.lulc, m.buildings):
        sig = inspect.signature(fn)
        params = list(sig.parameters)
        # Caller may pass S2 only OR S2+S1+DEM.
        assert params[0] == "s2l2a"
        assert "s1rtc" in params
        assert "dem" in params


def test_warm_is_no_op_when_disabled():
    """warm() must not download anything when ENABLE=0 or deps missing."""
    m = _reload_with_env(RIPRAP_TERRAMIND_NYC_ENABLE="0")
    # No exceptions, no side effects.
    m.warm()
    assert m._ADAPTERS == {}
    _reload_with_env(RIPRAP_TERRAMIND_NYC_ENABLE="1")
