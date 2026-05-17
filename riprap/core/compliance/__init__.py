"""Briefing-quality compliance — predicates sourced from real-world standards.

Public surface:

    from riprap.core.compliance import check_briefing
    report = check_briefing(paragraph_text)
    # report.passed     — bool: every predicate passed
    # report.results    — list[PredicateResult]
    # report.failed     — list[PredicateResult] for the ones that failed
    # report.summary()  — short multi-line human-readable summary

Rules are documented in `docs/briefing-standards.md`. Each predicate
function returns a `PredicateResult(passed, reason, evidence)`.
"""
from riprap.core.compliance.predicates import (
    ALL_PREDICATES,
    ComplianceReport,
    PredicateResult,
    check_briefing,
)

__all__ = ["PredicateResult", "ComplianceReport", "check_briefing", "ALL_PREDICATES"]
