"""Riprap stakeholder integration suite.

Drives `/api/agent/stream` against 20 queries derived from RESEARCH.md
(six anchored personas, six adapted variants, eight lateral use cases)
and records, for each:

  - planner intent
  - Stones invoked / fired / silent_by_design / errored
  - wall-clock time per Stone and total
  - briefing prose + citation count
  - Mellea grounding pass/4 + rerolls
  - a programmatic framing score (1-5) for the opening paragraph,
    measured against a per-question-type rubric

Outputs land in `tests/integration/results/<DATE>/`:
  - q{NN}-{slug}.json  — full per-query payload
  - SUMMARY.md          — table of all 20 (intent, time, grounding, framing)
  - FAILURES.md         — full briefings + proximate causes for failures

Usage:
    .venv/bin/python tests/integration/stakeholder_queries.py
    .venv/bin/python tests/integration/stakeholder_queries.py \\
        --base http://127.0.0.1:7860 --out tests/integration/results/2026-05-06
    .venv/bin/python tests/integration/stakeholder_queries.py \\
        --only 1,2,3 --timeout 600

Per-query timeout defaults to 600 s (10 min) per Adam's instruction —
log + move on past that.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

# ---- 20-query suite -------------------------------------------------------

# Each query carries:
#   id            : 01..20 (used in filename)
#   slug          : short kebab-case label
#   query         : the verbatim user query (DO NOT rewrite into address form)
#   persona       : human label for who's asking
#   question_type : key into FRAMING_RUBRICS
#   expected_intent : the planner intent we expect (None = no expectation;
#                     used to flag classifier drift but not as a hard fail)
#   anchor        : 'verbatim' | 'adapted' | 'lateral' — provenance in
#                   RESEARCH.md
#   notes         : free-form note about what makes this query interesting

QUERIES: list[dict[str, Any]] = [
    # --- ANCHORED (verbatim from RESEARCH.md) ---
    {
        "id": "01", "slug": "resident-pioneer",
        "query": "I'm thinking about renting an apartment at 80 Pioneer Street, Brooklyn. Should I worry?",
        "persona": "Resident / homebuyer (Pioneer)",
        "question_type": "habitability_decision",
        "expected_intent": "single_address",
        "anchor": "verbatim",
        "notes": "FloodHelpNY swap-in. Red Hook canonical Sandy turf.",
    },
    {
        "id": "02", "slug": "attorney-gold",
        "query": "Does 100 Gold Street, Manhattan need to disclose flood risk under RPL §462(2)?",
        "persona": "Real-estate attorney (Gold)",
        "question_type": "legal_disclosure",
        "expected_intent": "single_address",
        "anchor": "verbatim",
        "notes": "Negative-control on Sandy. Disclosure framing is the test.",
    },
    {
        "id": "03", "slug": "planner-hollis",
        "query": "Hollis, Queens",
        "persona": "NYC OEM/DEP planner (Hollis)",
        "question_type": "capital_planning",
        "expected_intent": "neighborhood",
        "anchor": "verbatim",
        "notes": "Bare neighborhood input. Capital-planning frame is the test.",
    },
    {
        "id": "04", "slug": "underwriter-houston",
        "query": "442 East Houston Street, Manhattan",
        "persona": "Insurance underwriter (Houston)",
        "question_type": "underwriting",
        "expected_intent": "single_address",
        "anchor": "verbatim",
        "notes": "Bare address. Audit-chain framing is the test.",
    },
    {
        "id": "05", "slug": "journalist-coney",
        "query": "Coney Island, Brooklyn",
        "persona": "Climate journalist (Coney Island)",
        "question_type": "journalism",
        "expected_intent": "neighborhood",
        "anchor": "verbatim",
        "notes": "Editorial / data-journalism frame.",
    },
    {
        "id": "06", "slug": "developer-gowanus",
        "query": "What are they building in Gowanus and is it risky",
        "persona": "Architect / developer (Gowanus)",
        "question_type": "development_siting",
        "expected_intent": "development_check",
        "anchor": "verbatim",
        "notes": "DOB filings + flood layers. Siting frame is the test.",
    },

    # --- ADAPTED VARIATIONS (same shape, different addresses) ---
    {
        "id": "07", "slug": "resident-grand-disclosure",
        "query": "I just got a lease for 504 Grand Street, Lower East Side. The landlord says no flood history. Is that true?",
        "persona": "Resident, disclosure-suspicion (Grand)",
        "question_type": "habitability_decision",
        "expected_intent": "single_address",
        "anchor": "adapted",
        "notes": "Tests whether the briefing engages the user's premise (landlord said X) head-on.",
    },
    {
        "id": "08", "slug": "planner-hammels",
        "query": "Hammels Houses, Rockaway",
        "persona": "NYCHA-in-flood-zone planner (Hammels)",
        "question_type": "capital_planning",
        "expected_intent": "neighborhood",
        "anchor": "adapted",
        "notes": "NYCHA × flood — capital-planning frame at NTA scale.",
    },
    {
        "id": "09", "slug": "mta-coney-vs-brighton",
        "query": "Should the MTA prioritize hardening the Coney Island-Stillwell Av subway entrance over Brighton Beach?",
        "persona": "MTA capital planner",
        "question_type": "comparison",
        "expected_intent": None,
        "anchor": "adapted",
        "notes": "Comparison question; the planner may classify as neighborhood. Verdict-style framing is the test.",
    },
    {
        "id": "10", "slug": "planner-redhook",
        "query": "Red Hook",
        "persona": "Planner — NYCHA + Sandy memory (Red Hook)",
        "question_type": "capital_planning",
        "expected_intent": "neighborhood",
        "anchor": "adapted",
        "notes": "Bare neighborhood. Sandy + NYCHA exposure overlay.",
    },
    {
        "id": "11", "slug": "doe-ps188",
        "query": "PS 188, Lower East Side",
        "persona": "DOE school siting (PS 188)",
        "question_type": "development_siting",
        "expected_intent": None,
        "anchor": "adapted",
        "notes": "Geocoder ambiguity (Brooklyn vs Manhattan PS 188). Disambiguation handling is the test — silence over confabulation expected if ambiguous.",
    },
    {
        "id": "12", "slug": "planner-bpc-protected",
        "query": "Battery Park City",
        "persona": "Planner — protected neighborhood (BPC)",
        "question_type": "capital_planning",
        "expected_intent": "neighborhood",
        "anchor": "adapted",
        "notes": "Has known protection infrastructure (BPC Resiliency). Protection-shadow case.",
    },

    # --- LATERAL USE CASES (RESEARCH.md §"Lateral and unexpected") ---
    {
        "id": "13", "slug": "grant-twobridges-cdbg",
        "query": "Generate the vulnerability assessment section for a HUD CDBG-DR application for the Two Bridges NTA, Manhattan.",
        "persona": "Climate-grant evidence (Two Bridges)",
        "question_type": "grant_evidence",
        "expected_intent": "neighborhood",
        "anchor": "lateral",
        "notes": "Tests whether the briefing aligns to a vulnerability-assessment shape rather than a generic Status section.",
    },
    {
        "id": "14", "slug": "retrospective-hollis-ida",
        "query": "What would Riprap have said about Hollis on August 31, 2021, the day before Ida?",
        "persona": "Time-machine retrospective (Hollis pre-Ida)",
        "question_type": "retrospective",
        "expected_intent": None,
        "anchor": "lateral",
        "notes": "Time-machine variant. Should declare the historical-snapshot mode is not wired rather than silently answer with current data.",
    },
    {
        "id": "15", "slug": "ejnyc-nycha-ranking",
        "query": "Rank the top 5 NYCHA developments by flood exposure, intersected with DAC designation.",
        "persona": "EJNYC × Riprap pairing",
        "question_type": "comparison",
        "expected_intent": None,
        "anchor": "lateral",
        "notes": "Multi-target ranking; not currently exposed as a single-shot intent. Failure mode analysis is the value here.",
    },
    {
        "id": "16", "slug": "floodnet-bk018-livenow",
        "query": "FloodNet sensor BK-018 just triggered. What's at stake in the next six hours within 500 m?",
        "persona": "FloodNet alert federation (BK-018)",
        "question_type": "emergency_response",
        "expected_intent": "live_now",
        "anchor": "lateral",
        "notes": "live_now intent + emergency-response framing.",
    },
    {
        "id": "17", "slug": "compare-pioneer-grand",
        "query": "Compare 80 Pioneer Street, Brooklyn to 504 Grand Street, Manhattan for flood exposure.",
        "persona": "Compare intent (Pioneer vs Grand)",
        "question_type": "comparison",
        "expected_intent": None,
        "anchor": "lateral",
        "notes": "Compare intent isn't currently exposed in the planner; will likely fall back to single_address with one of the two.",
    },
    {
        "id": "18", "slug": "court-houston-ida",
        "query": "Court exhibit: flood-exposure narrative for 442 East Houston Street on the date of Hurricane Ida, September 1, 2021.",
        "persona": "Court testimony (Houston × Ida)",
        "question_type": "retrospective",
        "expected_intent": "single_address",
        "anchor": "lateral",
        "notes": "Date-bounded retrospective on a known address. Should either snapshot or be explicit about not snapshotting.",
    },
    {
        "id": "19", "slug": "bbmcr-protection-envelope",
        "query": "Brooklyn-Bridge Montgomery Coastal Resiliency project area. What's the protection envelope and what's outside it?",
        "persona": "Capital planning, protection-shadow (BBMCR)",
        "question_type": "capital_planning",
        "expected_intent": "neighborhood",
        "anchor": "lateral",
        "notes": "Project-area framing; tests whether the briefing engages 'inside vs outside protection' as a structuring concept.",
    },
    {
        "id": "20", "slug": "control-astoria",
        "query": "Astoria, Queens",
        "persona": "Neighborhood control case (Astoria)",
        "question_type": "journalism",
        "expected_intent": "neighborhood",
        "anchor": "lateral",
        "notes": "Relatively low-exposure neighborhood. Tests handling of 'mostly fine' without confabulating risk.",
    },
]


# ---- Framing rubric -------------------------------------------------------

# For each question_type, define heuristic markers that distinguish a
# question-aware opening from a generic Status section.
#
# Score 1-5:
#   5 — opening explicitly addresses the user's question shape with a
#       direct verdict word (e.g. "Yes,", "No,", "Disclosure is required",
#       "Hardening Coney Island ranks higher", "Vulnerability assessment").
#   4 — opening references the user's question topic but stops short of
#       a verdict.
#   3 — opening is generic Status with the user's place named.
#   2 — opening is generic Status, place not named, but on-topic.
#   1 — opening fails to engage the question at all (or briefing absent).
#
# The scoring function is conservative: it returns the highest tier whose
# markers ALL match. If the prose is empty, score is 0.

FRAMING_RUBRICS: dict[str, dict[str, Any]] = {
    "habitability_decision": {
        "verdict_markers": [
            r"\b(yes|no)\b[,.]",
            r"should\s+(worry|be cautious|consider)",
            r"\b(habitable|safe to (rent|live|move))",
            r"flood (history|record) (does|is|shows|exists|confirms|contradicts)",
            r"landlord('s)?\s+(claim|statement|assertion)",
        ],
        "topic_markers": [
            r"renting|lease|moving in|live at|tenant|resident",
            r"should you (worry|consider)",
            r"flood (risk|history|exposure) (at|for) (this|the)",
        ],
        "place_only": [r"this address|this location|this property"],
    },
    "legal_disclosure": {
        "verdict_markers": [
            r"\b(disclosure|disclose) (is )?(required|not required|triggered|warranted)",
            r"\b(yes|no)\b[,.]",
            r"RPL\s*§?\s*\d+",
            r"under (the )?(law|statute|RPL|Real Property)",
            r"(must|should|need to) (disclose|be disclosed)",
        ],
        "topic_markers": [
            r"disclosure|disclose|seller|landlord|RPL|Property Condition",
            r"legal (obligation|requirement|standard)",
        ],
        "place_only": [r"this address|this property"],
    },
    "capital_planning": {
        "verdict_markers": [
            r"\b(prioritize|priority|highest|ranks|ranks (first|second|highest))",
            r"capital (plan|investment|spending|allocation)",
            r"recommend(s|ed)? (hardening|investment|prioriti[sz]ation)",
            r"top (priority|target|candidate)",
            r"(should|merits) (be )?(prioritized|targeted|funded)",
        ],
        "topic_markers": [
            r"planning|investment|infrastructure|hardening|resilien(ce|cy)",
            r"prioriti[sz]ation|allocation",
        ],
        "place_only": [r"this neighborhood|this NTA"],
    },
    "underwriting": {
        "verdict_markers": [
            r"audit (chain|trail|record)",
            r"underwrit(ing|er|able)",
            r"actuarial",
            r"loss history|claim(s)? history",
            r"insurabl[ey]",
            r"each (claim|figure|number) (cited|grounded|sourced)",
        ],
        "topic_markers": [
            r"insurance|premium|risk profile|loss",
            r"sources (cited|listed|named)",
        ],
        "place_only": [r"this address|this property"],
    },
    "journalism": {
        "verdict_markers": [
            r"reproducib(le|ility)",
            r"each (claim|figure|number) (in this brief|cites)",
            r"every (number|claim) (in this|cites|grounded)",
            r"(story|narrative|reporting) (about|on)",
        ],
        "topic_markers": [
            r"newsroom|reporting|story|coverage",
            r"sources (cited|listed)",
        ],
        "place_only": [r"this neighborhood|this NTA"],
    },
    "development_siting": {
        "verdict_markers": [
            r"\b(yes|no|risky|safe to build|inadvisable)\b[,.]",
            r"\b(\d+)\s+(active|proposed|filed) (project|filing|permit)",
            r"sit(es?|ing) (inside|outside|within|intersect)",
            r"sit(es?|ing) (recommendation|caution|concern)",
            r"under construction (inside|in the|at)",
        ],
        "topic_markers": [
            r"construction|development|filing|permit|DOB",
            r"build|building|project sites?",
        ],
        "place_only": [r"this neighborhood|this NTA"],
    },
    "grant_evidence": {
        "verdict_markers": [
            r"vulnerabilit(y|ies) (assessment|profile|evidence)",
            r"CDBG|HUD|BRIC|grant",
            r"(eligible|qualif(y|ies)) for (funding|disaster)",
            r"this (assessment|section|narrative) (documents|establishes)",
        ],
        "topic_markers": [
            r"vulnerab(le|ility)|grant|application|funding|federal",
            r"disadvantaged",
        ],
        "place_only": [r"this NTA|this neighborhood"],
    },
    "retrospective": {
        "verdict_markers": [
            r"(historical|retrospective|time.?machine|snapshot) (mode|view|run|reconstruction)",
            r"(as of|on|prior to|before) (the|that) (date|day|storm|event)",
            r"(does not|cannot|isn't able to) (snapshot|reconstruct|replay|provide)",
            r"current (data|state|signals) (only|are used)",
        ],
        "topic_markers": [
            r"\b(Ida|Sandy|2021|2012|hurricane)\b",
            r"date|prior to|before|day before",
        ],
        "place_only": [r"this address|this neighborhood"],
    },
    "emergency_response": {
        "verdict_markers": [
            r"(within|inside) (the )?(next )?(\d+\s*(h|hour|hours)|six hours)",
            r"\bat (stake|risk) (within|in the next)",
            r"sensor (BK-?\d+|triggered)",
            r"(immediate|imminent|active) (response|risk|alert)",
        ],
        "topic_markers": [
            r"FloodNet|sensor|alert|trigger",
            r"hours|nowcast|live",
        ],
        "place_only": [r"this address|this area"],
    },
    "comparison": {
        "verdict_markers": [
            r"\b([A-Z][\w\s]{2,30})\s+(ranks|scores|exceeds|is greater|is more|is less)",
            r"compared (to|against)",
            r"(higher|lower|greater|larger|smaller) (exposure|risk|count)",
            r"(prefer|recommend|choose) (\w+) over",
        ],
        "topic_markers": [
            r"compare|comparison|vs\.?|versus|both",
        ],
        "place_only": [r"these (addresses|neighborhoods|sites)"],
    },
    "generic_exposure": {
        "verdict_markers": [],
        "topic_markers": [r"flood (exposure|risk|signal)"],
        "place_only": [r"this address|this neighborhood"],
    },
}


# ---- SSE driver -----------------------------------------------------------

@dataclass
class StoneTiming:
    name: str
    started_at: float | None = None
    ended_at: float | None = None
    n_steps: int = 0


@dataclass
class RunResult:
    qid: str
    slug: str
    query: str
    persona: str
    question_type: str
    expected_intent: str | None
    anchor: str

    started_at: float = 0.0
    ended_at: float = 0.0

    plan: dict[str, Any] = field(default_factory=dict)
    intent: str = ""
    paragraph: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    mellea_attempts: list[dict[str, Any]] = field(default_factory=list)
    final: dict[str, Any] = field(default_factory=dict)
    stone_timings: dict[str, dict[str, Any]] = field(default_factory=dict)

    error: str | None = None
    timed_out: bool = False
    transport_error: str | None = None

    framing_score: int = 0
    framing_rationale: str = ""

    @property
    def wall_clock_s(self) -> float:
        return round(self.ended_at - self.started_at, 2)


_STEP_TO_STONE: dict[str, str] = {
    "sandy_inundation": "Cornerstone", "dep_stormwater": "Cornerstone",
    "ida_hwm_2021": "Cornerstone", "prithvi_eo_v2": "Cornerstone",
    "microtopo_lidar": "Cornerstone", "sandy_nta": "Cornerstone",
    "dep_extreme_2080_nta": "Cornerstone", "dep_moderate_2050_nta": "Cornerstone",
    "dep_moderate_current_nta": "Cornerstone", "microtopo_nta": "Cornerstone",
    "mta_entrance_exposure": "Keystone", "nycha_development_exposure": "Keystone",
    "doe_school_exposure": "Keystone", "doh_hospital_exposure": "Keystone",
    "terramind_synthesis": "Keystone", "eo_chip_fetch": "Keystone",
    "terramind_buildings": "Keystone",
    "floodnet": "Touchstone", "nyc311": "Touchstone",
    "nws_obs": "Touchstone", "noaa_tides": "Touchstone",
    "prithvi_eo_live": "Touchstone", "terramind_lulc": "Touchstone",
    "nyc311_nta": "Touchstone",
    "nws_alerts": "Lodestone", "ttm_forecast": "Lodestone",
    "ttm_311_forecast": "Lodestone", "floodnet_forecast": "Lodestone",
    "ttm_battery_surge": "Lodestone",
    "reconcile_granite41": "Capstone", "mellea_reconcile_address": "Capstone",
    "reconcile_neighborhood": "Capstone", "reconcile_development": "Capstone",
    "reconcile_live_now": "Capstone",
}


def stream_one(base_url: str, query: str, timeout_s: float) -> tuple[dict[str, Any], str | None]:
    """Drive a single SSE run. Returns (collected_events_dict, error_or_None).

    The collected dict has keys:
      plan, paragraph, steps[], mellea_attempts[], final, stone_timings,
      transport_error, timed_out
    """
    url = base_url.rstrip("/") + "/api/agent/stream?q=" + quote(query)

    out: dict[str, Any] = {
        "plan": {},
        "paragraph": "",
        "steps": [],
        "mellea_attempts": [],
        "final": {},
        "stone_timings": {},
        "transport_error": None,
        "timed_out": False,
    }

    cur_event = ""
    paragraph_buf = ""
    last_attempt = 0
    stones: dict[str, dict[str, float | int]] = {}
    t0 = time.time()
    deadline = t0 + timeout_s

    try:
        with httpx.Client(timeout=httpx.Timeout(timeout_s, read=timeout_s)) as cli:
            with cli.stream("GET", url) as resp:
                resp.raise_for_status()
                for raw_line in resp.iter_lines():
                    if time.time() > deadline:
                        out["timed_out"] = True
                        break
                    line = raw_line if isinstance(raw_line, str) else raw_line.decode()
                    if not line:
                        cur_event = ""
                        continue
                    if line.startswith("event:"):
                        cur_event = line.split(":", 1)[1].strip()
                        continue
                    if not line.startswith("data:"):
                        continue
                    payload_raw = line.split(":", 1)[1].strip()
                    try:
                        payload = json.loads(payload_raw)
                    except json.JSONDecodeError:
                        continue

                    ev = cur_event
                    if ev == "plan":
                        out["plan"] = payload
                    elif ev == "step":
                        out["steps"].append(payload)
                        step_name = (payload.get("step") or "").lower()
                        stone = _STEP_TO_STONE.get(step_name)
                        if stone:
                            t_start = float(payload.get("started_at") or 0)
                            t_elapsed = float(payload.get("elapsed_s") or 0)
                            t_end = t_start + t_elapsed if t_start else time.time()
                            d = stones.setdefault(stone, {
                                "first_started_at": t_start or time.time(),
                                "last_ended_at": t_end,
                                "n_steps": 0,
                                "n_ok": 0,
                                "n_err": 0,
                            })
                            d["last_ended_at"] = max(d["last_ended_at"], t_end)
                            d["n_steps"] = int(d["n_steps"]) + 1
                            if payload.get("ok"):
                                d["n_ok"] = int(d["n_ok"]) + 1
                            else:
                                d["n_err"] = int(d["n_err"]) + 1
                    elif ev == "token":
                        attempt = payload.get("attempt", 0) or 0
                        if attempt != last_attempt:
                            paragraph_buf = ""
                            last_attempt = attempt
                        paragraph_buf += payload.get("delta") or ""
                    elif ev == "mellea_attempt":
                        out["mellea_attempts"].append(payload)
                    elif ev == "final":
                        out["final"] = payload
                        if isinstance(payload.get("paragraph"), str):
                            paragraph_buf = payload["paragraph"]
                    elif ev == "error":
                        return out, f"server error: {payload.get('err')}"
                    elif ev == "done":
                        break
    except httpx.HTTPError as e:
        out["transport_error"] = f"{type(e).__name__}: {e}"
        return out, out["transport_error"]

    out["paragraph"] = paragraph_buf

    for name, d in stones.items():
        out["stone_timings"][name] = {
            "n_steps": d["n_steps"],
            "n_ok": d["n_ok"],
            "n_err": d["n_err"],
            "wall_clock_s": round(float(d["last_ended_at"]) - float(d["first_started_at"]), 2),
        }

    return out, None


# ---- Framing scorer -------------------------------------------------------

_HEADER_RE = re.compile(r"\*\*[A-Z][A-Za-z\s/]+\.\*\*")
_CITE_RE = re.compile(r"\[[a-z0-9_]+\]", re.I)
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def _opening_text(paragraph: str) -> str:
    """Extract the opening ('Status' section) prose for scoring.

    Strips section headers, citation tokens, and bold markers. Returns
    the first 2 sentences of the body following the first **Status.**
    header (or, if no header, the first 2 sentences of the paragraph).
    """
    if not paragraph:
        return ""

    # Find body after the first **Status.** header (or any first header).
    body = paragraph
    m = re.search(r"\*\*Status\.?\*\*", paragraph, re.I)
    if m:
        body = paragraph[m.end():]
    # Stop at the next header so we only score the opening section.
    body = _HEADER_RE.split(body, maxsplit=1)[0]

    body = _CITE_RE.sub("", body)
    body = _BOLD_RE.sub(r"\1", body)
    body = body.strip()

    # Take first 2 sentences.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\[])", body)
    return " ".join(parts[:2]).strip()


def score_framing(query_def: dict[str, Any], paragraph: str) -> tuple[int, str]:
    """Return (score 0-5, one-sentence rationale).

    0: no paragraph
    1: paragraph present, no markers match at all
    2: on-topic words present but no place / verdict
    3: place referenced (e.g. 'this address') but generic Status framing
    4: question-topic markers match (engages the user's framing)
    5: at least one verdict marker matches (delivers an answer-shape)
    """
    qt = query_def.get("question_type", "generic_exposure")
    rubric = FRAMING_RUBRICS.get(qt) or FRAMING_RUBRICS["generic_exposure"]
    opening = _opening_text(paragraph)
    if not opening:
        return 0, "no opening prose to score"
    low = opening.lower()

    def any_match(patterns: list[str]) -> str | None:
        for p in patterns:
            if re.search(p, low, re.I):
                return p
        return None

    verdict_hit = any_match(rubric["verdict_markers"])
    topic_hit = any_match(rubric["topic_markers"])
    place_hit = any_match(rubric["place_only"])

    if verdict_hit:
        return 5, f"verdict marker matched: /{verdict_hit}/"
    if topic_hit:
        return 4, f"topic marker matched: /{topic_hit}/ (no verdict)"
    if place_hit:
        return 3, f"place reference only: /{place_hit}/"
    if re.search(r"flood|exposure|risk", low):
        return 2, "on-topic exposure language but no question-aware framing"
    return 1, "no markers matched; opening doesn't engage the question shape"


# ---- Run + report ---------------------------------------------------------

def run_one(base: str, q: dict[str, Any], timeout_s: float) -> RunResult:
    res = RunResult(
        qid=q["id"], slug=q["slug"], query=q["query"],
        persona=q["persona"], question_type=q["question_type"],
        expected_intent=q.get("expected_intent"), anchor=q["anchor"],
    )
    res.started_at = time.time()
    try:
        collected, err = stream_one(base, q["query"], timeout_s)
    except Exception:  # noqa: BLE001
        res.ended_at = time.time()
        res.error = traceback.format_exc()
        return res

    res.ended_at = time.time()
    res.plan = collected.get("plan") or {}
    res.intent = res.plan.get("intent") or ""
    res.paragraph = collected.get("paragraph") or ""
    res.steps = collected.get("steps") or []
    res.mellea_attempts = collected.get("mellea_attempts") or []
    res.final = collected.get("final") or {}
    res.stone_timings = collected.get("stone_timings") or {}
    res.timed_out = bool(collected.get("timed_out"))
    res.transport_error = collected.get("transport_error")
    if err and not res.error:
        res.error = err

    score, rationale = score_framing(q, res.paragraph)
    res.framing_score = score
    res.framing_rationale = rationale
    return res


def _mellea_summary(final: dict[str, Any]) -> dict[str, Any]:
    m = final.get("mellea") or {}
    if not m:
        return {"passed": 0, "total": 4, "rerolls": 0, "n_attempts": 0,
                "requirements_passed": [], "requirements_failed": []}
    passed = m.get("requirements_passed") or []
    failed = m.get("requirements_failed") or []
    return {
        "passed": len(passed),
        "total": int(m.get("requirements_total") or 4),
        "rerolls": int(m.get("rerolls") or 0),
        "n_attempts": int(m.get("n_attempts") or 0),
        "requirements_passed": passed,
        "requirements_failed": failed,
    }


def write_per_query_json(res: RunResult, out_dir: Path) -> Path:
    fp = out_dir / f"q{res.qid}-{res.slug}.json"
    payload = asdict(res)
    payload["wall_clock_s"] = res.wall_clock_s
    payload["mellea"] = _mellea_summary(res.final)
    payload["citations"] = sorted(set(_CITE_RE.findall(res.paragraph)))
    payload["citation_count"] = len(payload["citations"])
    fp.write_text(json.dumps(payload, indent=2, default=str))
    return fp


def write_summary(results: list[RunResult], out_dir: Path) -> Path:
    fp = out_dir / "SUMMARY.md"
    rows = []
    rows.append("# Stakeholder integration suite — summary")
    rows.append("")
    rows.append(f"Run at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    rows.append(f"Suite size: {len(results)} queries")
    n_pass = sum(1 for r in results if r.error is None and not r.timed_out)
    n_fail = sum(1 for r in results if r.error is not None)
    n_to = sum(1 for r in results if r.timed_out)
    rows.append(f"Outcomes: {n_pass} ok / {n_fail} errored / {n_to} timed-out")
    rows.append("")
    rows.append("Framing score: 0–5 (5 = opening directly answers the question shape; "
                "3 = generic Status with place named; 1 = no engagement).")
    rows.append("")
    rows.append("| # | Persona | Intent | Wall (s) | Stones | Mellea | Citations | Frame | Status |")
    rows.append("|---|---------|--------|---------:|--------|--------|----------:|------:|--------|")
    for r in results:
        m = _mellea_summary(r.final)
        n_stones = len(r.stone_timings)
        n_steps = len(r.steps)
        cites = sorted(set(_CITE_RE.findall(r.paragraph)))
        intent_disp = r.intent or "?"
        if r.expected_intent and r.intent and r.intent != r.expected_intent:
            intent_disp = f"{r.intent} (≠{r.expected_intent})"
        if r.error:
            status = "ERROR"
        elif r.timed_out:
            status = "TIMEOUT"
        elif not r.paragraph:
            status = "NO PROSE"
        elif m["passed"] < m["total"]:
            status = f"mellea {m['passed']}/{m['total']}"
        else:
            status = "ok"
        rows.append(
            f"| {r.qid} | {r.persona} | {intent_disp} | {r.wall_clock_s} | "
            f"{n_stones}({n_steps} steps) | {m['passed']}/{m['total']} (rr={m['rerolls']}) | "
            f"{len(cites)} | {r.framing_score} | {status} |"
        )

    rows.append("")
    rows.append("## Framing-score distribution")
    rows.append("")
    dist = {i: 0 for i in range(6)}
    for r in results:
        dist[r.framing_score] = dist.get(r.framing_score, 0) + 1
    for k, v in sorted(dist.items()):
        rows.append(f"- score {k}: {v} queries")

    rows.append("")
    rows.append("## Framing rationale per query")
    rows.append("")
    for r in results:
        rows.append(f"- **q{r.qid} ({r.slug})** [{r.framing_score}/5] — {r.framing_rationale}")

    fp.write_text("\n".join(rows) + "\n")
    return fp


def write_failures(results: list[RunResult], out_dir: Path) -> Path:
    fp = out_dir / "FAILURES.md"
    rows = ["# Failures"]
    rows.append("")
    bad = [r for r in results if r.error or r.timed_out or not r.paragraph
           or _mellea_summary(r.final)["passed"] < _mellea_summary(r.final)["total"]]
    if not bad:
        rows.append("_No failures._")
        fp.write_text("\n".join(rows) + "\n")
        return fp
    for r in bad:
        m = _mellea_summary(r.final)
        rows.append(f"## q{r.qid} — {r.persona}")
        rows.append("")
        rows.append(f"- query: `{r.query}`")
        rows.append(f"- intent: `{r.intent}` (expected `{r.expected_intent}`)")
        rows.append(f"- wall-clock: {r.wall_clock_s} s")
        rows.append(f"- mellea: {m['passed']}/{m['total']} (rerolls={m['rerolls']}, attempts={m['n_attempts']})")
        rows.append(f"- mellea failed: {m['requirements_failed']}")
        rows.append(f"- timed_out: {r.timed_out}; transport_error: {r.transport_error}")
        if r.error:
            rows.append("")
            rows.append("```")
            rows.append(str(r.error)[:2000])
            rows.append("```")
        rows.append("")
        if r.paragraph:
            rows.append("Briefing prose:")
            rows.append("")
            rows.append("```markdown")
            rows.append(r.paragraph[:3000])
            rows.append("```")
        else:
            rows.append("_(no prose)_")
        rows.append("")
    fp.write_text("\n".join(rows) + "\n")
    return fp


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://127.0.0.1:7860",
                   help="FastAPI server base URL")
    p.add_argument("--out", default=None, help="output dir")
    p.add_argument("--only", default="", help="comma-sep query ids to run (e.g. 1,3,7)")
    p.add_argument("--timeout", type=float, default=600.0,
                   help="per-query timeout seconds (default 600)")
    p.add_argument("--label", default="", help="label appended to filenames")
    args = p.parse_args()

    out_dir = Path(args.out) if args.out else (
        Path(__file__).parent / "results" / time.strftime("%Y-%m-%d")
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    only = set()
    if args.only:
        only = {x.strip().lstrip("0") for x in args.only.split(",")}

    queries = [q for q in QUERIES if not only or q["id"].lstrip("0") in only]
    print(f"[suite] base={args.base} out_dir={out_dir} queries={len(queries)} "
          f"timeout={args.timeout}s label={args.label!r}", file=sys.stderr)

    results: list[RunResult] = []
    for i, q in enumerate(queries, 1):
        t0 = time.time()
        print(f"[suite] ({i}/{len(queries)}) q{q['id']} {q['persona']!r}: "
              f"{q['query'][:80]!r}", file=sys.stderr)
        r = run_one(args.base, q, args.timeout)
        elapsed = time.time() - t0
        m = _mellea_summary(r.final)
        flag = "OK"
        if r.error:
            flag = "ERR"
        elif r.timed_out:
            flag = "TO "
        elif not r.paragraph:
            flag = "NOPRO"
        print(f"[suite]   -> {flag} intent={r.intent or '?'} "
              f"steps={len(r.steps)} prose={len(r.paragraph)}c "
              f"mellea={m['passed']}/{m['total']} rerolls={m['rerolls']} "
              f"frame={r.framing_score} elapsed={elapsed:.1f}s",
              file=sys.stderr)
        results.append(r)
        # Persist after each query so partial completion is non-destructive.
        write_per_query_json(r, out_dir)

    sm = write_summary(results, out_dir)
    fp = write_failures(results, out_dir)
    print(f"[suite] wrote {sm}", file=sys.stderr)
    print(f"[suite] wrote {fp}", file=sys.stderr)

    if args.label:
        # Snapshot SUMMARY for delta comparisons (e.g. SUMMARY-baseline.md)
        labeled = out_dir / f"SUMMARY-{args.label}.md"
        labeled.write_text(sm.read_text())
        print(f"[suite] also wrote {labeled}", file=sys.stderr)

    n_err = sum(1 for r in results if r.error or r.timed_out)
    return 0 if n_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
