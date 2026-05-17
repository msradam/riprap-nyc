"""Compliance predicates for Riprap briefings.

Each predicate maps to a rule in `docs/briefing-standards.md`. Predicates
operate on the rendered briefing prose (post-reconcile, post-shaper).
Some predicates also accept structured context (e.g. which pebbles ran
offline, which sources cited) when that information adds rigor.

Rule citations in docstrings reference the section + rule numbering in
`docs/briefing-standards.md`. Predicates return a `PredicateResult` so
audit reports can quote the offending span verbatim.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class PredicateResult:
    """One predicate's verdict on the briefing."""
    name: str
    passed: bool
    rule: str          # citation, e.g. "FEMA 1.2"
    description: str   # what the predicate enforces (human-readable)
    reason: str = ""   # why it passed/failed (may quote offending text)
    evidence: list[str] = field(default_factory=list)  # offending spans


@dataclass
class ComplianceReport:
    paragraph: str
    results: list[PredicateResult]

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failed(self) -> list[PredicateResult]:
        return [r for r in self.results if not r.passed]

    @property
    def passed_results(self) -> list[PredicateResult]:
        return [r for r in self.results if r.passed]

    def summary(self) -> str:
        if self.passed:
            return f"✓ All {len(self.results)} compliance predicates passed."
        lines = [
            f"✗ {len(self.failed)} of {len(self.results)} compliance predicates failed:",
        ]
        for r in self.failed:
            lines.append(f"  - [{r.rule}] {r.description}")
            if r.reason:
                lines.append(f"      → {r.reason}")
            for e in r.evidence[:2]:
                lines.append(f"      evidence: {e!r}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _sentences(text: str) -> list[str]:
    """Naive sentence split — good enough for predicate scanning."""
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


_HEDGES = (
    "would", "may", "could", "modeled", "projected", "is mapped",
    "1% annual chance", "1 percent annual chance", "any given year",
    "during a base flood", "in modeled scenarios", "in the modeled",
    "expected", "anticipated", "estimated",
)


def _has_hedge(span: str) -> bool:
    s = span.lower()
    return any(h in s for h in _HEDGES)


# ---------------------------------------------------------------------------
# Predicates
# Each accepts (paragraph, context) and returns PredicateResult.
# `context` is an optional dict carrying structured info (pebble states,
# offline pebble ids, intent, etc.).
# ---------------------------------------------------------------------------

def _result(name: str, rule: str, description: str,
            passed: bool, reason: str = "",
            evidence: list[str] | None = None) -> PredicateResult:
    return PredicateResult(name=name, rule=rule, description=description,
                           passed=passed, reason=reason,
                           evidence=evidence or [])


# 1. FEMA — no "will flood" without hedge
_WILL_FLOOD_RE = re.compile(
    r"\b(will flood|is going to flood|is flooding|will be inundated|"
    r"is inundated|this address floods|the address floods)\b",
    re.IGNORECASE,
)


def no_will_flood_without_hedge(paragraph: str, context: dict | None = None) -> PredicateResult:
    """FEMA 1.2 — 'in zone' must not be conflated with 'will flood'."""
    bad: list[str] = []
    for s in _sentences(paragraph):
        m = _WILL_FLOOD_RE.search(s)
        if m and not _has_hedge(s):
            bad.append(s)
    return _result(
        "no_will_flood_without_hedge",
        rule="FEMA 1.2",
        description="No bare 'will flood' / 'is inundated' assertions; hedge required.",
        passed=not bad,
        reason="" if not bad else f"{len(bad)} unhedged future-flood assertion(s)",
        evidence=bad,
    )


# 1.3 — no false reassurance
_FALSE_REASSURANCE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"\bno risk\b",
        r"\bzero risk\b",
        r"\bcompletely safe\b",
        r"\bnothing to worry about\b",
        r"\bguaranteed dry\b",
        r"\bsafe from flooding\b",
        r"\bwon'?t flood\b",
        r"\bno chance of flood",
    )
]


def no_false_reassurance(paragraph: str, context: dict | None = None) -> PredicateResult:
    """FEMA 1.3 + EPA 5.7 — no language minimizing residual or future risk."""
    bad: list[str] = []
    for s in _sentences(paragraph):
        for pat in _FALSE_REASSURANCE_PATTERNS:
            if pat.search(s):
                bad.append(s)
                break
    return _result(
        "no_false_reassurance",
        rule="FEMA 1.3 / EPA 5.7",
        description="No language asserting absence of flood risk or false reassurance.",
        passed=not bad,
        reason="" if not bad else f"{len(bad)} false-reassurance phrase(s)",
        evidence=bad,
    )


# 1.1 — "100-year flood" requires recurrence clarification
def hundred_year_flood_clarified(paragraph: str, context: dict | None = None) -> PredicateResult:
    """FEMA 1.1 — '100-year flood' acceptable only with recurrence-interval caveat."""
    s = paragraph.lower()
    has_term = bool(re.search(r"\b100[- ]year flood\b", s))
    has_clarification = bool(re.search(
        r"(1\s*%\s*annual chance|1 percent annual chance|any given year)", s,
    ))
    if has_term and not has_clarification:
        return _result(
            "hundred_year_flood_clarified",
            rule="FEMA 1.1",
            description="'100-year flood' must be accompanied by the 1% annual chance framing.",
            passed=False,
            reason="'100-year flood' used without the '1% annual chance' caveat.",
        )
    return _result(
        "hundred_year_flood_clarified",
        rule="FEMA 1.1",
        description="'100-year flood' must be accompanied by the 1% annual chance framing.",
        passed=True,
    )


# 1.5 — FIRM citation has vintage
_FIRM_TOKENS_RE = re.compile(
    r"\b(FEMA flood map|FIRM|flood insurance rate map|flood zone)\b",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def firm_citation_has_vintage(paragraph: str, context: dict | None = None) -> PredicateResult:
    """FEMA 1.5 — FEMA flood maps cited must carry their effective date."""
    bad: list[str] = []
    for s in _sentences(paragraph):
        if _FIRM_TOKENS_RE.search(s) and not _YEAR_RE.search(s):
            bad.append(s)
    return _result(
        "firm_citation_has_vintage",
        rule="FEMA 1.5",
        description="Sentences citing FEMA flood maps must include the map vintage (year).",
        passed=not bad,
        reason="" if not bad else f"{len(bad)} FEMA-map citation(s) without a year",
        evidence=bad,
    )


# 2.1, 2.2 — IPCC likelihood vocabulary
_IPCC_LIKELIHOOD_TERMS = {
    "virtually certain": (99, 100),
    "extremely likely":  (95, 100),
    "very likely":       (90, 100),
    "likely":            (66, 100),
    "more likely than not": (50, 100),
    "about as likely as not": (33, 66),
    "unlikely":          (0, 33),
    "very unlikely":     (0, 10),
    "extremely unlikely": (0, 5),
    "exceptionally unlikely": (0, 1),
}
_UNCALIBRATED_HEDGES = ("probably", "fairly likely", "good chance",
                        "decent chance", "pretty likely", "kinda likely")


def no_uncalibrated_probability_language(paragraph: str, context: dict | None = None) -> PredicateResult:
    """IPCC 2.2 — uncalibrated hedges ('probably', 'good chance', etc.) must
    not be paired with numeric probabilities. Encourages the AR6 lexicon."""
    bad: list[str] = []
    for s in _sentences(paragraph):
        sl = s.lower()
        has_uncalibrated = any(h in sl for h in _UNCALIBRATED_HEDGES)
        has_number = bool(re.search(r"\b\d+(\.\d+)?\s*%", sl))
        if has_uncalibrated and has_number:
            bad.append(s)
    return _result(
        "no_uncalibrated_probability_language",
        rule="IPCC 2.2",
        description="Uncalibrated hedges (e.g. 'probably') paired with a numeric probability must use the IPCC AR6 lexicon instead.",
        passed=not bad,
        evidence=bad,
    )


# 3.2 — projection cites a horizon
_PROJECTION_TOKENS_RE = re.compile(
    r"\b(project(?:ed|ion)|forecast|scenario|model(?:ed)? for|nowcast)\b",
    re.IGNORECASE,
)
_HORIZON_RE = re.compile(
    r"(by\s+(?:19|20)\d{2}|"
    r"in\s+(?:19|20)\d{2}|"
    r"(?:19|20)\d{2}\s+(?:slr|sea[- ]level rise|baseline|scenario)|"
    r"(?:next|over\s+the\s+next|past|last|previous)\s+\d+(?:\.\d+)?\s*[- ]?\s*(?:year|month|week|day|hour|minute)s?|"
    r"\d+(?:\.\d+)?\s*[- ]?\s*(?:year|month|week|day|hour|minute)s?\s+(?:ahead|out|horizon|window|forecast|nowcast|cadence|projection|outlook)|"
    r"short[- ]term|medium[- ]term|long[- ]term|near[- ]term)",
    re.IGNORECASE,
)


def projection_has_horizon(paragraph: str, context: dict | None = None) -> PredicateResult:
    """TCFD 3.2 — projections must declare their time horizon."""
    bad: list[str] = []
    for s in _sentences(paragraph):
        if _PROJECTION_TOKENS_RE.search(s) and not _HORIZON_RE.search(s):
            bad.append(s)
    return _result(
        "projection_has_horizon",
        rule="TCFD 3.2",
        description="Projection sentences must declare a time horizon (short/medium/long-term or an explicit year/duration).",
        passed=not bad,
        evidence=bad,
    )


# 4.1 — scope declaration present
def scope_declaration_present(paragraph: str, context: dict | None = None) -> PredicateResult:
    """ASTM 4.1 — every brief declares itself as a flood-exposure briefing."""
    s = paragraph.lower()
    has = any(t in s for t in (
        "flood-exposure briefing", "flood exposure briefing",
        "this briefing", "this flood briefing",
    ))
    return _result(
        "scope_declaration_present",
        rule="ASTM 4.1",
        description="The briefing must declare its scope (it is a flood-exposure briefing, not a certificate or determination).",
        passed=has,
        reason="" if has else "No scope declaration found in the prose.",
    )


# 4.6 — informational disclaimer
def informational_disclaimer_present(paragraph: str, context: dict | None = None) -> PredicateResult:
    """ASTM 4.6 — closing disclaimer that the brief is informational only."""
    s = paragraph.lower()
    has = any(t in s for t in (
        "not a substitute", "informational only", "not a flood certificate",
        "not an elevation certificate", "not an insurance determination",
        "does not constitute", "consult a licensed",
    ))
    return _result(
        "informational_disclaimer_present",
        rule="ASTM 4.6",
        description="Brief must declare that it is informational, not a substitute for professional flood / elevation / insurance determination.",
        passed=has,
        reason="" if has else "No informational-only disclaimer found.",
    )


# 4.5 — automation disclosure
def automation_disclosure_present(paragraph: str, context: dict | None = None) -> PredicateResult:
    """ASTM 4.5 — machine-generated briefs must declare automation + sources."""
    s = paragraph.lower()
    has = any(t in s for t in (
        "automated", "machine-generated", "algorithmically",
        "generated by", "produced by riprap", "compiled by riprap",
    ))
    return _result(
        "automation_disclosure_present",
        rule="ASTM 4.5",
        description="Brief must disclose that it is automated / machine-generated.",
        passed=has,
        reason="" if has else "No automation disclosure found.",
    )


# 4.4 — data-gap disclosure when probes offline
def data_gap_disclosed_when_probe_offline(paragraph: str, context: dict | None = None) -> PredicateResult:
    """ASTM 4.4 + CERC 5.6 — when probes are offline, the briefing must
    say so (what's known / what isn't).

    Requires `context.offline_pebbles` (list[str]); if not provided,
    predicate passes by default (cannot verify).
    """
    offline = (context or {}).get("offline_pebbles") or []
    if not offline:
        return _result(
            "data_gap_disclosed_when_probe_offline",
            rule="ASTM 4.4 / CERC 5.6",
            description="When probes are offline, the briefing must disclose the data gap.",
            passed=True,
            reason="No offline probes reported; nothing to disclose.",
        )
    s = paragraph.lower()
    gap_markers = ("offline", "unavailable", "not available", "could not",
                   "missing", "data gap", "not evaluated")
    has_disclosure = any(m in s for m in gap_markers)
    return _result(
        "data_gap_disclosed_when_probe_offline",
        rule="ASTM 4.4 / CERC 5.6",
        description="Offline probes must be disclosed as data gaps.",
        passed=has_disclosure,
        reason=("Offline probes are not disclosed in the prose: "
                + ", ".join(offline)) if not has_disclosure else "",
    )


# 5.8 — no unrelated risk comparisons (lightning, car accidents…)
_UNRELATED_RISK_RE = re.compile(
    r"\b(car accident|automobile accident|driving|lightning strike|airplane crash|"
    r"plane crash|shark attack|lottery)\b",
    re.IGNORECASE,
)


def no_unrelated_risk_comparisons(paragraph: str, context: dict | None = None) -> PredicateResult:
    """EPA 5.8 — don't compare flood risk to dissimilar everyday risks."""
    bad: list[str] = []
    for s in _sentences(paragraph):
        if _UNRELATED_RISK_RE.search(s):
            bad.append(s)
    return _result(
        "no_unrelated_risk_comparisons",
        rule="EPA 5.8",
        description="Flood risk must not be compared to unrelated everyday risks (lightning, car accidents, etc.).",
        passed=not bad,
        evidence=bad,
    )


# 6.5 — no false precision
_FALSE_PRECISION_RE = re.compile(
    # 3+ significant digits attached to physical-quantity units
    r"\b\d+\.\d{3,}\s*(m|ft|km|mi|mm|cm|in|sq\s?m|sq\s?ft|inches|feet)\b",
    re.IGNORECASE,
)


def no_rounding_to_false_precision(paragraph: str, context: dict | None = None) -> PredicateResult:
    """AP 6.5 — round to a precision the underlying data supports.

    Catches things like '5870.5 m' (LiDAR + haversine doesn't justify 0.1 m
    precision over kilometer-scale distances); should be '~5.9 km' or '~5870 m'.
    """
    bad = _FALSE_PRECISION_RE.findall(paragraph)
    matches: list[str] = []
    if bad:
        # Re-scan to grab the offending tokens with context
        for m in _FALSE_PRECISION_RE.finditer(paragraph):
            start = max(0, m.start() - 20)
            end = min(len(paragraph), m.end() + 20)
            matches.append(paragraph[start:end].strip())
    return _result(
        "no_rounding_to_false_precision",
        rule="AP 6.5",
        description="Numeric values must be rounded to a precision the underlying source supports.",
        passed=not bad,
        evidence=matches,
    )


# 7.1 / AP 6.1 — every numeric claim has a citation nearby
_NUM_TOKEN_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|ft|m|mm|cm|km|in|inches|feet|complaints?|events?|sensors?)\b",
                           re.IGNORECASE)
_CITATION_RE = re.compile(r"\[[a-z][a-z0-9_]*\]", re.IGNORECASE)


def every_numeric_claim_cited(paragraph: str, context: dict | None = None) -> PredicateResult:
    """SPJ 7.1 / AP 6.1 — every numeric claim must be attributed."""
    bad: list[str] = []
    for s in _sentences(paragraph):
        if _NUM_TOKEN_RE.search(s) and not _CITATION_RE.search(s):
            bad.append(s)
    return _result(
        "every_numeric_claim_cited",
        rule="SPJ 7.1 / AP 6.1",
        description="Every sentence with a numeric quantity must carry a [doc_id] citation.",
        passed=not bad,
        evidence=bad,
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

ALL_PREDICATES: list[Callable[..., PredicateResult]] = [
    no_will_flood_without_hedge,
    no_false_reassurance,
    hundred_year_flood_clarified,
    firm_citation_has_vintage,
    no_uncalibrated_probability_language,
    projection_has_horizon,
    scope_declaration_present,
    informational_disclaimer_present,
    automation_disclosure_present,
    data_gap_disclosed_when_probe_offline,
    no_unrelated_risk_comparisons,
    no_rounding_to_false_precision,
    every_numeric_claim_cited,
]


def check_briefing(paragraph: str, context: dict | None = None) -> ComplianceReport:
    """Run every predicate over the briefing, return a ComplianceReport."""
    results = [p(paragraph, context) for p in ALL_PREDICATES]
    return ComplianceReport(paragraph=paragraph, results=results)
