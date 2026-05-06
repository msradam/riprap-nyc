# Question-aware framing — before/after delta

Compares two runs of `tests/integration/stakeholder_queries.py`:

- **baseline**: `tests/integration/results/2026-05-06/baseline` — system before `app/framing.py`
- **framed**:   `tests/integration/results/2026-05-06/framed` — same suite, Capstone now augmented with a per-question-type opening directive

Framing score is 0–5 (5 = opening directly answers the user's question shape; 3 = generic Status with place named; 1 = no engagement). The same scorer runs against both runs.

## Aggregate

| Metric | Baseline | Framed | Δ |
|--------|---------:|-------:|---:|
| n queries | 20 | 20 | — |
| sum framing | 45 | 56 | +11 |
| mean framing | 2.25 | 2.80 | +0.55 |
| ≥ 3/5 | 5 | 8 | +3 |
| ≥ 4/5 | 2 | 5 | +3 |
| ≥ 5/5 | 0 | 3 | +3 |

## Per-query detail

| # | Persona | Q-type | Frame | Mellea | Wall | Δ frame |
|---|---------|--------|------:|-------:|-----:|---------|
| 01 | Resident / homebuyer (Pioneer) | habitability_decision | 2→5 | 4→3/4 | 141s | **+3** |
| 02 | Real-estate attorney (Gold) | legal_disclosure | 2→5 | 3→4/4 | 134s | **+3** |
| 03 | NYC OEM/DEP planner (Hollis) | capital_planning | 2→2 | 4→4/4 | 68s | +0 |
| 04 | Insurance underwriter (Houston) | underwriting | 2→2 | 3→4/4 | 91s | +0 |
| 05 | Climate journalist (Coney Island) | journalism | 2→2 | 4→4/4 | 75s | +0 |
| 06 | Architect / developer (Gowanus) | development_siting | 4→4 | 3→2/4 | 115s | +0 |
| 07 | Resident, disclosure-suspicion (Gra | habitability_decision | 3→3 | 0→0/4 | 8s | +0 |
| 08 | NYCHA-in-flood-zone planner (Hammel | capital_planning | 2→2 | 4→4/4 | 60s | +0 |
| 09 | MTA capital planner | comparison | 2→2 | 3→4/4 | 67s | +0 |
| 10 | Planner — NYCHA + Sandy memory (Red | capital_planning | 2→2 | 4→4/4 | 64s | +0 |
| 11 | DOE school siting (PS 188) | development_siting | 2→2 | 3→3/4 | 111s | +0 |
| 12 | Planner — protected neighborhood (B | capital_planning | 2→2 | 4→4/4 | 71s | +0 |
| 13 | Climate-grant evidence (Two Bridges | grant_evidence | 2→5 | 4→4/4 | 68s | **+3** |
| 14 | Time-machine retrospective (Hollis  | retrospective | 3→3 | 0→0/4 | 5s | +0 |
| 15 | EJNYC × Riprap pairing | comparison | 2→2 | 0→0/4 | 6s | +0 |
| 16 | FloodNet alert federation (BK-018) | emergency_response | 0→2 | 0→0/4 | 17s | **+2** |
| 17 | Compare intent (Pioneer vs Grand) | comparison | 2→2 | 3→4/4 | 102s | +0 |
| 18 | Court testimony (Houston × Ida) | retrospective | 3→3 | 0→0/4 | 12s | +0 |
| 19 | Capital planning, protection-shadow | capital_planning | 4→4 | 0→0/4 | 11s | +0 |
| 20 | Neighborhood control case (Astoria) | journalism | 2→2 | 4→4/4 | 113s | +0 |

## Opening sentence diff

### q01 — Resident / homebuyer (Pioneer)

_Question_: `I'm thinking about renting an apartment at 80 Pioneer Street, Brooklyn. Should I worry?`

Baseline opening:

> The address at 80 PIONEER STREET, Brooklyn is **exposed to historical flood events from Hurricane Sandy and ongoing localized flooding**, as evidenced by its inclusion within the empirical 2012 inundation extent ([sandy]) and frequent flood-related complaints in recent years ([nyc311]).

Framed opening:

> Yes, this address is exposed to flood risk based on its inclusion within the Hurricane Sandy inundation zone as documented in [sandy].

_Frame: 2 → 5; detector matched type: `on-topic exposure language but no question-aware framing` → `verdict marker matched: /\b(yes|no)\b[,.]/`_

### q02 — Real-estate attorney (Gold)

_Question_: `Does 100 Gold Street, Manhattan need to disclose flood risk under RPL §462(2)?`

Baseline opening:

> The address on **100 GOLD STREET, Manhattan** exhibits moderate flood exposure due to its location on a mid-slope and proximity to urban flooding indicators, as evidenced by 311 complaints and FloodNe

Framed opening:

> Disclosure is warranted because the site experiences moderate flood exposure as indicated by 56.6% of surrounding cells being lower in elevation within a 750 m radius, suggesting susceptibility to sur

_Frame: 2 → 5; detector matched type: `on-topic exposure language but no question-aware framing` → `verdict marker matched: /\b(disclosure|disclose) (is )?(required|not required|tr`_

### q03 — NYC OEM/DEP planner (Hollis)

_Question_: `Hollis, Queens`

Baseline opening:

> Hollis (NTA QN1206), located within Community District QN12 Jamaica-St.

Framed opening:

> Hollis, located in Queens (NTA QN1206) as per [nta_resolve], experiences moderate flood exposure with significant sewer-related complaints and terrain features conducive to flooding.

_Frame: 2 → 2; detector matched type: `on-topic exposure language but no question-aware framing` → `on-topic exposure language but no question-aware framing`_

### q04 — Insurance underwriter (Houston)

_Question_: `442 East Houston Street, Manhattan`

Baseline opening:

> The address is exposed to historical flood events from Hurricane Sandy and recent localized flooding, as evidenced by its inclusion in the empirical 2012 inundation zone ([sandy]) and multiple 311 flood-related complaints within a 200 m radius over the past five years ([nyc311]).

Framed opening:

> The address at 442 EAST HOUSTON STREET, Manhattan is **exposed to historical flood events from Hurricane Sandy** and recent localized flooding incidents, as evidenced by its inclusion within the empir

_Frame: 2 → 2; detector matched type: `on-topic exposure language but no question-aware framing` → `on-topic exposure language but no question-aware framing`_

### q05 — Climate journalist (Coney Island)

_Question_: `Coney Island, Brooklyn`

Baseline opening:

> Coney Island-Sea Gate (NTA BK1302) in Brooklyn faces **significant flood exposure**, as evidenced by high historical inundation from Hurricane Sandy and substantial modeled flooding under future sea-l

Framed opening:

> Coney Island-Sea Gate (NTA BK1302) in Brooklyn experiences significant flood exposure, as evidenced by 87.5% of its area being inundated during Hurricane Sandy [sandy_nta].

_Frame: 2 → 2; detector matched type: `on-topic exposure language but no question-aware framing` → `on-topic exposure language but no question-aware framing`_

### q06 — Architect / developer (Gowanus)

_Question_: `What are they building in Gowanus and is it risky`

Baseline opening:

> Carroll Gardens-Cobble Hill-Gowanus-Red Hook (NTA BK0601) in Brooklyn has **56 active major-construction projects** [dob_permits], with **13 (23%)** falling inside the 2012 Sandy inundation zone and *

Framed opening:

> 56 active construction filings sit inside Carroll Gardens-Cobble Hill-Gowanus-Red Hook (NTA BK0601), with **13 (23.21%)** within the 2012 Sandy inundation zone, **13 (23.21%)** intersecting at least o

_Frame: 4 → 4; detector matched type: `topic marker matched: /construction|development|filing|permit|DOB/ (no verdict)` → `topic marker matched: /construction|development|filing|permit|DOB/ (no verdict)`_

### q07 — Resident, disclosure-suspicion (Grand)

_Question_: `I just got a lease for 504 Grand Street, Lower East Side. The landlord says no flood history. Is that true?`

Baseline opening:

> No grounded data available for this address.

Framed opening:

> No grounded data available for this address.

_Frame: 3 → 3; detector matched type: `place reference only: /this address|this location|this property/` → `place reference only: /this address|this location|this property/`_

### q08 — NYCHA-in-flood-zone planner (Hammels)

_Question_: `Hammels Houses, Rockaway`

Baseline opening:

> Rockaway Beach-Arverne-Edgemere (NTA QN1402) in Queens faces **significant flood exposure**, as evidenced by high historical inundation and projected future flooding.

Framed opening:

> Rockaway Beach-Arverne-Edgemere (NTA QN1402), located in Community District QN14 The Rockaways of Queens, experiences **significant flood exposure**, as evidenced by 88.1% inundation during Hurricane 

_Frame: 2 → 2; detector matched type: `on-topic exposure language but no question-aware framing` → `on-topic exposure language but no question-aware framing`_

### q09 — MTA capital planner

_Question_: `Should the MTA prioritize hardening the Coney Island-Stillwell Av subway entrance over Brighton Beach?`

Baseline opening:

> Coney Island-Sea Gate, as defined by the NYC DCP Neighborhood Tabulation Areas (NTA BK1302) within Community District BK13 Coney Island-Brighton Beach, faces **significant flood exposure**, evidenced 

Framed opening:

> Coney Island-Sea Gate (NTA BK1302) in Brooklyn exhibits **high flood exposure**, with 87.5% of its area inundated during Hurricane Sandy [sandy_nta] and significant modeled flooding under future sea-l

_Frame: 2 → 2; detector matched type: `on-topic exposure language but no question-aware framing` → `on-topic exposure language but no question-aware framing`_

### q10 — Planner — NYCHA + Sandy memory (Red Hook)

_Question_: `Red Hook`

Baseline opening:

> Carroll Gardens-Cobble Hill-Gowanus-Red Hook (NTA BK0601) in Brooklyn faces **significant flood exposure**, as evidenced by substantial historical inundation and ongoing flood-related complaints.

Framed opening:

> Carroll Gardens-Cobble Hill-Gowanus-Red Hook (NTA BK0601) in Brooklyn experiences significant flood exposure, as evidenced by 40.6% of its area being inundated during Hurricane Sandy [sandy_nta].

_Frame: 2 → 2; detector matched type: `on-topic exposure language but no question-aware framing` → `on-topic exposure language but no question-aware framing`_

### q11 — DOE school siting (PS 188)

_Question_: `PS 188, Lower East Side`

Baseline opening:

> The address at 188 PO MASONE WAY, Brooklyn, NY experiences moderate flood exposure due to its location on a mid-slope with significant surrounding lower elevations; **54.8%** of cells within a 200 m r

Framed opening:

> The address at 188 PO MASONE WAY, Brooklyn, NY experiences moderate flood exposure due to its location on a mid-slope with significant surrounding lower elevations; **54.8%** of cells within a 200 m r

_Frame: 2 → 2; detector matched type: `on-topic exposure language but no question-aware framing` → `on-topic exposure language but no question-aware framing`_

### q12 — Planner — protected neighborhood (BPC)

_Question_: `Battery Park City`

Baseline opening:

> The Financial District-Battery Park City (NTA MN0101) in Manhattan faces **significant flood exposure**, as evidenced by substantial historical and projected inundation extents.

Framed opening:

> Financial District-Battery Park City (NTA MN0101) in Manhattan experiences moderate flood exposure, with 38.5% of its area inundated during Hurricane Sandy [sandy_nta] and modeled scenarios indicating

_Frame: 2 → 2; detector matched type: `on-topic exposure language but no question-aware framing` → `on-topic exposure language but no question-aware framing`_

### q13 — Climate-grant evidence (Two Bridges)

_Question_: `Generate the vulnerability assessment section for a HUD CDBG-DR application for the Two Bridges NTA, Manhattan.`

Baseline opening:

> Chinatown-Two Bridges (NTA MN0301) in Manhattan faces **significant flood exposure**, as evidenced by substantial historical inundation and ongoing community reports.

Framed opening:

> Vulnerability assessment: Chinatown-Two Bridges (NTA MN0301) in Manhattan exhibits moderate flood exposure, with significant historical inundation from Hurricane Sandy and ongoing concerns from curren

_Frame: 2 → 5; detector matched type: `on-topic exposure language but no question-aware framing` → `verdict marker matched: /vulnerabilit(y|ies) (assessment|profile|evidence)/`_

### q14 — Time-machine retrospective (Hollis pre-Ida)

_Question_: `What would Riprap have said about Hollis on August 31, 2021, the day before Ida?`

Baseline opening:

> No grounded data available for this address.

Framed opening:

> No grounded data available for this address.

_Frame: 3 → 3; detector matched type: `place reference only: /this address|this neighborhood/` → `place reference only: /this address|this neighborhood/`_

### q15 — EJNYC × Riprap pairing

_Question_: `Rank the top 5 NYCHA developments by flood exposure, intersected with DAC designation.`

Baseline opening:

> Could not resolve target to an NTA: no NTA match in target='NYC' or query='Rank the top 5 NYCHA developments by flood exposure, intersected with DAC designation.'

Framed opening:

> Could not resolve target to an NTA: no NTA match in target='NYC' or query='Rank the top 5 NYCHA developments by flood exposure, intersected with DAC designation.'

_Frame: 2 → 2; detector matched type: `on-topic exposure language but no question-aware framing` → `on-topic exposure language but no question-aware framing`_

### q16 — FloodNet alert federation (BK-018)

_Question_: `FloodNet sensor BK-018 just triggered. What's at stake in the next six hours within 500 m?`

Baseline opening:

> 

Framed opening:

> A flood surge is expected within the next 6 minutes at The Battery, NY, based on the current TTM forecast peak residual of **0.23 ft** [ttm_forecast], which exceeds recent peaks of **0.47 ft** in the 

_Frame: 0 → 2; detector matched type: `no opening prose to score` → `on-topic exposure language but no question-aware framing`_

### q17 — Compare intent (Pioneer vs Grand)

_Question_: `Compare 80 Pioneer Street, Brooklyn to 504 Grand Street, Manhattan for flood exposure.`

Baseline opening:

> The address is **exposed to flood risk**, as it was inundated by Hurricane Sandy in 2012 and experiences recurrent flooding events, indicated by 311 complaints and FloodNet sensor data [sandy], [nyc31

Framed opening:

> The address at 80 PIONEER STREET, Brooklyn, NY (BBL: 3005310031) is **exposed to higher flood risk than comparable inland locations**, as it was **flooded by Hurricane Sandy in 2012** ([sandy]) and si

_Frame: 2 → 2; detector matched type: `on-topic exposure language but no question-aware framing` → `on-topic exposure language but no question-aware framing`_

### q18 — Court testimony (Houston × Ida)

_Question_: `Court exhibit: flood-exposure narrative for 442 East Houston Street on the date of Hurricane Ida, September 1, 2021.`

Baseline opening:

> No grounded data available for this address.

Framed opening:

> No grounded data available for this address.

_Frame: 3 → 3; detector matched type: `place reference only: /this address|this neighborhood/` → `place reference only: /this address|this neighborhood/`_

### q19 — Capital planning, protection-shadow (BBMCR)

_Question_: `Brooklyn-Bridge Montgomery Coastal Resiliency project area. What's the protection envelope and what's outside it?`

Baseline opening:

> Could not resolve target to an NTA: no NTA match in target='Brooklyn Bridge' or query="Brooklyn-Bridge Montgomery Coastal Resiliency project area.

Framed opening:

> Could not resolve target to an NTA: no NTA match in target='Brooklyn Bridge' or query="Brooklyn-Bridge Montgomery Coastal Resiliency project area.

_Frame: 4 → 4; detector matched type: `topic marker matched: /planning|investment|infrastructure|hardening|resilien(ce|` → `topic marker matched: /planning|investment|infrastructure|hardening|resilien(ce|`_

### q20 — Neighborhood control case (Astoria)

_Question_: `Astoria, Queens`

Baseline opening:

> Astoria (Central), located in Queens as per [nta_resolve], exhibits moderate flood exposure with significant sewer-related issues.

Framed opening:

> Astoria (Central), located in Queens as defined by NTA QN0103, exhibits moderate flood exposure with 2.7% of its area projected to be flooded under current and moderate future sea-level rise scenarios

_Frame: 2 → 2; detector matched type: `on-topic exposure language but no question-aware framing` → `on-topic exposure language but no question-aware framing`_

## Stop-condition check

Queries with framing < 3 in the framed run: **12**.

**Threshold exceeded.** Per Adam's stop condition, this means the Capstone prompt-conditional alone is insufficient. The next step would be option (a) — planner sub-classifier — or option (c) — both. Documented but NOT implemented in this overnight pass.
