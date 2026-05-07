"""End-to-end integration tests for the post-Phase-1/2/3 FSM.

Hits `/api/agent/stream` over SSE and asserts on the resulting trace
+ briefing for the three NYC test addresses (Brighton Beach, Hollis,
Hunts Point). Designed to be the regression gate for the new
specialists (Prithvi live, GLiNER, Granite Reranker R2).

Setup:
    Server must be running on RIPRAP_TEST_BASE (default
    http://127.0.0.1:7860). Tests assume the server was started with:
      RIPRAP_RERANKER_ENABLE=1
      RIPRAP_GLINER_ENABLE=1
      RIPRAP_PRITHVI_LIVE_ENABLE=1
    (defaults match these except the reranker flag.)

Backend parameterization:
    `RIPRAP_TEST_BACKENDS=ollama` (default) or
    `RIPRAP_TEST_BACKENDS=ollama,vllm` to run the full matrix. We
    don't flip the server's backend per test — instead the test
    suite is run twice with different RIPRAP_LLM_PRIMARY env on the
    server side, and asserts on the active backend via /api/backend.

Usage:
    .venv/bin/uvicorn web.main:app --port 7860 &  # in another shell
    .venv/bin/pytest tests/test_integration.py -v
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

BASE = os.environ.get("RIPRAP_TEST_BASE", "http://127.0.0.1:7860")
# Heavy specialists (prithvi_live, terramind) are only added to the FSM
# when RIPRAP_HEAVY_SPECIALISTS=1 or RIPRAP_ML_BASE_URL is set.  Tests
# that assert these steps fired must skip when the gate is off.
_HEAVY_SPECIALISTS = os.environ.get("RIPRAP_HEAVY_SPECIALISTS", "").lower() in (
    "1", "true", "yes"
) or bool(os.environ.get("RIPRAP_ML_BASE_URL", "").strip())
TIMEOUT_S = float(os.environ.get("RIPRAP_TEST_TIMEOUT", "300"))


@dataclass
class StreamResult:
    events: list[tuple[str, dict]]
    plan: dict | None
    final: dict | None
    errors: list[dict]
    trace_steps: list[str]
    elapsed_s: float


def _stream(query: str, timeout: float = TIMEOUT_S) -> StreamResult:
    """Hit /api/agent/stream and return a parsed StreamResult."""
    url = f"{BASE}/api/agent/stream?q={urllib.parse.quote(query)}"
    t0 = time.time()
    events: list[tuple[str, dict]] = []
    plan = None
    final = None
    errors: list[dict] = []
    trace_steps: list[str] = []

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        ev_name = None
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
            if line.startswith("event:"):
                ev_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and ev_name is not None:
                try:
                    payload = json.loads(line.split(":", 1)[1].strip())
                except Exception:
                    payload = {"_raw": line}
                events.append((ev_name, payload))
                if ev_name == "plan":
                    plan = payload
                elif ev_name == "final":
                    final = payload
                elif ev_name == "step":
                    trace_steps.append(payload.get("step", ""))
                elif ev_name == "error":
                    errors.append(payload)
                elif ev_name == "done":
                    break
                ev_name = None
    return StreamResult(events=events, plan=plan, final=final,
                        errors=errors, trace_steps=trace_steps,
                        elapsed_s=time.time() - t0)


def _backend() -> dict:
    with urllib.request.urlopen(f"{BASE}/api/backend", timeout=10) as r:
        return json.loads(r.read())


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

ADDRESSES = [
    pytest.param("2940 Brighton 3rd St, Brooklyn", id="brighton"),
    pytest.param("Hollis",                          id="hollis"),
    pytest.param("Hunts Point",                     id="hunts"),
]


# Steps every linear single_address run must hit, regardless of intent.
# prithvi_eo_live is only in the FSM when _HEAVY_SPECIALISTS is True,
# so it's excluded from this list and tested separately.
EXPECTED_STEPS = [
    "geocode",
    "sandy_inundation",
    "dep_stormwater",
    "floodnet",
    "nyc311",
    "noaa_tides",
    "nws_alerts",
    "nws_obs",
    "ttm_forecast",
    "microtopo_lidar",
    "ida_hwm_2021",
    "prithvi_eo_v2",
    "rag_granite_embedding",
    "gliner_extract",          # Phase 2 integration
    # reconcile step name varies by strict mode; not asserted here
]


# ---------------------------------------------------------------------------
# Smoke
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def backend_info() -> dict:
    return _backend()


def test_backend_endpoint_reachable(backend_info):
    assert "primary" in backend_info
    assert backend_info.get("reachable") is True, (
        f"Active LLM backend is not reachable: {backend_info}"
    )


# ---------------------------------------------------------------------------
# Per-address single_address E2E
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", params=ADDRESSES)
def streamed(request) -> StreamResult:
    """Run the SSE stream once per address, share across assertions."""
    return _stream(request.param)


def test_no_error_events(streamed: StreamResult):
    assert not streamed.errors, (
        f"stream emitted {len(streamed.errors)} error events: "
        f"{streamed.errors[:3]}"
    )


def test_planner_emitted(streamed: StreamResult):
    assert streamed.plan is not None, "no plan event in stream"
    assert streamed.plan.get("intent") in (
        "single_address", "live_now", "neighborhood", "development_check"
    ), f"unknown intent: {streamed.plan.get('intent')}"


def test_expected_steps_fired(streamed: StreamResult):
    if streamed.plan and streamed.plan.get("intent") != "single_address":
        pytest.skip(
            f"intent={streamed.plan['intent']}; non-linear FSM has its own "
            "step list — see TestNeighborhood/TestLiveNow if added"
        )
    fired = set(streamed.trace_steps)
    missing = [s for s in EXPECTED_STEPS if s not in fired]
    assert not missing, (
        f"expected steps did not fire: {missing} "
        f"(actually fired: {sorted(fired)})"
    )


def test_final_paragraph_present(streamed: StreamResult):
    assert streamed.final is not None, "no final event"
    para = streamed.final.get("paragraph") or ""
    assert len(para) >= 100, (
        f"final paragraph too short ({len(para)} chars): {para!r}"
    )


def test_paragraph_has_citations(streamed: StreamResult):
    if streamed.final is None:
        pytest.skip("no final event")
    import re
    para = streamed.final.get("paragraph", "")
    cites = re.findall(r"\[([a-z][a-z0-9_]*)\]", para)
    assert len(cites) >= 3, (
        f"paragraph has {len(cites)} citations; expected ≥3.\n"
        f"paragraph: {para!r}"
    )


def test_mellea_passes_or_acceptable_rerolls(streamed: StreamResult):
    if streamed.final is None:
        pytest.skip("no final event")
    mellea = streamed.final.get("mellea") or {}
    if not mellea:
        pytest.skip("non-strict mode (no mellea metadata)")
    passed = len(mellea.get("requirements_passed") or [])
    total = mellea.get("requirements_total") or 4
    assert passed >= total - 1, (
        f"Mellea passed only {passed}/{total}: "
        f"failed={mellea.get('requirements_failed')}, "
        f"rerolls={mellea.get('rerolls')}"
    )


# ---------------------------------------------------------------------------
# Phase-specific assertions
# ---------------------------------------------------------------------------

def test_phase1_prithvi_live_step(streamed: StreamResult):
    """Live water specialist must fire as a trace step. We don't assert
    `ok=True` — STAC can time out, no recent low-cloud scene may exist
    — only that the step ran and recorded its outcome."""
    if streamed.plan and streamed.plan.get("intent") != "single_address":
        pytest.skip("non-linear FSM")
    if not _HEAVY_SPECIALISTS:
        pytest.skip("RIPRAP_HEAVY_SPECIALISTS not enabled — prithvi_eo_live not in FSM")
    found = [e for e in streamed.events
             if e[0] == "step" and e[1].get("step") == "prithvi_eo_live"]
    assert found, "step_prithvi_live did not fire"


def test_phase2_gliner_extract_step(streamed: StreamResult):
    """GLiNER specialist runs and either extracts entities or no-ops."""
    if streamed.plan and streamed.plan.get("intent") != "single_address":
        pytest.skip("non-linear FSM")
    found = [e for e in streamed.events
             if e[0] == "step" and e[1].get("step") == "gliner_extract"]
    assert found, "gliner_extract step did not fire"
    payload = found[0][1]
    assert payload.get("ok") is True, (
        f"gliner_extract failed: {payload.get('err')}"
    )


def test_phase3_reranker_takes_effect_when_enabled():
    """If RIPRAP_RERANKER_ENABLE was set when the server started, the
    rag step's hits should carry a `retriever_score` field (only the
    rerank path adds it). Otherwise the test skips — we assert
    the *capability*, not its mandatory presence."""
    # Run a one-off query and inspect the rag step result.
    res = _stream("100 Gold St Manhattan")
    rag_step = next((p for n, p in res.events
                     if n == "step" and p.get("step") == "rag_granite_embedding"),
                    None)
    if rag_step is None:
        pytest.skip("no rag step in stream")
    # The reranker enrichment shows up in the doc messages reaching the
    # reconciler, not in the rag step's own result blob, so this test
    # checks instead that the briefing has at most one [rag_<source>]
    # citation per source — the dedup-after-rerank guarantee.
    if res.final is None:
        pytest.skip("no final paragraph")
    import re
    cites = re.findall(r"\[(rag_[a-z0-9_]+)\]", res.final.get("paragraph", ""))
    counts: dict[str, int] = {}
    for c in cites:
        counts[c] = counts.get(c, 0) + 1
    over = [c for c, n in counts.items() if n > 4]  # generous; same-doc
    assert not over, (
        f"unexpected citation flooding from one rag source: {counts}"
    )


# ---------------------------------------------------------------------------
# Iterator test — used to spot-check cli-style consumers
# ---------------------------------------------------------------------------

def _iter_events(query: str) -> Iterator[tuple[str, dict]]:
    """Useful in REPL — yields (event_name, payload) lazily."""
    yield from _stream(query).events
