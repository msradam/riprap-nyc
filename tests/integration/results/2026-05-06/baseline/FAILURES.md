# Failures

## q02 — Real-estate attorney (Gold)

- query: `Does 100 Gold Street, Manhattan need to disclose flood risk under RPL §462(2)?`
- intent: `single_address` (expected `single_address`)
- wall-clock: 96.5 s
- mellea: 3/4 (rerolls=1, attempts=2)
- mellea failed: ['citations_resolve']
- timed_out: False; transport_error: None

Briefing prose:

```markdown
**Status.**
The address on **100 GOLD STREET, Manhattan** exhibits moderate flood exposure due to its location on a mid-slope and proximity to urban flooding indicators, as evidenced by 311 complaints and FloodNet sensor data [nyc311], [floodnet].

**Empirical evidence.**
There have been **26** flood-related 311 service requests within a **200 m radius** over the past five years, with the majority (14) related to clogged catch basins causing flooding [nyc311]. Additionally, one FloodNet sensor within **600 m** recorded a **peak flood depth of 14 mm** during a recent event on **2026-03-12** [floodnet].

**Modeled scenarios.**
The terrain analysis indicates the point elevation is **5.19 m above sea level**, with a **Topographic Wetness Index (TWI) of 9.52**, suggesting moderate saturation propensity [microtopo]. The **Height Above Nearest Drainage (HAND)** value is **6.42 m**, confirming a moderate elevation relative to the nearest drainage [microtopo]. Within a **750 m radius**, **56.6 %** of cells are lower in elevation than this address, contributing to potential surface runoff during heavy rainfall events [microtopo].

**Policy context.**
NYCHA's flood resilience efforts include **32 passive barriers** and **5 wet flood-proofing measures** across its sites, reflecting a city-wide strategy to enhance infrastructure resilience against flooding [rag_nycha]. The NYC Comptroller’s report highlights ongoing preparedness challenges, emphasizing the need for updated flash flood readiness plans [rag_comptroller].

[doc_id] 0
[doc_id] 1
[doc_id] 2
[doc_id] 3
[doc_id] 4
[doc_id] 5
```

## q04 — Insurance underwriter (Houston)

- query: `442 East Houston Street, Manhattan`
- intent: `single_address` (expected `single_address`)
- wall-clock: 123.79 s
- mellea: 3/4 (rerolls=1, attempts=2)
- mellea failed: ['citations_resolve']
- timed_out: False; transport_error: None

Briefing prose:

```markdown
**Status.**
The address is exposed to historical flood events from Hurricane Sandy and recent localized flooding, as evidenced by its inclusion in the empirical 2012 inundation zone ([sandy]) and multiple 311 flood-related complaints within a 200 m radius over the past five years ([nyc311]). **flood risk**.

**Empirical evidence.**
Hurricane Sandy directly flooded this address on October 29‑30, 2012, as confirmed by the NYC Sandy Inundation Zone data ([sandy]). Within a 200 m radius, there have been 19 flood-related 311 service requests in the last five years, with the majority (14) being catch basin clogged/flooding incidents ([nyc311]). Additionally, three sensors within 600 m of the address recorded labeled flood events in the past three years, totaling five flood occurrences ([floodnet]).

**Modeled scenarios.**
The terrain analysis indicates that the point elevation at this address is **3.0 m above sea level**, situated on a mid-slope with 48.8 % of surrounding cells within a 200 m radius being lower in elevation ([microtopo]). The Topographic Wetness Index (TWI) value of **8.92** suggests moderate saturation propensity, while the Height Above Nearest Drainage (HAND) of **3.0 m** reflects typical urban-block elevation above drainage ([microtopo]). A forecast from FloodNet predicts a peak residual of **0.13 ft**, expected to occur approximately 18 minutes from now at The Battery gauge, indicating a minor wind-driven setup component ([ttm_forecast]).

**Policy context.**
No specific RAG documents are cited for this address; however, the presence of historical flood data and recent service requests suggests that local authorities may prioritize infrastructure improvements and drainage maintenance in this area ([rag_policy]).
```

## q06 — Architect / developer (Gowanus)

- query: `What are they building in Gowanus and is it risky`
- intent: `development_check` (expected `development_check`)
- wall-clock: 107.74 s
- mellea: 3/4 (rerolls=1, attempts=2)
- mellea failed: ['citations_dense']
- timed_out: False; transport_error: None

Briefing prose:

```markdown
**Status.**
Carroll Gardens-Cobble Hill-Gowanus-Red Hook (NTA BK0601) in Brooklyn has **56 active major-construction projects** [dob_permits], with **13 (23%)** falling inside the 2012 Sandy inundation zone and **13 (23%)** within at least one DEP Stormwater scenario, including **6 (11%)** in deeper DEP bands (1-4 ft or >4 ft) [dob_permits].

**Flagged projects.**
- **20 Coffey St, Brooklyn (BBL 3-00589-0003).** new building issued 11/26/2025; owner **20 COFFEY LLC**. In Sandy zone: True; in DEP scenarios: dep_extreme_2080; max DEP depth class: 3. [dob_permits]
- **62 Imlay Street, Brooklyn (BBL 3-00515-0050).** major alteration (use/occupancy) issued 10/14/2025; owner **PRIME GROUP HOLDINGS, LLC**. In Sandy zone: True; in DEP scenarios: dep_extreme_2080, dep_moderate_2050; max DEP depth class: 3. [dob_permits]
- **570 Smith Street, Brooklyn (BBL 3-00486-0023).** major alteration (use/occupancy) issued 09/30/2025; owner **570 SMITH STREET REALTY CORP**. In Sandy zone: True; in DEP scenarios: dep_extreme_2080, dep_moderate_2050; max DEP depth class: 3. [dob_permits]
- **100 Sullivan Street, Brooklyn (BBL 3-00555-0027).** new building issued 08/04/2025; owner **CHEN AND LIN INC**. In Sandy
```

## q07 — Resident, disclosure-suspicion (Grand)

- query: `I just got a lease for 504 Grand Street, Lower East Side. The landlord says no flood history. Is that true?`
- intent: `single_address` (expected `single_address`)
- wall-clock: 10.18 s
- mellea: 0/4 (rerolls=0, attempts=0)
- mellea failed: []
- timed_out: False; transport_error: None

Briefing prose:

```markdown
No grounded data available for this address.
```

## q09 — MTA capital planner

- query: `Should the MTA prioritize hardening the Coney Island-Stillwell Av subway entrance over Brighton Beach?`
- intent: `neighborhood` (expected `None`)
- wall-clock: 105.98 s
- mellea: 3/4 (rerolls=1, attempts=2)
- mellea failed: ['citations_dense']
- timed_out: False; transport_error: None

Briefing prose:

```markdown
**Status.**
Coney Island-Sea Gate, as defined by the NYC DCP Neighborhood Tabulation Areas (NTA BK1302) within Community District BK13 Coney Island-Brighton Beach, faces **significant flood exposure**, evidenced by high historical inundation and projected future flooding impacts.

**Empirical evidence.**
During Superstorm Sandy in 2012, **87.5%** of the neighborhood was inside the inundation extent [sandy_nta]. Over the past three years, NYC 311 recorded **382** flood-related complaints within Coney Island-Sea Gate, with the top descriptors being Sewer Backup (148), Street Flooding (94), and Catch Basin Clogged/Flooding (71) [nyc311_nta].

**Modeled scenarios.**
Under a moderate stormwater scenario in 2050 with projected sea level rise, **7.8%** of the neighborhood is modeled to be flooded, with **3.1%** in the nuisance band (>4 in to 1 ft), **0.4%** in the 1‑4 ft band, and **4.3%** in the >4 ft band [dep_moderate_2050_nta]. For a more extreme scenario in 2080 with higher sea level rise, **44.2%** of the neighborhood is projected to be flooded, comprising **4.7%** in the nuisance band, **1.2%** in the 1‑4 ft band, and **38.4%** in the >4 ft band [dep_extreme_2080_nta].

**Policy context.**
The NYC Department of Environmental Protection (DEP) is actively modeling flood scenarios to inform infrastructure planning [dep_*_nta]. The current moderate stormwater scenario under present sea level rise indicates **2.1%** flooding, with **1.9%**
```

## q11 — DOE school siting (PS 188)

- query: `PS 188, Lower East Side`
- intent: `single_address` (expected `None`)
- wall-clock: 117.77 s
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
- wall-clock: 5.6 s
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
- wall-clock: 6.26 s
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
- wall-clock: 14.35 s
- mellea: 0/4 (rerolls=0, attempts=0)
- mellea failed: []
- timed_out: False; transport_error: None

Briefing prose:

```markdown
**Status.**
**Live signals.**
- Tide observation and residual from [noaa_tides]: Observed water level is 3.57 ft above MLLW, with a predicted astronomical tide of 3.78 ft, resulting in a residual setdown of -0.21 ft. - Recent peak |residual| in context window from [ttm_forecast]: The forecasted peak surge residual at The Battery, NY is 0.18 ft, expected to occur about 6 minutes from now.
```

## q17 — Compare intent (Pioneer vs Grand)

- query: `Compare 80 Pioneer Street, Brooklyn to 504 Grand Street, Manhattan for flood exposure.`
- intent: `single_address` (expected `None`)
- wall-clock: 137.23 s
- mellea: 3/4 (rerolls=1, attempts=2)
- mellea failed: ['citations_resolve']
- timed_out: False; transport_error: None

Briefing prose:

```markdown
**Status.**
The address is **exposed to flood risk**, as it was inundated by Hurricane Sandy in 2012 and experiences recurrent flooding events, indicated by 311 complaints and FloodNet sensor data [sandy], [nyc311], [floodnet].

**Empirical evidence.**
Hurricane Sandy directly flooded the location on October 29‑30, 2012, as confirmed by the empirical inundation zone [sandy]. Within a 200 m radius, there have been **65 flood-related 311 complaints** over the past five years, with notable categories including clogged catch basins and sewer backups [nyc311]. Additionally, two of four FloodNet sensors within 600 m recorded labeled flood events in the last three years, totaling **four flood incidents**, peaking at **51 mm depth** on October 30 2025 near the sensor "openly_driven_tarpon" [floodnet].

**Modeled scenarios.**
The terrain analysis shows the address as a **topographic low point** within its 200 m neighborhood, with **80 % of surrounding cells lower in elevation**, contributing to surface runoff concentration toward this location [microtopo]. The Topographic Wetness Index (TWI = 14.79) further confirms high saturation propensity, and the Height Above Nearest Drainage (HAND = 3.81 m) indicates moderate urban‑block elevation above drainage [microtopo].

**Policy context.**
The NOAA tide gauge at The Battery, 2.5 km from the address, recorded a residual of **0.17 ft** relative to astronomical predictions, suggesting minimal wind-driven surge impact at this moment [ttm_forecast]. No specific RAG documents are cited for this address; however, broader NYC flood policies may consider these observations in risk assessments [rag_nyc_flood_policy].

No additional information is
```

## q18 — Court testimony (Houston × Ida)

- query: `Court exhibit: flood-exposure narrative for 442 East Houston Street on the date of Hurricane Ida, September 1, 2021.`
- intent: `single_address` (expected `single_address`)
- wall-clock: 9.43 s
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
- wall-clock: 8.78 s
- mellea: 0/4 (rerolls=0, attempts=0)
- mellea failed: []
- timed_out: False; transport_error: None

Briefing prose:

```markdown
Could not resolve target to an NTA: no NTA match in target='Brooklyn Bridge' or query="Brooklyn-Bridge Montgomery Coastal Resiliency project area. What's the protection envelope and what's outside it?"
```

