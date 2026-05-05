"""Capstone — the Synthesiser.

Granite 4.1 (8B) writes the cited briefing under Mellea-validated
rejection sampling. Every numeric claim is anchored to a `[doc_id]`
citation pointing back into one of the four data-Stones; sentences
that fail the four grounding checks (`numerics_grounded`,
`no_placeholder_tokens`, `citations_dense`, `citations_resolve`) are
rolled with surgical feedback until the budget is exhausted.

This module is a thin alias around `app.reconcile` — the working code
stays in `app/reconcile.py` for git-blame continuity. The naming is in
the user-facing trace and the README.
"""
from __future__ import annotations

from typing import Any

from app import reconcile as _reconcile

NAME = "Capstone"
TAGLINE = "The Synthesiser"
DESCRIPTION = (
    "Writes the cited briefing — Granite 4.1 + Mellea rejection sampling."
)

# Capstone consumes everything the four data-Stones produced; we don't
# enumerate state keys here because the reconciler reads the FSM state
# directly and `app/reconcile.py:build_documents()` is the source of
# truth for which keys it touches.
SOURCES: list[str] = []

# Re-export the reconciler entrypoints under the Stone name so callers
# can write `from app.stones import capstone; capstone.run(state)`.
build_documents = _reconcile.build_documents
trim_docs_to_plan = _reconcile.trim_docs_to_plan
verify_paragraph = _reconcile.verify_paragraph
run = _reconcile.reconcile
EXTRA_SYSTEM_PROMPT = _reconcile.EXTRA_SYSTEM_PROMPT


def collect(state: dict[str, Any]) -> dict[str, Any]:
    """Return the Capstone's outputs from the state dict (for the trace)."""
    out: dict[str, Any] = {}
    for k in ("paragraph", "audit", "mellea"):
        if state.get(k) is not None:
            out[k] = state[k]
    return out
