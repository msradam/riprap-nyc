# Failures

## q01 — Resident / homebuyer (Pioneer)

- query: `I'm thinking about renting an apartment at 80 Pioneer Street, Brooklyn. Should I worry?`
- intent: `single_address` (expected `single_address`)
- wall-clock: 140.96 s
- mellea: 3/4 (rerolls=1, attempts=2)
- mellea failed: ['citations_resolve']
- timed_out: False; transport_error: None

Briefing prose:

```markdown
**Status.**
Yes, this address is exposed to flood risk based on its inclusion within the Hurricane Sandy inundation zone as documented in [sandy].

**Empirical evidence.**
The address was flooded during Hurricane Sandy on October 29‑30 2012, confirmed by the empirical 2012 inundation extent [sandy]. Within a 200 m radius, there have been 65 flood-related complaints to NYC 311 over the past five years, with notable categories including clogged catch basins (24) and sewer backups (22) [nyc311]. Additionally, within a 600 m proximity, two FloodNet sensors recorded four labeled flood events in the last three years, peaking at 51 mm depth on October 30 2025 [floodnet].

**Modeled scenarios.**
The terrain analysis indicates that this location is a topographic low point within a 200 m neighborhood, with 0.8 % of surrounding cells being lower in elevation than the address itself [microtopo]. The Topographic Wetness Index (TWI) is **14.79**, indicating a very high saturation propensity; the Height Above Nearest Drainage (HAND) is **3.81 m**, suggesting moderate urban‑block elevation above drainage [microtopo].

**Policy context.**
No specific RAG documents are cited for this address, but the presence of flood exposure suggests that local flood mitigation policies may apply, such as those from NYC’s Department of Environmental Protection (DEP) and the Office of Emergency Management (OEM). 

[doc_id] citations:
- [sandy]
- [nyc311]
- [floodnet]
- [microtopo]

The NOAA tide gauge at The Battery, 2.5 km from the address, shows an observed water level of **3.39 ft** versus a predicted astronomical tide of
```

## q06 — Architect / developer (Gowanus)

- query: `What are they building in Gowanus and is it risky`
- intent: `development_check` (expected `development_check`)
- wall-clock: 114.8 s
- mellea: 2/4 (rerolls=1, attempts=2)
- mellea failed: ['numerics_grounded', 'citations_dense']
- timed_out: False; transport_error: None

Briefing prose:

```markdown
**Status.**
56 active construction filings sit inside Carroll Gardens-Cobble Hill-Gowanus-Red Hook (NTA BK0601), with **13 (23.21%)** within the 2012 Sandy inundation zone, **13 (23.21%)** intersecting at least one DEP Stormwater scenario, and **6 (10.71%)** falling in the deeper DEP bands (1-4 ft or >4 ft) — [dob_permits].

**Flagged projects.**
- 20 Coffey St, Brooklyn (BBL 3-00589-0003). new building issued 11/26/2025; owner **20 COFFEY LLC**. In Sandy zone: True; in DEP scenarios: dep_extreme_2080; max DEP depth class: 3. [dob_permits]
- 62 Imlay Street, Brooklyn (BBL 3-00515-0050). major alteration (use/occupancy) issued 10/14/2025; owner **PRIME GROUP HOLDINGS, LLC**. In Sandy zone: True; in DEP scenarios: dep_extreme_2080, dep_moderate_2050; max DEP depth class: 3. [dob_permits]
- 570 Smith Street, Brooklyn (BBL 3-00486-0023). major alteration (use/occupancy) issued 09/30/2025; owner **570 SMITH STREET REALTY CORP**. In Sandy zone: True; in DEP scenarios: dep_extreme_2080, dep_moderate_2050; max DEP depth class: 3. [dob_permits]
- 100 Sullivan Street, Brooklyn (BBL 3-00555-0027). new building issued 08/04/2025; owner **CHEN AND LIN INC**. In Sandy zone: True; in DE
```

## q07 — Resident, disclosure-suspicion (Grand)

- query: `I just got a lease for 504 Grand Street, Lower East Side. The landlord says no flood history. Is that true?`
- intent: `single_address` (expected `single_address`)
- wall-clock: 7.85 s
- mellea: 0/4 (rerolls=0, attempts=0)
- mellea failed: []
- timed_out: False; transport_error: None

Briefing prose:

```markdown
No grounded data available for this address.
```

## q11 — DOE school siting (PS 188)

- query: `PS 188, Lower East Side`
- intent: `single_address` (expected `None`)
- wall-clock: 111.4 s
- mellea: 3/4 (rerolls=1, attempts=2)
- mellea failed: ['citations_dense']
- timed_out: False; transport_error: None

Briefing prose:

```markdown
**Status.**
The address at 188 PO MASONE WAY, Brooklyn, NY experiences moderate flood exposure due to its location on a mid-slope with significant surrounding lower elevations; **54.8%** of cells within a 200 m radius are lower, indicating potential drainage challenges [doc_id: microtopo].

**Empirical evidence.**
In the past five years, there have been **14** flood-related 311 service requests within a 200 m radius, primarily due to sewer backups (**10** instances) and catch basin clogging (**3** instances), with occasional street flooding (**1** instance) [doc_id: nyc311].

**Modeled scenarios.**
The Topographic Wetness Index (TWI) is **8.77**, classified as moderate, suggesting susceptibility to saturation under certain hydrological conditions [doc_id: microtopo]. The Height Above Nearest Drainage (HAND) of **18.86 m** indicates the address sits well above the local drainage network, reducing immediate flood risk from surface runoff [doc_id: microtopo].

**Policy context.**
No RAG documents are present for this specific address; however, NYC 311 data suggests ongoing maintenance needs related to sewer and catch basin issues, which may be addressed by municipal infrastructure programs [doc_id: nyc311].
```

## q14 — Time-machine retrospective (Hollis pre-Ida)

- query: `What would Riprap have said about Hollis on August 31, 2021, the day before Ida?`
- intent: `single_address` (expected `None`)
- wall-clock: 4.59 s
- mellea: 0/4 (rerolls=0, attempts=0)
- mellea failed: []
- timed_out: False; transport_error: None

Briefing prose:

```markdown
No grounded data available for this address.
```

## q15 — EJNYC × Riprap pairing

- query: `Rank the top 5 NYCHA developments by flood exposure, intersected with DAC designation.`
- intent: `development_check` (expected `None`)
- wall-clock: 5.65 s
- mellea: 0/4 (rerolls=0, attempts=0)
- mellea failed: []
- timed_out: False; transport_error: None

Briefing prose:

```markdown
Could not resolve target to an NTA: no NTA match in target='NYC' or query='Rank the top 5 NYCHA developments by flood exposure, intersected with DAC designation.'
```

## q16 — FloodNet alert federation (BK-018)

- query: `FloodNet sensor BK-018 just triggered. What's at stake in the next six hours within 500 m?`
- intent: `live_now` (expected `live_now`)
- wall-clock: 17.16 s
- mellea: 0/4 (rerolls=0, attempts=0)
- mellea failed: []
- timed_out: False; transport_error: None

Briefing prose:

```markdown
**Status.**
A flood surge is expected within the next 6 minutes at The Battery, NY, based on the current TTM forecast peak residual of **0.23 ft** [ttm_forecast], which exceeds recent peaks of **0.47 ft** in the context window.
**Live signals.**
- **NOAA Tide Prediction:** At 2026-05-06 02:36, the observed water level was **3.09 ft** above MLLW at The Battery, NY, with a residual of **-0.31 ft** compared to the predicted **3.4 ft**, indicating a setdown condition [noaa_tides]. - **TTM Forecast Peak Surge Residual:** A peak surge residual of **0.23 ft** is expected in about 6 minutes from now [ttm_forecast]. No active NWS alerts or additional precipitation observations are currently reported.
```

## q18 — Court testimony (Houston × Ida)

- query: `Court exhibit: flood-exposure narrative for 442 East Houston Street on the date of Hurricane Ida, September 1, 2021.`
- intent: `single_address` (expected `single_address`)
- wall-clock: 11.85 s
- mellea: 0/4 (rerolls=0, attempts=0)
- mellea failed: []
- timed_out: False; transport_error: None

Briefing prose:

```markdown
No grounded data available for this address.
```

## q19 — Capital planning, protection-shadow (BBMCR)

- query: `Brooklyn-Bridge Montgomery Coastal Resiliency project area. What's the protection envelope and what's outside it?`
- intent: `neighborhood` (expected `neighborhood`)
- wall-clock: 10.69 s
- mellea: 0/4 (rerolls=0, attempts=0)
- mellea failed: []
- timed_out: False; transport_error: None

Briefing prose:

```markdown
Could not resolve target to an NTA: no NTA match in target='Brooklyn Bridge' or query="Brooklyn-Bridge Montgomery Coastal Resiliency project area. What's the protection envelope and what's outside it?"
```

