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
