"""Riprap query planner — Granite 4.1 routes a natural-language query
to one of several intents and selects which specialists to invoke.

This is the agentic kernel: instead of running every specialist on
every query, the planner reads the query and emits a structured plan.
The executor then runs only the relevant specialists, in parallel
where dependencies permit.

Output is a single JSON object with a fixed schema (see PLAN_SCHEMA).
We use Ollama's `format='json'` constrained-decoding mode so Granite
4.1 cannot emit malformed structure. A deterministic post-validator
sanity-checks the plan against the supported intents and specialists.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from app import llm

log = logging.getLogger("riprap.planner")

# Routing is a small structured-output task; speed wins over depth here.
# Pin to the 3b variant explicitly — even if a deployment pulls 8b for
# reconciliation, the planner stays small to keep TTFB low.
OLLAMA_MODEL = os.environ.get("RIPRAP_PLANNER_MODEL",
                              os.environ.get("RIPRAP_OLLAMA_MODEL", "granite4.1:3b"))

# ---- Plan schema -----------------------------------------------------------
#
# The set of intents Riprap currently supports. Every plan picks exactly
# one; the executor maps intent → action graph in app/intents/.

INTENTS = {
    "single_address": (
        "Use when the query refers to a SPECIFIC LOCATABLE POINT — either "
        "(a) a street address with house number + street name (e.g. "
        "'116-50 Sutphin Blvd', '350 5th Ave Manhattan'), or (b) a named "
        "development, complex, or housing project that geocodes to a single "
        "location (e.g. 'Coney Island I Houses', 'Carleton Manor Houses', "
        "'Vladeck Houses'). If the query names only a general neighborhood "
        "or borough with no specific address or named building, use "
        "'neighborhood'."
    ),
    "neighborhood": (
        "Use when the query names a NEIGHBORHOOD or BOROUGH with no "
        "specific street address (e.g. 'Brighton Beach', 'Carroll "
        "Gardens', 'Brooklyn', 'is Red Hook at risk?', 'show me Hollis "
        "flooding'). Skip geocoding; resolve to NTA polygon(s) and run "
        "polygon-level specialists."
    ),
    "live_now": (
        "User asked about CURRENT CONDITIONS in NYC (e.g. 'is there "
        "flooding right now', 'what's the surge tonight'). Skip historic "
        "and modeled specialists; focus on live-data specialists."
    ),
    "development_check": (
        "User asked about CURRENT/IN-PROGRESS CONSTRUCTION OR DEVELOPMENT "
        "in a place, with implicit interest in flood risk for those projects "
        "(e.g. 'what are they building in Gowanus and is it risky?', "
        "'show me new construction in flood zones', 'are there projects "
        "underway in Red Hook?'). Resolve target to NTA polygon, pull active "
        "DOB construction permits inside it, cross-reference each project "
        "with Sandy + DEP flood layers, return a flagged-projects list."
    ),
    "compare": (
        "Use ONLY when the query explicitly compares TWO specific street "
        "ADDRESSES (e.g. 'compare 80 Pioneer St Brooklyn to 100 Gold St "
        "Manhattan', 'which is riskier: X or Y?', 'X vs Y flood risk'). "
        "Extract BOTH full street addresses into targets as two separate "
        "{type: 'address', text: ...} objects. Run the full single-address "
        "specialist suite for each."
    ),
}

SPECIALISTS = {
    # name: (description, which intents may invoke it)
    "geocode":       ("Resolve address text to lat/lon via NYC DCP Geosearch.",     ["single_address", "compare"]),
    "nta_resolve":   ("Resolve a neighborhood or borough name to NTA polygon(s).",  ["neighborhood"]),
    "sandy":         ("2012 Sandy inundation extent (point-in-polygon or % of NTA).", ["single_address", "neighborhood", "compare"]),
    "dep_stormwater":("DEP Stormwater Maps — 3 modeled scenarios.",                ["single_address", "neighborhood", "compare"]),
    "floodnet":      ("Live FloodNet ultrasonic sensors + trigger history.",      ["single_address", "neighborhood", "live_now", "compare"]),
    "nyc311":        ("NYC 311 flood-related complaints in buffer or polygon.",    ["single_address", "neighborhood", "compare"]),
    "noaa_tides":    ("Live NOAA Battery / Kings Pt / Sandy Hook water level.",   ["single_address", "neighborhood", "live_now", "compare"]),
    "nws_alerts":    ("Live NWS active flood-relevant alerts at point.",           ["single_address", "neighborhood", "live_now", "compare"]),
    "npcc4_slr":     ("NPCC4 (2024) sea-level rise projections at the Battery — 2050/2100 low/mid/high/extreme.", ["single_address", "neighborhood", "compare"]),
    "nws_obs":       ("Live NWS hourly precip from nearest ASOS station.",         ["single_address", "neighborhood", "live_now", "compare"]),
    "ttm_forecast":  ("Granite TTM r2 surge-residual nowcast at the Battery.",     ["single_address", "neighborhood", "live_now", "compare"]),
    "microtopo":     ("LiDAR-derived terrain (HAND, TWI, percentile) at point or aggregated over polygon.", ["single_address", "neighborhood", "compare"]),
    "ida_hwm":       ("USGS Hurricane Ida 2021 high-water marks proximity.",       ["single_address", "neighborhood", "compare"]),
    "prithvi":       ("Prithvi-EO 2.0 Hurricane Ida 2021 satellite flood polygons.", ["single_address", "neighborhood", "compare"]),
    "rag":           ("Retrieve relevant agency-report passages over the policy corpus.", ["single_address", "neighborhood", "development_check", "compare"]),
    "dob_permits":   ("Active NYC DOB construction permits inside a polygon, each cross-referenced with Sandy + DEP flood scenarios. Use for 'what are they building' / 'projects in progress' queries.", ["development_check"]),
}


@dataclass
class Plan:
    intent: str
    targets: list[dict[str, str]]
    specialists: list[str]
    rationale: str


PLAN_SCHEMA_DESC = """The output JSON must have exactly these keys:

{
  "intent": one of [single_address, neighborhood, live_now, development_check],
  "targets": [
    // one or more target objects, each with:
    //   {"type": "address", "text": "<address text>"}    when intent=single_address
    //   {"type": "nta",     "text": "<neighborhood>"}    when intent=neighborhood
    //   {"type": "borough", "text": "<borough>"}         when intent=neighborhood (boro-wide)
    //   {"type": "nyc",     "text": "NYC"}               when intent=live_now (no specific place)
  ],
  "specialists": [list of specialist names from the SPECIALISTS catalog the executor should run],
  "rationale": "<one sentence: why this intent + this set of specialists>"
}

Hard rules:
- Pick ONE intent only.
- Specialists must be drawn from the catalog and must be applicable to the chosen intent.
- For intent=single_address: ALWAYS include "geocode". Typically include all static + live specialists.
- For intent=neighborhood: ALWAYS include "nta_resolve". Skip "geocode". Include polygon-capable specialists.
- For intent=live_now: ONLY live specialists. Skip historic/modeled (sandy, dep_*, ida_hwm, prithvi).
- For intent=development_check: ALWAYS include "nta_resolve" AND "dob_permits". Sandy + DEP are also useful so the model can compare project locations to flood layers.
- For intent=compare: ALWAYS include "geocode". Extract BOTH street addresses into targets — the executor runs the full specialist suite once per address. Targets must be exactly 2 items, both type="address".
- IMPORTANT — TARGETS: extract neighborhood/borough names directly from the query text. If the query says "in Gowanus", "what about Brighton Beach", "around Carroll Gardens", etc., the target MUST be {"type": "nta", "text": "<the place name>"}. Use {"type": "nyc"} ONLY when the query mentions NYC as a whole and no specific place. Failing to extract a place name will cause the executor to give up — be explicit.
- "targets" is a list because the user may name multiple places (e.g. "compare Brighton Beach and Coney Island").
- "rationale" is one short sentence — what your reasoning was.
"""


SYSTEM_PROMPT = f"""You are Riprap's query planner. You read a user's natural-language flood-risk query and emit a structured execution plan.

You do NOT have access to any data. You only decide which intent fits the query and which specialists are relevant. Another component (the executor) will run the specialists.

Available intents:
{chr(10).join(f"  - {k}: {v}" for k, v in INTENTS.items())}

Available specialists (and which intents they apply to):
{chr(10).join(f"  - {name}: {desc} (intents: {', '.join(intents)})" for name, (desc, intents) in SPECIALISTS.items())}

{PLAN_SCHEMA_DESC}

Output ONLY the JSON object. No commentary, no markdown. The "rationale" field MUST be ONE SHORT SENTENCE (under 20 words). Stop immediately after the closing brace."""


# ---- Not-implemented short-circuits ----------------------------------------
#
# These patterns are well-defined feature gaps. Returning a graceful message
# is better than routing them into an intent that silently fails.

_RETROSPECTIVE_RE = re.compile(
    r"(?:what\s+would\s+(?:riprap|you|it)\s+have\s+said"
    r"|what\s+(?:was|were)\s+(?:the\s+)?(?:flood|risk|status)"
    r"|(?:as\s+of|on)\s+(?:august|september|october|november|december|january|"
    r"february|march|april|may|june|july)\s+\d"
    r"|on\s+(?:the\s+date\s+of|hurricane\s+ida|hurricane\s+sandy)"
    r"|(?:september|august|october)\s+\d{1,2},?\s+20\d{2}"
    r")",
    re.IGNORECASE,
)

_RANKING_RE = re.compile(
    r"(?:rank\s+(?:the\s+)?top\s+\d"
    r"|top\s+\d+\s+\w+\s+by\s+flood"
    r"|intersect(?:ed)?\s+with\s+(?:dac|ejnyc|social\s+vulnerability)"
    r"|sort(?:ed)?\s+by\s+(?:flood\s+)?(?:exposure|risk|score)"
    r")",
    re.IGNORECASE,
)

NOT_IMPLEMENTED_INTENTS = {
    "retrospective": (
        _RETROSPECTIVE_RE,
        "Historical-date mode (\"what would Riprap have said on [date]\") "
        "is on the roadmap but not yet available. Riprap currently reports "
        "present-state flood exposure; past-state reconstruction is planned "
        "for a future release (see deck slide 8).",
    ),
    "ranking": (
        _RANKING_RE,
        "Cross-development ranking queries (\"rank top N by flood exposure\", "
        "\"intersect with DAC designation\") require a cross-register join "
        "that is on the roadmap but not yet available. Try a specific address "
        "or neighborhood instead.",
    ),
}


def _not_implemented_message(query: str) -> str | None:
    """Return a user-facing message if the query matches a known feature gap,
    else None."""
    for _name, (pattern, message) in NOT_IMPLEMENTED_INTENTS.items():
        if pattern.search(query):
            return message
    return None


# ---- Planner call ----------------------------------------------------------

def plan(query: str, model: str = OLLAMA_MODEL, on_token=None) -> Plan:
    """Ask Granite 4.1 to plan a query. Returns a validated Plan.

    If on_token is provided, the planner runs in streaming mode and
    on_token(delta) is called for each chunk of the JSON output as
    Granite generates. The streaming endpoint uses this to show the
    agent's reasoning forming live in the UI.
    """
    msg = _not_implemented_message(query)
    if msg:
        log.info("planner: short-circuit not_implemented for query %r", query[:80])
        if on_token:
            on_token(json.dumps({"intent": "not_implemented", "message": msg}))
        return Plan(intent="not_implemented", targets=[],
                    specialists=[], rationale=msg)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": query},
    ]
    # Cap output — the plan JSON is tiny; an uncapped model can spin
    # forever in the rationale field and exhaust the stream timeout.
    _opts = {"temperature": 0, "num_predict": 512}
    if on_token is None:
        resp = llm.chat(model=model, messages=messages,
                           format="json", options=_opts)
        raw = resp["message"]["content"].strip()
    else:
        chunks: list[str] = []
        for chunk in llm.chat(model=model, messages=messages,
                                 format="json", stream=True,
                                 options=_opts):
            delta = (chunk.get("message") or {}).get("content") or ""
            if delta:
                chunks.append(delta)
                on_token(delta)
        raw = "".join(chunks).strip()
    log.info("planner raw: %s", raw[:400])
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        # Model hit num_predict ceiling mid-JSON — try salvaging with a
        # truncated-JSON repair: strip to last valid closing brace.
        trimmed = raw
        for i in range(len(raw) - 1, -1, -1):
            if raw[i] == "}":
                trimmed = raw[:i + 1]
                break
        try:
            d = json.loads(trimmed)
            log.warning("planner JSON repaired by trimming to last '}'")
        except json.JSONDecodeError as e2:
            raise ValueError(f"planner emitted non-JSON: {raw[:200]!r}") from e2
    return _validate(d, raw_query=query)


def _validate(d: dict[str, Any], raw_query: str) -> Plan:  # TODO(cleanup): cc-grade-D (23)
    """Defensive parse + sanitize. The model might pick an invalid intent
    or a specialist that isn't applicable; fall back to single_address
    with the raw query as the address (the most common case)."""
    intent = d.get("intent")
    if intent not in INTENTS:
        log.warning("planner picked invalid intent %r; defaulting to single_address", intent)
        intent = "single_address"

    raw_targets = d.get("targets") or []
    targets: list[dict[str, str]] = []
    for t in raw_targets:
        if not isinstance(t, dict):
            continue
        t_type = t.get("type")
        t_text = (t.get("text") or "").strip()
        if not t_text or t_type not in ("address", "nta", "borough", "nyc"):
            continue
        targets.append({"type": t_type, "text": t_text})
    if not targets:
        # Reasonable fallback: assume the raw query IS the target
        if intent == "single_address":
            targets = [{"type": "address", "text": raw_query}]
        elif intent == "neighborhood":
            targets = [{"type": "nta", "text": raw_query}]
        elif intent == "compare":
            # Planner failed to extract two addresses — treat whole query as
            # single address so the caller gets at least one result rather
            # than a confusing empty response.
            log.warning("compare intent but no valid targets extracted; "
                        "falling back to single raw query")
            targets = [{"type": "address", "text": raw_query}]
        else:
            targets = [{"type": "nyc", "text": "NYC"}]

    raw_specialists = d.get("specialists") or []
    specialists: list[str] = []
    for s in raw_specialists:
        if isinstance(s, str) and s in SPECIALISTS:
            _, applicable = SPECIALISTS[s]
            if intent in applicable:
                specialists.append(s)
    # Enforce a floor: each intent has canonical specialists that should
    # always run. The planner picks ADDITIONS; we ensure the minimum.
    required = _required_specialists(intent)
    added = [s for s in required if s not in specialists]
    if added:
        log.info("planner missed required %s for intent=%s; adding", added, intent)
        specialists = list(dict.fromkeys(specialists + required))
    if not specialists:
        specialists = _default_specialists(intent)

    rationale = (d.get("rationale") or "").strip()[:300] or "(no rationale provided)"
    return Plan(intent=intent, targets=targets, specialists=specialists, rationale=rationale)


def _required_specialists(intent: str) -> list[str]:
    """Floor: specialists that are ALWAYS run for an intent regardless of
    what the planner emitted. Captures load-bearing signals the planner
    sometimes forgets (sandy / dep for neighborhood; geocode for address)."""
    if intent == "single_address":
        return ["geocode", "sandy", "dep_stormwater", "microtopo"]
    if intent == "neighborhood":
        return ["nta_resolve", "sandy", "dep_stormwater", "nyc311"]
    if intent == "live_now":
        return ["nws_alerts", "noaa_tides"]
    if intent == "development_check":
        return ["nta_resolve", "dob_permits", "sandy", "dep_stormwater"]
    if intent == "compare":
        return ["geocode", "sandy", "dep_stormwater", "microtopo"]
    return []


def _default_specialists(intent: str) -> list[str]:
    if intent in ("single_address", "compare"):
        return ["geocode", "sandy", "dep_stormwater", "floodnet", "nyc311",
                "noaa_tides", "nws_alerts", "nws_obs", "ttm_forecast",
                "microtopo", "ida_hwm", "prithvi", "rag"]
    if intent == "neighborhood":
        return ["nta_resolve", "sandy", "dep_stormwater", "nyc311",
                "microtopo", "rag"]
    if intent == "live_now":
        return ["noaa_tides", "nws_alerts", "nws_obs", "ttm_forecast", "floodnet"]
    return []
