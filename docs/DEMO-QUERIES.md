# Demo Query Shortlist

_Generated: 2026-05-06. Based on live Space probe (AMD MI300X · vLLM) +
framed-run session notes (2026-05-06 02:21 UTC, local Ollama)._

---

## Primary arc (the three-query demo)

Together these show: resident / planner / grant-writer persona breadth,
all five Stones firing (or deterministically skipping), Granite TTM r2 +
Prithvi-EO-2.0-NYC-Pluvial + Granite Embedding 278M fine-tunes lighting up,
and the new two-column compare layout.

---

### Query 1: "I'm thinking about renting an apartment at 80 Pioneer Street, Brooklyn. Should I worry?"

**Persona:** Renter evaluating a move to Red Hook — canonical Sandy turf.
**Borough / neighborhood:** Red Hook, Brooklyn
**Intent:** `single_address`
**Verified wall-clock:** 5.7 s (live Space, AMD MI300X, 2026-05-06)
**Mellea:** 4/4, 0 rerolls (cleanest result in the suite)
**Stones fired / silent / errored:**
- Cornerstone (Sandy, DEP stormwater): fired — Sandy inside ✓, DEP outside (negative result is cited)
- Touchstone (311, FloodNet, NOAA/NWS): fired — 65 complaints, 4 FloodNet events, NOAA gauge live
- Lodestone (microtopo, Ida HWM): fired — TWI 14.79 (very high), Ida HWM 130 m away
- Keystone (TTM forecast, Prithvi-EO v2, GLiNER): fired — surge forecast, Prithvi polygon lookup, entities extracted
- Capstone (RAG + reconcile): fired — 1 RAG hit (rag_nycha 0.84), Mellea 4/4
- `prithvi_eo_live`, `terramind_synthesis`: errored (torchvision::nms on cpu-basic — known, deterministic)
**Fine-tunes invoked:** Granite TTM r2 (tide surge), Granite-TTM-r2-Battery-Surge, Prithvi-EO-2.0-NYC-Pluvial (v2 polygon), Granite Embedding 278M (RAG), GLiNER
**Briefing verdict opener:** "The address at 80 PIONEER STREET, Brooklyn, NY, is **significantly exposed to flood risk**, as it was **within the Hurricane Sandy inundation zone** on October 29–30, 2012 [sandy] and sits at a **topographic low point** with a **Topographic Wetness Index (TWI) of 14.79**, indicating very high saturation propensity [microtopo]."
**Fragility notes:** 0 rerolls on both live Space run and sessions notes baseline run. Lowest reroll risk in the suite. Geocoder resolves cleanly to Red Hook every time.

---

### Query 2: "Hollis, Queens"

**Persona:** NYC OEM/DEP capital planner looking at sewer backlog by NTA.
**Borough / neighborhood:** Hollis, NTA QN1206, Queens
**Intent:** `neighborhood`
**Verified wall-clock:** 3.9 s (live Space, AMD MI300X, 2026-05-06); 68 s (local Ollama, framed run)
**Mellea:** 4/4, 0 rerolls (live Space); 4/4, 1 reroll (framed Ollama run)
**Stones fired / silent / errored:**
- 311, DEP stormwater, microtopo: all fired
- NTA-level specialists run (8 steps total on cpu-basic Space)
- Keystone/Prithvi/TerraMind: silenced by design for neighborhood intent
**Fine-tunes invoked:** Granite Embedding 278M (RAG), GLiNER; TTM may fire for NTA-level surge context
**Briefing verdict opener:** "Hollis, located in Queens (NTA QN1206) as per [nta_resolve], experiences moderate flood exposure with significant sewer-related complaints and terrain features conducive to flooding."
**Fragility notes:** Bare NTA name — relies on planner routing `neighborhood` correctly. Has been stable across all probe runs. Low reroll risk. Wall-clock under 5 s on vLLM; well within demo patience.

---

### Query 3 (compare): "Compare 80 Pioneer Street Brooklyn to 100 Gold Street Manhattan"

**Persona:** Real-estate attorney comparing a Sandy-zone lease to a lower-risk mid-Manhattan address; or a journalist showing the contrast.
**Borough / neighborhood:** Red Hook, Brooklyn vs Financial District, Manhattan
**Intent:** `compare` (verified routing on live Space post-28a77ae fix)
**Verified wall-clock:** ~15 s (sequential PLACE A + PLACE B FSMs; estimated from step times — 5.7 s + 8.0 s + reconcile overhead; exact wall_s not captured)
**Mellea:** 4/4 PLACE A (Pioneer, 0 rerolls) + 4/4 PLACE B (Gold, 0 rerolls)
**Stones fired / silent / errored:** Full single_address FSM run for each target (24 steps each); same error pattern as Query 1 (torchvision::nms deterministic)
**Fine-tunes invoked:** Granite TTM r2, Granite-TTM-r2-Battery-Surge, Prithvi-EO-2.0-NYC-Pluvial, Granite Embedding 278M, GLiNER (all for both targets)
**Briefing verdict opener:** Two-column layout renders in the UI. PLACE A opener: "The address at 80 PIONEER STREET, Brooklyn, NY, is **significantly exposed to flood risk**…" PLACE B opener (Gold Street) contrasts — lower 311 count (26 vs 65), no Sandy inundation, Ida HWM 3.47 km away vs 130 m.
**Delta bar content:** Sandy zone: ✓ Pioneer / ✗ Gold · 311 complaints: 65 vs 26 · FloodNet events: 4 vs 1 · Ida HWM nearest: 130 m vs 3,472 m · Elevation pct\_200m lower: 0.8% vs 38.2%
**Fragility notes:** Requires compare intent to route (planner must parse two addresses from free text). Verified stable post-fix. If the planner unexpectedly returns `single_address`, PLACE B will be silently dropped — watch the plan badge in the UI before proceeding. No reroll risk on either leg.

---

## Backup queries

| Primary | Backup | Reason |
|---------|--------|--------|
| Query 1 — 80 Pioneer Street, Brooklyn | `Coney Island, Brooklyn` | Neighborhood intent; 4/4 0rr 4.7s on live Space. Different Stones surface (NTA-level DEP, 87.5% NTA in Sandy zone). Swap if Pioneer geocoder drifts. |
| Query 2 — Hollis, Queens | `Coney Island, Brooklyn` | Same neighborhood path; also 4/4 0rr 4.7s. Stronger Sandy narrative (87.5% of NTA inside Sandy 2012 extent). |
| Query 3 compare — Pioneer vs Gold | `442 East Houston Street, Manhattan` + follow-up compare | Houston alone: PASS 11.9s 4/4 but rr=2 (higher risk). No verified clean compare backup; run Houston as a single_address if compare intent fails. |

---

## Queries to avoid

| Query | Failure mode |
|-------|-------------|
| `Compare Hollis Queens to Red Hook Brooklyn` | Fragile — PLACE A (Hollis) failed `citations_resolve` 3 times, total 2 rerolls on live Space; will exceed RIPRAP_MELLEA_MAX_ATTEMPTS=3 under load |
| `Compare the Two Bridges neighborhood to Battery Park City` | Hard failure — planner emitted `compare` but backend fell through to `single_address` with "No grounded data available"; neighborhood-vs-neighborhood compare not fully wired |
| `Compare Two Bridges NTA…` (grant-writer CDBG-DR query, q13) | Safe as neighborhood solo (4/4 0rr 68s Ollama, not retested as compare target) but CDBG-DR framing not verified on live vLLM path |
| `442 East Houston Street, Manhattan` (solo) | PASS but 2 rerolls on live Space — acceptable for secondary demo, risky as opener |
| `504 Grand Street, Manhattan` (q07) | 0/4 Mellea in every session-note run; geocodes but reconcile fails |
| `What would Riprap have said about Hollis on August 31, 2021…` | `not_implemented` — retrospective intent not wired; returns 0/4 in ~5 s |
| `Court exhibit: flood-exposure narrative for 442 East Houston…` | Same `not_implemented` path; 0/4 |
| Any `live_now` query (e.g. FloodNet BK-018) | 0/4 Mellea — live_now reconcile does not currently pass grounding checks |
| `EJNYC × Riprap pairing` / BBMCR capital planning | 0/4 Mellea, 0 steps — planner routes to `development_check` but no DOB filings match; returns immediately empty |
