"""
Shape assertion for the compare-intent SSE endpoint.

Validates that /api/agent/stream emits exactly one `final` event for a compare
query, with the structure that the SvelteKit compare layout depends on:

  final.intent  == "compare"
  final.targets == [{label, address}, {label, address}]   (exactly 2)
  final.paragraph contains "## PLACE A" and "## PLACE B" sections separated
                 by a markdown "---" divider
  each half of the paragraph contains at least one [citation] bracket

Run against a live local server:
    .venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860 &
    .venv/bin/python -m pytest tests/test_compare_shape.py -v
"""
from __future__ import annotations

import json
import re

import httpx
import pytest

BASE = "http://127.0.0.1:7860"
COMPARE_QUERY = "Compare 80 Pioneer Street Brooklyn to 100 Gold Street Manhattan"


def _parse_sse_stream(raw: str) -> list[dict]:
    """Parse raw SSE text into a list of {type, data} dicts."""
    events: list[dict] = []
    current: dict = {}
    for line in raw.splitlines():
        if line.startswith("event:"):
            current["type"] = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            raw_data = line.split(":", 1)[1].strip()
            try:
                current["data"] = json.loads(raw_data)
            except json.JSONDecodeError:
                current["data"] = raw_data
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events


@pytest.fixture(scope="module")
def compare_events() -> list[dict]:
    """Stream a compare query and return all parsed SSE events."""
    url = f"{BASE}/api/agent/stream"
    params = {"q": COMPARE_QUERY}
    try:
        with httpx.stream("GET", url, params=params, timeout=600.0) as resp:
            resp.raise_for_status()
            raw = resp.read().decode()
    except httpx.ConnectError:
        pytest.skip(f"Server not reachable at {BASE}")
    return _parse_sse_stream(raw)


def test_has_plan_with_compare_intent(compare_events):
    plans = [e for e in compare_events if e.get("type") == "plan"]
    assert len(plans) == 1, f"Expected 1 plan event, got {len(plans)}"
    plan = plans[0]["data"]
    assert plan.get("intent") == "compare", f"plan.intent={plan.get('intent')!r}"


def test_exactly_one_final_event(compare_events):
    finals = [e for e in compare_events if e.get("type") == "final"]
    assert len(finals) == 1, f"Expected 1 final event, got {len(finals)}"


def test_final_intent_is_compare(compare_events):
    final = next(e for e in compare_events if e.get("type") == "final")
    data = final["data"]
    assert data.get("intent") == "compare", f"final.intent={data.get('intent')!r}"


def test_final_targets_has_two_addresses(compare_events):
    final = next(e for e in compare_events if e.get("type") == "final")
    targets = final["data"].get("targets", [])
    assert len(targets) == 2, f"Expected 2 targets, got {len(targets)}: {targets}"
    for i, t in enumerate(targets):
        assert "address" in t, f"target[{i}] missing 'address' key: {t}"
        assert isinstance(t["address"], str) and t["address"].strip(), \
            f"target[{i}].address is blank: {t}"


def test_final_paragraph_has_both_place_sections(compare_events):
    final = next(e for e in compare_events if e.get("type") == "final")
    para = final["data"].get("paragraph", "")
    assert "## PLACE A" in para, "paragraph missing '## PLACE A' header"
    assert "## PLACE B" in para, "paragraph missing '## PLACE B' header"
    assert "---" in para, "paragraph missing '---' divider between places"


def test_each_place_section_has_at_least_one_citation(compare_events):
    final = next(e for e in compare_events if e.get("type") == "final")
    para = final["data"].get("paragraph", "")

    # Split at the markdown divider between PLACE A and PLACE B.
    parts = re.split(r"\n\s*---\s*\n", para, maxsplit=1)
    assert len(parts) == 2, f"Could not split paragraph at '---': got {len(parts)} parts"

    cite_re = re.compile(r"\[[a-z][a-z0-9_]*\]", re.IGNORECASE)
    for i, part in enumerate(parts):
        label = "PLACE A" if i == 0 else "PLACE B"
        cites = cite_re.findall(part)
        assert len(cites) >= 1, f"{label} section has no [citation] brackets"
