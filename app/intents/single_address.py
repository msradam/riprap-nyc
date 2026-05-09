"""single_address intent — the existing linear FSM, wrapped behind the
planner-aware execution interface. The planner's specialist list is
respected only as an OPT-OUT: if the planner explicitly omitted a
specialist we'd otherwise run, we skip it. The fixed FSM stays as the
canonical path because (a) it's well-tested, (b) order-of-execution
matters slightly (geocode before everything), and (c) the executor
parallelism for an address is bounded by Granite 4.1 reconcile time
anyway."""
from __future__ import annotations

import re

from app.fsm import run as run_linear

_ADDRESS_SHAPE = re.compile(
    r"^\d+\s+[A-Z][\w\s\.\-']+(St|Street|Ave|Avenue|Rd|Road|Blvd|"
    r"Boulevard|Pl|Place|Ln|Lane|Dr|Drive|Way|Ct|Court|Pkwy|"
    r"Parkway|Sq|Square|Ter|Terrace|Hwy|Highway)\.?",
    re.IGNORECASE,
)


def _looks_like_address(s: str) -> bool:
    return bool(s and _ADDRESS_SHAPE.search(s))


def run(plan, query: str, progress_q=None, strict: bool = False) -> dict:
    """Execute the planner's single_address Plan via the existing linear
    FSM. If progress_q is provided, FSM steps and Granite reconcile tokens
    are forwarded to it for live streaming.

    strict=True flips the FSM's reconcile step to Mellea-validated
    rejection sampling (via a thread-local flag). Disables token
    streaming for that step."""
    from app.fsm import (
        iter_steps,
        set_mellea_attempt_callback,
        set_planned_specialists,
        set_planner_intent,
        set_strict_mode,
        set_token_callback,
        set_user_query,
    )
    planner_addr = next(
        (t["text"] for t in plan.targets if t.get("type") == "address"),
        None,
    )
    addr = planner_addr if _looks_like_address(planner_addr) else query
    set_strict_mode(strict)
    set_planned_specialists(plan.specialists or [])
    set_user_query(query)
    set_planner_intent(plan.intent)
    if progress_q is not None:
        def _on_token(delta: str, attempt_idx: int = 0):
            # `attempt_idx` is the 0-based Mellea reroll index. The
            # SvelteKit client treats a change in this value as a
            # signal to clear the live briefing buffer (per
            # web/sveltekit/src/lib/client/agentStream.ts:onAttemptStart).
            # We surface it as a 1-based attempt counter so the chip
            # in the UI reads "attempt N" naturally.
            progress_q.put({"kind": "token", "delta": delta,
                            "attempt": attempt_idx + 1})
        def _on_mellea_attempt(attempt_idx, passed, failed):
            progress_q.put({"kind": "mellea_attempt",
                            "attempt": attempt_idx,
                            "passed": passed, "failed": failed})
        # Streaming Mellea now emits tokens during each attempt — wire
        # the token callback for both strict and non-strict paths.
        set_token_callback(_on_token)
        set_mellea_attempt_callback(_on_mellea_attempt)
        try:
            final = None
            for ev in iter_steps(addr):
                if ev["kind"] == "step":
                    progress_q.put({"kind": "step", **ev})
                else:
                    final = ev
            out = {**(final or {}), "trace": []}
        finally:
            set_token_callback(None)
            set_mellea_attempt_callback(None)
            set_strict_mode(False)
            set_planned_specialists(None)
            set_user_query(None)
            set_planner_intent(None)
    else:
        try:
            out = run_linear(addr)
        finally:
            set_strict_mode(False)
            set_planned_specialists(None)
            set_user_query(None)
            set_planner_intent(None)
    out["intent"] = "single_address"
    out["plan"] = {
        "intent": plan.intent,
        "targets": plan.targets,
        "specialists": plan.specialists,
        "rationale": plan.rationale,
    }
    return out
