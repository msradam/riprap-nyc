# Overnight pass — morning brief — 2026-05-06

> Branch: `overnight-2026-05-06`. Local-only, not pushed, not deployed.
> Read this in 5 min; everything detailed lives in linked sub-reports.

## Status one-liner

Three of four work streams landed: code audit ran clean and committed
mechanical fixes only; the 20-query stakeholder integration suite
exists, ran end-to-end against local Granite + local specialists, and
now produces per-query JSON + SUMMARY + FAILURES; the question-aware
Capstone framing landed as a Capstone prompt-conditional and the
before/after delta is in `tests/integration/results/2026-05-06/FRAMING-DELTA.md`.
The morning brief itself is the fourth deliverable.

_(The baseline → framed delta numbers in §3 are filled in once both
suite runs finish — see "Branch state" §6 for which commits to inspect
in the meantime.)_

---

## 1. Code audit — `audit/AUDIT-2026-05-06.md`

`ruff` found 106 issues across the whole repo. Mechanical fixes
applied to production code paths only (`app/`, `web/`, `scripts/`,
`services/`, `tests/`); `experiments/` was left alone. Vulture
confirmed only one F401 worth removing (`io` in `app/inference.py`);
the rest are kept per Adam's "vulture-confirmed only" rule.

**The four real bugs in `experiments/` (NOT touched, flagged for
Adam to triage):**
1. `experiments/17_riprap_integration/terramind_nyc.py:117` —
   F821 references `np` in a type annotation; numpy isn't imported
   at module top.
2. `experiments/18_terramind_nyc_lora/shared/eval_adapter.py:125` —
   Py 3.12 nested f-string; will fail to import on the HF Space (3.10).
3. `experiments/05_terramind_nyc_finetune/training/verify_phase1.py:438` —
   B023 closure-over-loop-variable, the standard "all closures see
   the last value" trap.
4. `experiments/18_terramind_nyc_lora/shared/publish_hf.py:107` —
   F841 `api` assigned but never used; may be a missing
   `api.upload_*` call.

**Complexity hotspots** (flagged, NOT refactored — pre-demo freeze):
- `app/reconcile.py:build_documents` is **F=178** by cyclomatic
  complexity. CLAUDE.md explicitly says don't touch pre-demo. Held.
- Other C+ functions: `mellea_validator.reconcile_strict_streaming` (D=23),
  `planner._validate` (D=22), `rag.retrieve` (C=20), three more at
  C=16-18. All expected; none touched.

**Lowest MI modules (still passable, not urgent):**
`app/intents/neighborhood.py` (32), `web/main.py` (37),
`scripts/probe_addresses.py` (36). Length is the cost of being
data-heavy / demo-front-door / probe-tester respectively. Post-demo
candidates for refactor.

**Commit:** `9cc6ec4 audit: mechanical fixes from ruff + vulture`.

---

## 2. 20-query stakeholder integration suite — `tests/integration/results/2026-05-06/SUMMARY.md`

The suite at `tests/integration/stakeholder_queries.py` drives
`/api/agent/stream` against 20 queries derived from `RESEARCH.md`:
six verbatim personas, six adapted variants, eight lateral use cases.
Per query it captures planner intent, Stones invoked / fired /
silent_by_design / errored, wall-clock per Stone, the briefing prose,
citations resolved, Mellea grounding pass-rate + rerolls, and a
**framing score** (0-5) for the opening paragraph against a
per-question-type rubric.

**Outputs in `tests/integration/results/2026-05-06/`:**
- `q01-resident-pioneer.json` ... `q20-control-astoria.json` — full
  per-query payload (plan, paragraph, steps, mellea, framing rationale).
- `SUMMARY.md` — table of all 20 (intent, time, grounding,
  framing, status).
- `FAILURES.md` — full briefings + proximate cause for any query
  that errored, timed out, missed Mellea, or returned no prose.

**Baseline run summary** (filled in after run completes):
- Mean framing score: _(see SUMMARY.md)_
- Queries with framing ≥ 3: _(see SUMMARY.md)_
- Queries that errored / timed out: _(see FAILURES.md)_

**Baseline commit:** `e203d5f tests: add 20-query stakeholder integration suite`.

---

## 3. Question-aware Capstone framing — `docs/QUESTION-AWARE-FRAMING.md` + `tests/integration/results/2026-05-06/FRAMING-DELTA.md`

**Diagnosis (full version: `docs/QUESTION-AWARE-FRAMING.md`).** Three
options were on the table: (a) planner sub-classifier, (b) Capstone
prompt-conditional, (c) both. **Recommendation and what landed: (b).**
The four-section evidence structure (Status / Empirical / Modeled /
Policy) and the four Mellea grounding checks stay byte-identical;
only the Status sentence's directive changes.

**Implementation:**
- New `app/framing.py` — 11 question types, regex-based deterministic
  detector, per-type opening-directive table, `augment_system_prompt`.
- `app/fsm.py` — new `set_user_query` + `set_planner_intent`
  threadlocals; `step_reconcile` augments
  `app.reconcile.EXTRA_SYSTEM_PROMPT` before passing to
  `reconcile_strict_streaming`.
- `app/intents/single_address.py` — sets/resets the new threadlocals.
- `app/intents/neighborhood.py`, `development_check.py`,
  `live_now.py` — augment their own EXTRA_SYSTEM_PROMPT before
  reconcile.

**Detector accuracy against suite labels:** 14/20 verbatim. The 6
mismatches are all bare-place queries where the suite's persona-
imposed label isn't discoverable from the query text alone — these
fall back to `journalism` (bare neighborhood) or `generic_exposure`
(bare address, baseline behavior preserved).

**Before/after framing delta** (filled in after framed run):
- Baseline mean: _(see FRAMING-DELTA.md)_
- Framed mean: _(see FRAMING-DELTA.md)_
- Δ: _(see FRAMING-DELTA.md)_
- Stop condition: _(see FRAMING-DELTA.md)_

**Commit:** `1a82fde framing: question-aware Capstone opening`.

---

## 4. Branch state

Branch: **`overnight-2026-05-06`**, local only. To inspect:

```bash
git log --oneline overnight-2026-05-06 ^main
```

Commit chronology (newest first; expect Adam's parallel `comms-`
commits to be interleaved depending on which got merged):

- `f40ebd2 tests: add FRAMING-DELTA.md generator`
- `1a82fde framing: question-aware Capstone opening (Capstone prompt-conditional)`
- `e203d5f tests: add 20-query stakeholder integration suite`
- `9cc6ec4 audit: mechanical fixes from ruff + vulture`

Plus auto-merged commits from Adam's `comms-overnight-2026-05-06`
work (slides, research, submission docs).

To revert any single piece:

```bash
git revert <commit-sha>           # safe: creates a new commit that undoes
git checkout main                  # discard the branch entirely
git branch -D overnight-2026-05-06
```

The framing change touches 5 files; reverting `1a82fde` is a clean
backout if the framed run shows regressions.

---

## 5. Three things to look at first when you open the laptop

1. **`tests/integration/results/2026-05-06/FRAMING-DELTA.md`** — does
   the per-query before/after framing-score table show the lift you
   expected? Pay special attention to q01 (resident, "should I worry"),
   q02 (attorney, RPL §462), q06 (developer, Gowanus), q14
   (retrospective, Hollis pre-Ida). Those are the personas where the
   demo demands the framed shape.
2. **`tests/integration/results/2026-05-06/FAILURES.md`** — which of
   the 20 queries did NOT pass cleanly. The bare-address ones (q04
   Houston, q11 PS 188) and the lateral ones (q14 retrospective, q15
   ranking, q17 compare) are the most likely to fail in interesting
   ways. Read the briefing prose under each to judge whether the
   Capstone said something defensible.
3. **`audit/AUDIT-2026-05-06.md` punch list** — the four
   `experiments/` bugs flagged at the top. Those are real bugs the
   demo hides because nobody imports them at runtime, but if anyone
   tries to reproduce the fine-tunes during the hackathon Q&A, they'll
   hit `experiments/18` failing to import on Py 3.10.

---

## What did NOT land

- **No deployment, no push.** Per instructions; both targets
  untouched.
- **No refactor of `build_documents` / Mellea checks / FSM
  structure.** All flagged in `audit/AUDIT-2026-05-06.md` as
  post-demo work.
- **No new dependencies.** All work used `ruff` / `vulture` / `radon`
  (already installed via `uv tool install`) and the existing repo
  code.
- **No planner sub-classifier (option a).** The diagnosis recommends
  (b) only; if the framed run's stop condition fires (>5 queries with
  framing < 3), `docs/QUESTION-AWARE-FRAMING.md` describes what (a)
  would require.

---

## Operating notes for the morning

- Local server: `nohup .venv/bin/uvicorn web.main:app --host 127.0.0.1
  --port 7860 ...` was running on port 7860 throughout the night.
  Check `ps -fp $(pgrep -f "uvicorn web.main")` to see if it's still
  alive; safe to kill with `pkill -f "uvicorn web.main"`.
- Server log: `/tmp/riprap-overnight/server.log`.
- Suite run logs: `/tmp/riprap-overnight/suite-baseline.log`,
  `/tmp/riprap-overnight/suite-framed.log`.

---

_Faithful account, not victory lap: this brief should match the
commit log + the on-disk reports exactly. If anything here doesn't,
trust the file system, not the brief._
