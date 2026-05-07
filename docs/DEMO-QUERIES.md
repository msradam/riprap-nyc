# Demo Query Shortlist

_Last updated: 2026-05-06. Primary arc verified on live Space (AMD MI300X · vLLM).
50-query validation sweep run post-bugfix: 50/50 PASS, avg 11.2 s, 36/50 Mellea 4/4._

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
**Verified wall-clock:** 5.7 s (2026-05-06); **9.8 s (50-query sweep, 2026-05-06)**
**Mellea:** 4/4, 0 rerolls (cleanest result in the suite; confirmed clean in sweep)
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
**Verified wall-clock:** 3.9 s (2026-05-06); **7.0 s (50-query sweep, 2026-05-06)**
**Mellea:** 4/4, 0 rerolls (confirmed clean in sweep)
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
**Verified wall-clock:** ~15 s (estimated 2026-05-06); **20.7 s (50-query sweep, 2026-05-06)**
**Mellea:** 4/4 combined (0 rerolls) — confirmed clean in sweep
**Stones fired / silent / errored:** Full single_address FSM run for each target (24 steps each); same error pattern as Query 1 (torchvision::nms deterministic)
**Fine-tunes invoked:** Granite TTM r2, Granite-TTM-r2-Battery-Surge, Prithvi-EO-2.0-NYC-Pluvial, Granite Embedding 278M, GLiNER (all for both targets)
**Briefing verdict opener:** Two-column layout renders in the UI. PLACE A opener: "The address at 80 PIONEER STREET, Brooklyn, NY, is **significantly exposed to flood risk**…" PLACE B opener (Gold Street) contrasts — lower 311 count (26 vs 65), no Sandy inundation, Ida HWM 3.47 km away vs 130 m.
**Delta bar content:** Sandy zone: ✓ Pioneer / ✗ Gold · 311 complaints: 65 vs 26 · FloodNet events: 4 vs 1 · Ida HWM nearest: 130 m vs 3,472 m · Elevation pct\_200m lower: 0.8% vs 38.2%
**Fragility notes:** Requires compare intent to route (planner must parse two addresses from free text). Verified stable post-fix. If the planner unexpectedly returns `single_address`, PLACE B will be silently dropped — watch the plan badge in the UI before proceeding. No reroll risk on either leg.

---

## Verified clean queries (50-query sweep, 2026-05-06)

Best queries per intent type from the sweep — 0 rerolls, Mellea 4/4, fast wall-clock.

### Address (cleanest 3)

| Query | Wall-clock | Mellea | Rerolls | Notes |
|-------|-----------|--------|---------|-------|
| `I'm thinking about renting an apartment at 80 Pioneer Street, Brooklyn. Should I worry?` | 9.8 s | 4/4 | 0 | Primary demo arc. All Stones fire. |
| `Hollis, Queens` | 7.0 s | 4/4 | 0 | Also neighborhood intent — clean on both paths. |
| `100 Gold Street, Manhattan` | 10.6 s | 4/4 | 0 | Negative control: outside Sandy zone; low reroll. |

### Neighborhood (cleanest 3)

| Query | Wall-clock | Mellea | Rerolls | Notes |
|-------|-----------|--------|---------|-------|
| `Coney Island, Brooklyn` | 5.5 s | 4/4 | 0 | Fastest neighborhood in suite. 87.5% NTA in Sandy. |
| `Hunts Point, Bronx` | 5.3 s | 4/4 | 0 | Clean South Bronx probe; Bronx representation. |
| `East New York, Brooklyn` | 7.0 s | 4/4 | 0 | Inland stormwater narrative, different from coastal arc. |

### Compare (cleanest 3)

| Query | Wall-clock | Mellea | Rerolls | Notes |
|-------|-----------|--------|---------|-------|
| `Compare 80 Pioneer Street Brooklyn to 100 Gold Street Manhattan` | 20.7 s | 4/4 | 0 | Primary demo arc. Maximum delta. Cross-borough. |
| `Compare Red Hook Brooklyn to the Financial District Manhattan for flood risk` | 18.5 s | 4/4 | 0 | Neighborhood-vs-neighborhood cross-borough. |
| `Compare 157-11 Rockaway Beach Blvd Queens to 100 Gold Street Manhattan` | 15.2 s | 4/4 | 0 | Far Rockaway vs FiDi — extreme delta. |

### Planner / development check (cleanest)

| Query | Wall-clock | Mellea | Rerolls | Notes |
|-------|-----------|--------|---------|-------|
| (see "Queries to avoid" — all planner queries in sweep had rr≥2 or 0/4) | — | — | — | Planner intent is fragile for demo; prefer address/neighborhood/compare. |

---

## Backup queries

| Primary | Backup | Reason |
|---------|--------|--------|
| Query 1 — 80 Pioneer Street, Brooklyn | `Coney Island, Brooklyn` | Neighborhood intent; 4/4 0rr 5.5 s in sweep. Different Stones surface (NTA-level DEP, 87.5% NTA in Sandy zone). Swap if Pioneer geocoder drifts. |
| Query 2 — Hollis, Queens | `Hunts Point, Bronx` | 4/4 0rr 5.3 s in sweep. Shows Bronx coverage, different stormwater narrative. |
| Query 3 compare — Pioneer vs Gold | `Compare Red Hook Brooklyn to the Financial District Manhattan` | 4/4 0rr 18.5 s. Neighborhood-vs-neighborhood; cleaner than address parsing if planner struggles. |

---

## Queries to avoid

| Query | Failure mode |
|-------|-------------|
| `What was the flood situation at 750 Baychester Avenue, Bronx during Ida?` | `not_implemented` — "during Ida" triggers retrospective intent; returns 0/4 in 0.03 s. Confirmed in 50-query sweep. |
| `What's the storm surge risk for 157-11 Rockaway Beach Blvd, Queens?` | All specialists errored (0.0s wall-clock per specialist); 0/4 Mellea, 1.6 s total. Geocoder likely fails on this address format; reword as neighborhood ("Far Rockaway, Queens") instead. |
| `What's the flood risk at 325 Hudson Street, Manhattan?` | 2/4 Mellea with 2 rerolls — citations_resolve and numerics_grounded both failing. Hudson Square has sparse source data; risky for demo. |
| All planner/development-check queries | rr≥2 across the board in sweep (q031, q035, q039, q044, q048). Development-check intent sparse on citations; reconciler hits MAX_ATTEMPTS. Avoid on demo. |
| `Compare Canarsie Brooklyn to Park Slope Brooklyn` | 3/4 Mellea, 3 rerolls, 24.2 s — slowest same-borough compare in sweep. Use cross-borough compares instead. |
| `Compare Mott Haven Bronx to Hunts Point Bronx` | 4/4 but 3 rerolls, 28.0 s — slowest query in sweep. Both NTAs have sparse sensor data. |
| `Compare Hollis Queens to Red Hook Brooklyn` | Fragile (prior run) — PLACE A (Hollis) failed `citations_resolve`; will exceed MAX_ATTEMPTS under load. |
| `Compare the Two Bridges neighborhood to Battery Park City` | Hard failure — planner fell through to `single_address`; neighborhood-vs-neighborhood compare fragile. |
| `442 East Houston Street, Manhattan` (solo) | 2 rerolls historically — acceptable secondary, risky as opener. |
| `504 Grand Street, Manhattan` | 0/4 Mellea in every run; geocodes but reconcile fails. |
| Any `live_now` query (e.g. FloodNet BK-018) | 0/4 Mellea — live_now reconcile does not pass grounding checks. |
| `What would Riprap have said about Hollis on August 31, 2021…` | `not_implemented` — retrospective intent not wired. |
| `EJNYC × Riprap pairing` / BBMCR capital planning | 0/4 Mellea, 0 steps — planner routes to `development_check` but no DOB filings match. |
