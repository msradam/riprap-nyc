# Open Issues — post-hackathon triage

These bugs were identified in the `audit/AUDIT-2026-05-06.md` pass.
All are in `experiments/` (exploratory/reproduction code) and were
explicitly left untouched pre-demo per Adam's instruction.

---

## 1. `experiments/17` — F821 numpy annotation race

**File:** `experiments/17_riprap_integration/terramind_nyc.py:117`
**Ruff code:** F821 (3×)
**Issue:** Type annotation references `np` (numpy) before it is
imported at module top. Currently masked by `from __future__ import
annotations` (lazy eval). Will fail if Python ever evaluates it
eagerly, or if this module is ported to a context that drops the
future import.
**Fix:** Move `import numpy as np` to module top.

---

## 2. `experiments/18` — f-string syntax only valid on Py 3.12+

**File:** `experiments/18_terramind_nyc_lora/shared/eval_adapter.py:125`
**Ruff code:** invalid-syntax
**Issue:** Inner f-string reuses outer quote style (valid in Py 3.12,
syntax error in Py 3.10). The HF Space (Py 3.10) cannot import this
file. Currently local-only; will error if anyone tries to ship it.
**Fix:** Change inner f-string quotes or use `.format()`.

---

## 3. `experiments/05` — closure captures loop variable

**File:** `experiments/05_terramind_nyc_finetune/training/verify_phase1.py:438`
**Ruff code:** B023 (2×)
**Issue:** Closure inside a `for` loop binds the loop variable by
reference (all closures see the last value). The classic Python
late-binding trap. May or may not be a bug depending on intent — needs
a human eye on what the closure does.
**Fix:** Rebind with a default arg: `lambda x=x: ...`.

---

## 4. `experiments/18` — possibly dead `api` assignment

**File:** `experiments/18_terramind_nyc_lora/shared/publish_hf.py:107`
**Ruff code:** F841
**Issue:** `api` is assigned (likely from `HfApi()`) but never used
in the file. May be a bug (intended to call `api.upload_file(...)`) or
a leftover from an edit. Needs a human eye.
**Fix:** Either use `api` in the upload calls, or remove the assignment.

---

## 5. `_merge_mellea` puts requirements in both `passed` and `failed`

**File:** `web/main.py:563`
**Issue:** Uses `set(a_passed + b_passed)` (union) for `requirements_passed`. If
leg A fails `citations_resolve` but leg B passes it, `citations_resolve`
ends up in both `requirements_passed` and `requirements_failed` in the
merged Mellea dict. The UI then shows "4/4 passed" with a contradictory
"failed: citations_resolve" entry.
**Fix:** Use intersection for `requirements_passed`:
```python
"requirements_passed": list(set(_lst(a, "requirements_passed")) & set(_lst(b, "requirements_passed"))),
```

---

## 6. `mellea.attempts` wrong field name in `persistSnapshot`

**File:** `web/sveltekit/src/routes/q/[queryId]/+page.svelte:598`
**Issue:** `finalResult?.mellea?.attempts` is always `undefined` — the Mellea
field is `n_attempts`. Falls back silently to the streaming `attempt` counter.
The PDF/print snapshot always has wrong attempt metadata.
**Fix:**
```js
attempts: finalResult?.mellea?.n_attempts ?? attempt
```

---

## 7. NTA-typed compare targets fall through to single_address

**File:** `web/main.py:514`
**Issue:** `addr_targets = [t for t in p.targets if t.get("type") == "address"]`
filters out NTA targets. When the planner returns `type: "nta"` for both sides
of a compare query (e.g. "Compare Two Bridges to Battery Park City"), `addr_targets`
is empty, the fallback runs the full raw query text through `single_address`, the
geocoder finds no valid address, and the response is "No grounded data available."
**Fix:** Accept `"nta"` targets and route each through the `neighborhood` intent
instead of `single_address`, or accept both type values and pick the right intent
per target.

---

## 8. `iter_steps` returns without `final` when FSM fails pre-iteration

**File:** `app/fsm.py:1292–1294`
**Issue:** If `app.iterate()` raises before any action completes (so
`final_state_holder["state"]` is never set), `iter_steps` does a bare `return`
after the error event. No `final` event is yielded. The SSE stream closes with
an open Stone in the trace UI (the `stone_done` for the active Stone never fires),
leaving the frontend in a non-terminal render state.
**Fix:** Yield a synthetic `final` with an error flag when `state is None`:
```python
if state is None:
    yield {"kind": "final", "paragraph": "", "error": "FSM failed before any action completed"}
    return
```
