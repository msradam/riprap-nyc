# Overnight pass — morning brief — 2026-05-06

> Branch: `overnight-2026-05-06`. Local-only, not pushed, not deployed.
> Read this in 5 min; everything detailed lives in linked sub-reports.

## Status one-liner

All four work streams landed. The audit committed mechanical fixes
only and flagged real bugs in `experiments/` for triage. The 20-query
suite ran twice (baseline + framed) end-to-end against local Granite +
local specialists. The question-aware Capstone framing lifted mean
framing 2.25 → 2.80 and produced three verdict-style openings (q01
"Yes", q02 "Disclosure is warranted", q13 "Vulnerability assessment:")
where there were zero before. The framing's stop condition fired
(12 < 3); option (a) — planner sub-classifier — is sketched in
`docs/QUESTION-AWARE-FRAMING.md` but explicitly NOT implemented per
your "don't silently expand scope" rule. One out-of-scope geocoder
bug surfaced and is documented in
`OVERNIGHT-2026-05-06-OUT-OF-SCOPE.md` (NOT fixed).

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

**Baseline run summary:**
- 20/20 OK (no errors, no timeouts).
- Mean framing score: **2.25** (mostly stuck at 2 = "on-topic exposure
  language but no question-aware framing").
- Queries with framing ≥ 3: 5 / 20 (q06, q07, q14, q18, q19 — note q07,
  q14, q18, q19 scored 3 only because they returned the canned
  "No grounded data available for this address." which the rubric
  scores as 3 = place-referenced).
- 4 queries had Mellea 0/4: q07 (lease query, geocoder failed),
  q14 (retrospective query, geocoder failed), q15 (NYCHA ranking,
  planner mis-routed to dev_check with 0 steps), q16 (FloodNet
  live_now with no active signals), q18 (court exhibit retrospective,
  geocoder failed), q19 (BBMCR project name, NTA didn't resolve).
- The geocoder failures are documented in
  `OVERNIGHT-2026-05-06-OUT-OF-SCOPE.md` — same root cause: the
  length-ratio heuristic in `app/intents/single_address.py:33`
  rejects the planner's correctly-extracted address when the user's
  query is conversational.

**Baseline commit:** `e203d5f tests: add 20-query stakeholder integration suite`.
Per-query JSONs preserved at
`tests/integration/results/2026-05-06/baseline/`.

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

**Before/after framing delta** (full report:
`tests/integration/results/2026-05-06/FRAMING-DELTA.md`):

| Metric | Baseline | Framed | Δ |
|--------|---------:|-------:|---:|
| Mean framing | 2.25 | 2.80 | +0.55 |
| ≥ 3/5 | 5 | 8 | +3 |
| ≥ 4/5 | 2 | 5 | +3 |
| ≥ 5/5 | 0 | 3 | +3 |

**The three queries that hit 5/5** (verdict-style openings — the
demo-critical wins):
- **q01** resident habitability — opening flipped from "exposed to
  historical flood events..." to "**Yes**, this address is exposed
  to flood risk based on its inclusion within the Hurricane Sandy
  inundation zone..."
- **q02** attorney disclosure — opening flipped to "**Disclosure is
  warranted** because the site experiences moderate flood exposure
  as indicated by 56.6% of surrounding cells..."
- **q13** grant evidence — opening flipped to "**Vulnerability
  assessment**: Chinatown-Two Bridges (NTA MN0301) in Manhattan
  exhibits moderate flood exposure..."

**Mellea net change:** +4 improved (3/4 → 4/4), -2 regressed (q01
4/4 → 3/4, q06 3/4 → 2/4), 14 unchanged. Net +2 grounding checks
gained across the suite.

**Stop condition: FIRED.** 12 / 20 framed queries scored below 3
(threshold > 5 ⇒ stop). Per Adam's instruction, NOT iterating further
on the prompt-conditional. Triage of the 12 + sketch of what option
(a) — planner sub-classifier — would require lives in
`docs/QUESTION-AWARE-FRAMING.md` §"Outcome of the 2026-05-06 framed
run" + §"What option (a) would require." Headline:

- 4 / 12 are rubric-vs-directive vocabulary mismatch (bare
  neighborhood → journalism directive applied, but rubric scored
  for capital_planning markers). Not a framing failure.
- 4 / 12 are short-prose-floor failures (geocoder + planner short
  circuit). No framing change can fix these.
- 4 / 12 are cases where Granite ignored the soft directive. These
  are where option (a) would actually help.

**Commits:** `1a82fde framing: question-aware Capstone opening`,
`342dd4d framing: clarify the directive's scope`,
`f40ebd2 tests: add FRAMING-DELTA.md generator`,
`9c61976 tests: baseline + framed run results`.

---

## 4. Branch state

Branch: **`overnight-2026-05-06`**, local only. To inspect:

```bash
git log --oneline overnight-2026-05-06 ^main
```

Commit chronology (newest first; Adam's parallel `comms-` commits
get auto-merged in via the runtime so they may interleave):

- `9c61976 tests: baseline + framed run results, 2026-05-06`
- `342dd4d framing: clarify the directive's scope is the Status sentence only`
- `e81962b docs: log out-of-scope findings from the overnight pass`
- `8894517 docs: morning brief skeleton`
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

1. **`tests/integration/results/2026-05-06/FRAMING-DELTA.md`** — the
   per-query opening diff is the most useful artifact in the pass.
   Read q01, q02, q13 first (the three queries that hit 5/5 — these
   are the demo wins). Then the four "Granite ignored the directive"
   cases triaged in `docs/QUESTION-AWARE-FRAMING.md` ("Outcome of the
   2026-05-06 framed run" §3) — those are where option (a) would
   actually pay off if you decide to spend the 2-3 hours.
2. **`OVERNIGHT-2026-05-06-OUT-OF-SCOPE.md`** — one real bug
   surfaced: the planner-vs-query length-ratio threshold in
   `app/intents/single_address.py:33` rejects the planner's
   correctly-extracted address whenever the user's query is long and
   conversational. Failure mode is "No grounded data available" with
   Mellea 0/4. Hits q07 (resident lease question), q14
   (retrospective), q18 (court exhibit) — exactly the conversational
   personas the demo arc wants to handle gracefully. Suggested fix
   is in the doc; NOT applied.
3. **`audit/AUDIT-2026-05-06.md` punch list** — the four
   `experiments/` bugs flagged at the top. Real bugs the demo
   hides because nobody imports them at runtime; if anyone tries to
   reproduce the fine-tunes during the hackathon Q&A, they'll hit
   `experiments/18` failing to import on Py 3.10 (nested f-string).

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
