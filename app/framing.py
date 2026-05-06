"""Question-aware framing for the Capstone briefing opening.

The four-section structure (Status / Empirical / Modeled / Policy) is
load-bearing for the Mellea grounding checks and stays unchanged. What
this module does is detect the *shape* of the user's question from the
raw query string + planner intent, then return a single-sentence
directive that conditions only the opening Status sentence.

Eleven question types are recognised; they mirror the rubric in
`tests/integration/stakeholder_queries.py:FRAMING_RUBRICS`. Detection
is deterministic regex matching — no extra LLM call, no added latency.

Usage:

    from app.framing import augment_system_prompt
    system_prompt = augment_system_prompt(
        EXTRA_SYSTEM_PROMPT, query=user_query, intent=plan.intent,
    )

The returned prompt has the original text plus a trailing
`QUESTION-AWARE OPENING:` block. Granite 4.1 attends to this through
the system-prompt cache and applies it to the Status sentence.
"""
from __future__ import annotations

import re
from typing import Final

QUESTION_TYPES: Final[tuple[str, ...]] = (
    "habitability_decision",
    "legal_disclosure",
    "capital_planning",
    "underwriting",
    "journalism",
    "development_siting",
    "grant_evidence",
    "retrospective",
    "emergency_response",
    "comparison",
    "generic_exposure",
)


# ---- Per-type opening directives ------------------------------------------
#
# Each directive is one sentence that supplements (does not replace) the
# Status section's existing instruction. Granite 4.1 has a strong prior
# toward "this address is exposed to ..." openings; the directive
# overrides that in a question-shaped way without disturbing the four
# grounding invariants.

_DIRECTIVES: dict[str, str] = {
    "habitability_decision": (
        "The Status sentence MUST start with a direct verdict word "
        "(\"Yes\" if the documents show meaningful flood evidence, \"No\" "
        "if they don't), then name the single strongest piece of "
        "evidence with its [doc_id]. The user is deciding whether to "
        "live here — answer the question, then cite."
    ),
    "legal_disclosure": (
        "The Status sentence MUST state whether the documents contain "
        "facts a NY RPL §462(2) or §231-b disclosure would need to "
        "record. Begin with \"Disclosure is warranted\" or \"Disclosure "
        "is not triggered\" based on the evidence, then name the "
        "specific fact with its [doc_id]. The user is a real-estate "
        "professional checking the disclosure threshold."
    ),
    "capital_planning": (
        "The Status sentence MUST frame the place as a capital-planning "
        "candidate: name the dominant exposure with its [doc_id] and "
        "indicate whether the evidence supports prioritization "
        "(\"merits prioritization\", \"ranks high for hardening\") or "
        "not. The user allocates infrastructure investment."
    ),
    "underwriting": (
        "The Status sentence MUST emphasize that every figure in the "
        "briefing is independently sourced — open with the dominant "
        "exposure and the specific [doc_id], then add a half-clause "
        "noting that the audit chain follows below. The user is an "
        "underwriter who needs a defensible loss narrative."
    ),
    "journalism": (
        "The Status sentence MUST be reproducible reporting prose: "
        "name the place, name the dominant exposure with [doc_id], "
        "and avoid editorial verbs like \"shocking\" or \"alarming\". "
        "The user is a data journalist who will cite this prose verbatim."
    ),
    "development_siting": (
        "The Status sentence MUST start with the count of active "
        "construction filings cited from [dob_permits] (e.g. \"N "
        "active construction filings sit inside ...\") and indicate "
        "which flood layer they intersect. The user is a developer or "
        "architect doing a pre-design siting check."
    ),
    "grant_evidence": (
        "The Status sentence MUST open with \"Vulnerability "
        "assessment:\" and name the place + dominant exposure with "
        "[doc_id]. Treat the briefing as the evidence section of a "
        "HUD CDBG-DR or FEMA BRIC application — formal, third-person, "
        "free of advocacy framing."
    ),
    "retrospective": (
        "Riprap currently runs on present-day data sources. The Status "
        "sentence MUST acknowledge the question is retrospective and "
        "state explicitly that the briefing reflects the CURRENT state "
        "of these data sources, not a snapshot from the requested date. "
        "Then proceed with the present-day exposure picture so the user "
        "still gets the geography. Silence-over-confabulation: never "
        "reconstruct historical conditions you can't verify."
    ),
    "emergency_response": (
        "The Status sentence MUST quantify what is at risk in the "
        "next few hours, citing the live signal that triggered the "
        "query and any active alerts with [doc_id]. The user needs an "
        "operational picture, not a historical exposure summary."
    ),
    "comparison": (
        "The Status sentence MUST name BOTH places the user is "
        "comparing and indicate which one shows greater exposure on "
        "the strongest cited signal. If only one place's data is "
        "available in the documents, say so explicitly. The user is "
        "doing a head-to-head decision."
    ),
    "generic_exposure": "",  # default — no override
}


# ---- Detector -------------------------------------------------------------
#
# Patterns are ordered: the FIRST type whose pattern matches wins. Order
# matters — more specific question shapes (legal_disclosure, grant_evidence,
# emergency_response) come before more general ones (habitability_decision,
# capital_planning) so the obvious specialist tags don't get swallowed.

_PATTERNS: list[tuple[str, list[re.Pattern]]] = [
    ("retrospective", [
        re.compile(r"\b(would have|would Riprap|on (the )?date of|as of (the )?(date|day)|"
                   r"day before|prior to|before (Hurricane|Ida|Sandy|the storm)|"
                   r"on (August|September|October|November|December|January|February|March|"
                   r"April|May|June|July) \d{1,2},? ?\d{4}|"
                   r"time.?machine|retrospective|court (exhibit|testimony))\b", re.I),
    ]),
    ("emergency_response", [
        re.compile(r"\b(just triggered|right now|next (few |six |\d+ )?hours?|"
                   r"in the next \d+|currently flooding|flood (warning|watch) is active|"
                   r"sensor [A-Z]{2}-?\d+|live (alert|trigger))\b", re.I),
    ]),
    ("legal_disclosure", [
        re.compile(r"\b(disclos(e|ure|ed)|RPL\s*§?\s*\d+|Property Condition Disclosure|"
                   r"§\s*462|§\s*231-?b|seller'?s? disclosure|landlord'?s? disclosure|"
                   r"required to disclose|need to disclose)\b", re.I),
    ]),
    ("grant_evidence", [
        re.compile(r"\b(vulnerability assessment|CDBG-?DR|HUD|BRIC|"
                   r"grant application|funding application|community resilience grant|"
                   r"FEMA application|disaster recovery (application|funding))\b", re.I),
    ]),
    ("development_siting", [
        re.compile(r"\b(what (are|is) (they|being) build(ing)?|new construction|"
                   r"under construction|active (construction|filing|project|permit)|"
                   r"projects? (in progress|underway|planned)|architects?|"
                   r"siting check|pre.?design|"
                   r"DOB filing|developer)\b", re.I),
    ]),
    ("comparison", [
        # `prioritize X over Y` can have many words between, hence the
        # bounded non-greedy span — capped at 80 chars to avoid runaway.
        re.compile(r"\b(compare\b|comparison|\bvs\b|\bversus\b|"
                   r"head-?to-?head|\brank\s+the\s+top)\b", re.I),
        re.compile(r"\bprioritize\b.{1,80}\bover\b", re.I | re.S),
        re.compile(r"\bover\s+\w+(?:\s+\w+){0,3}\s+for\s+(hardening|investment)\b", re.I),
    ]),
    ("capital_planning", [
        re.compile(r"\b(prioritiz(e|ation)|capital plan(ning)?|harden(ing|s)?|"
                   r"infrastructure investment|where (should|to) (we |the )(invest|"
                   r"prioritize|harden)|MTA.+prioritize|DEP.+prioritize|"
                   r"protection envelope|outside (it|the protection)|"
                   r"resilien(ce|cy) project)\b", re.I),
    ]),
    ("habitability_decision", [
        re.compile(r"\b(should I worry|should I (be|consider)|is (it|this) safe|"
                   r"can I (rent|live|move|raise (my )?kids?)|considering (renting|leasing|moving)|"
                   r"(thinking about|planning to) (rent|lease|move|buy)|"
                   r"is (this|that|the landlord) true|landlord (says|claims|told)|"
                   r"no flood history|just got a lease|new lease|signing a lease|"
                   r"\bworry\b)", re.I),
    ]),
    ("underwriting", [
        re.compile(r"\b(underwrit(e|er|ing|able)|actuarial|loss history|"
                   r"insurabl[ey]|catastrophe (model|risk)|"
                   r"insurance (audit|memo|profile)|"
                   r"audit (chain|trail))\b", re.I),
    ]),
    ("journalism", [
        re.compile(r"\b(reporter|journalist|newsroom|story|coverage|"
                   r"published?|publish (this|the))", re.I),
    ]),
]


def detect(query: str, intent: str | None = None) -> str:
    """Classify the question shape from the raw query and planner intent.

    Returns one of `QUESTION_TYPES`. Falls back to `generic_exposure`
    when no pattern matches — that's the existing behavior, preserved.

    `intent` is currently advisory only (the patterns don't read it),
    but the parameter is part of the API so future refinements can
    use it (e.g. an `intent=neighborhood` query without a verdict
    keyword could default to `journalism` rather than `generic_exposure`).
    """
    if not query:
        return "generic_exposure"
    q = query.strip()
    for qt, patterns in _PATTERNS:
        if any(p.search(q) for p in patterns):
            return qt
    # Heuristic fallback: bare neighborhood/borough names from a planner
    # context default to journalism (most common stakeholder reading a
    # neighborhood-only query is a reporter or planner). For
    # single_address with no question keyword, fall back to generic.
    if intent == "neighborhood" and len(q.split()) <= 3:
        return "journalism"
    return "generic_exposure"


def opening_instruction(question_type: str) -> str:
    """Return the directive sentence(s) for a question type.
    Returns empty string for `generic_exposure` (no override)."""
    return _DIRECTIVES.get(question_type, "")


def augment_system_prompt(base: str, *, query: str,
                           intent: str | None = None) -> str:
    """Wrap a base system prompt with a question-aware opening directive.

    No-op when the detector returns `generic_exposure` — the original
    behavior is preserved.
    """
    qt = detect(query, intent)
    directive = opening_instruction(qt)
    if not directive:
        return base
    return (
        f"{base}\n\n"
        f"QUESTION-AWARE OPENING (this directive overrides ONLY the opening "
        f"**Status.** sentence; the four-section structure and citation "
        f"discipline above remain in force):\n{directive}"
    )
