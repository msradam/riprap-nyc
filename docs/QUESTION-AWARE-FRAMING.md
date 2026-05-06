# Question-aware briefing framing

Diagnosis + recommendation for WS3 of the 2026-05-06 overnight pass.

The four-section briefing structure (Status / Empirical / Modeled /
Policy) is non-negotiable — it's what the four Mellea grounding checks
score, and rewriting it risks the 4/4 pass rate. What we want to change
is the **opening sentence of the Status section**, so it engages the
question shape the user actually asked. Today every briefing leads
with a generic "this address is exposed to flood risk" no matter
whether the user asked "should I worry?" (resident), "is disclosure
required?" (attorney), or "where should we prioritize hardening?"
(planner).

## Where the system_prompt is set today

| Call site | Path | `EXTRA_SYSTEM_PROMPT` source |
|-----------|------|------------------------------|
| `app/fsm.py:983 step_reconcile` | single_address (strict) | `app/reconcile.py:53` |
| `app/intents/neighborhood.py:377` | neighborhood (strict) | local @ `app/intents/neighborhood.py:35` |
| `app/intents/development_check.py:218` | development_check (strict) | local @ `app/intents/development_check.py:32` |
| `app/intents/live_now.py:212` | live_now (non-strict) | local @ `app/intents/live_now.py:38` |
| `app/reconcile.py:1089 reconcile()` | legacy non-strict | `app/reconcile.py:53` |

All four strict paths funnel into `mellea_validator.reconcile_strict_streaming(doc_msgs, system_prompt, ...)`. The system_prompt is currently a constant per call site.

## Three options Adam outlined

### (a) Planner sub-classifier
Add a fifth `question_type` field to the planner's JSON schema. Granite
4.1:3b classifies it alongside `intent`. Capstone reads it and conditions
the opening.

- ✅ Reuses an LLM that already understands the query
- ❌ Re-validates the planner contract — the `_validate()` parser, the
      schema doc, the fallback logic, and `scripts/probe_addresses.py`
      all need to grow a new field
- ❌ Costs another planner call iteration to converge if the model
      mis-emits the new field
- ❌ The planner is the warm-cache path the demo lives or dies on —
      changing its output schema five days before pitch is high-risk

### (b) Capstone prompt-conditional
Detect `question_type` from the raw query string with a deterministic
regex-based heuristic, augment the system_prompt with a per-type
"opening directive," pass through to `reconcile_strict_streaming`. No
planner change.

- ✅ Lowest blast radius — only touches the Capstone call sites
- ✅ Deterministic, testable, zero added latency (no LLM call)
- ✅ Easy to roll back — remove the `augment_system_prompt(...)` call
- ✅ The four Mellea grounding checks stay byte-identical
- ⚠️ Question-shape detection is heuristic, not learned. Edge cases
     (weird phrasings, code-switching) will fall back to a generic
     directive. Acceptable for the demo personas — they're known up
     front.

### (c) Both
Planner emits a hint, Capstone uses it as a tiebreaker over the
heuristic.

- Same risks as (a). Pre-demo, the marginal accuracy isn't worth the
  schema change.

## Recommendation: **option (b)**

Implementation lives in a new module `app/framing.py`:

- `detect(query, intent) -> question_type` — regex-based detector that
  returns one of 11 question types (the same eleven as the suite's
  framing rubric).
- `opening_instruction(question_type) -> str | None` — returns the
  directive sentence to inject, or None for `generic_exposure` (the
  default — current behavior unchanged).
- `augment_system_prompt(base, query, intent) -> str` — wraps the base
  prompt with a `QUESTION-AWARE OPENING` block.

Wiring:

1. `app/fsm.py` — add `set_query(q)` / `_current_query()` threadlocals
   alongside the existing `set_strict_mode`. `step_reconcile()` reads
   the query + intent to augment the system prompt before calling
   `reconcile_strict_streaming`.
2. `app/intents/single_address.py:run()` — call `set_query(query)`
   before `iter_steps`, reset in `finally` (matches the existing
   threadlocal pattern).
3. `app/intents/neighborhood.py:run()` — augment the local
   `EXTRA_SYSTEM_PROMPT` directly before passing to
   `reconcile_strict_streaming`.
4. `app/intents/development_check.py:run()` — same as neighborhood.
5. `app/intents/live_now.py:run()` — same; non-strict path so it just
   prepends to the system message content.
6. `app/reconcile.py:reconcile()` (legacy) — out of scope; it's not on
   the demo path and the strict path covers all current intents.

## Stop conditions

Per Adam's instruction: if the framing rubric scores below 3 on more
than five queries after the change lands, document what option (a) /
(c) would require and stop. **Do not silently expand scope.**

The "below 3 on more than five" test is the trigger to move to
heavier interventions — typically that the regex detector misclassified
the question or the Granite model is ignoring the directive under the
existing system prompt's strong four-section discipline.
