# Riprap scoring methodology

> Riprap produces a **flood-exposure tier (1–4) per NYC address**, not
> a calibrated damage probability. The tier is a deterministic
> literature-grounded composite of public-data signals; the language
> model writes the citing prose around it but does not score.

## 1. Why this design

Closed-methodology scores (First Street, Jupiter, Fathom) are useful
products but uncitable in civic work. A NYCEM grant writer can't quote
"0.73" in a FEMA BRIC sub-application without a defensible audit trail.
At the same time, an LLM-emitted score would be non-reproducible and
uncalibrated, with documented LLM-as-judge pathologies (Zheng et al.
2023; Wang et al. 2024). The honest middle: **a deterministic rubric a
planner can argue with**.

The tier is computed in `app/score.py` and mirrored in `web/static/app.js`.
Both implementations are kept in sync; the Python side is authoritative
for register builds and CLI exports.

## 2. Methodology pedigree

The composite construction follows a well-trodden path in the multi-
indicator vulnerability/exposure literature:

- **Cutter, Boruff & Shirley (2003)**, *Social Science Quarterly* 84(2):
  242–261. The SoVI hazards-of-place pattern: group indicators
  thematically; sum factors with equal weights because there is no
  defensible theoretical basis for differential weighting.
- **Tate (2012)**, *Natural Hazards* 63: 325–347. Explicit Monte Carlo
  sensitivity analysis showing that hierarchical equal-weighted
  composites are the most rank-stable. This is why we use equal weights
  *within* sub-indices.
- **Balica, Wright & van der Meulen (2012)**, *Natural Hazards* 64:
  73–105. Coastal City Flood Vulnerability Index, multiplicative
  (Exposure × Susceptibility / Resilience). We adopt only the
  override-behavior of multiplicative form, as a "max-empirical floor"
  (§4 below), because we have no resilience term.
- **Kim et al. (2019)**, *Scientific Reports* 9:18564. Additive vs
  geometric aggregation; additive is more transparent and reproducible
  *if* sub-indices are pre-grouped thematically. Done.

NPCC4 (2024) Ch. 3 (Rosenzweig et al., *Annals of the New York Academy
of Sciences* 1539) and the NYC Hazard Mitigation Plan 2024 supply the
NYC-specific tiering hierarchy that informs which scenarios get higher
weights inside the Regulatory sub-index.

## 3. Sub-index structure

Three thematic sub-indices, each normalized to [0, 1] by dividing the
weighted sum by the maximum possible weight in the group. The composite
is the simple sum of the three sub-indices (range 0–3).

### 3.1 Regulatory sub-index

Binary "inside zone" indicators with weights ordered by agency tiering:

| Indicator                       | Weight | Citation |
|---------------------------------|-------:|----------|
| FEMA NFHL 1% (SFHA)             | 1.00   | FEMA NFHL. Regulatory mandate threshold |
| FEMA NFHL 0.2%                  | 0.50   | FEMA NFHL. Tail scenario |
| NYC DEP Moderate-2050 + 2.5 ft  | 0.75   | NYC DEP Stormwater Maps 2021; NPCC4 Ch.3 |
| NYC DEP Extreme-2080 + SLR      | 0.50   | NYC DEP Stormwater Maps 2021. Explicitly tail |
| NYC DEP Tidal-2050              | 0.75   | NPCC4 Ch.3 coastal projection |

Why DEP-2050 outranks DEP-2080: NPCC4 designates the 2080 extreme
scenario as a **tail** projection. Closer-horizon coastal/pluvial
maps. Those a current planner can act on. Get the higher weight.

### 3.2 Hydrological sub-index

Continuous terrain measures, banded into 4 levels (1.0 / 0.66 / 0.33 / 0):

| Indicator | Weight | Bands | Citation |
|---|---:|---|---|
| HAND (m)                | 1.00 | <1, 1–3, 3–10, ≥10 | Nobre et al., 2011, *J. Hydrology* 404: 13–29 |
| TWI quartile            | 0.50 | ≥12, 10–12, 8–10, <8 | Beven & Kirkby, 1979; Sørensen et al., 2006, *HESS* 10 |
| Elev pct (200 m, inv)   | 0.50 | <10, 10–25, 25–50, ≥50 | Standard geomorphometric proxy |
| Elev pct (750 m, inv)   | 0.50 | <10, 10–25, 25–50, ≥50 | Standard geomorphometric proxy |
| Basin relief (m)        | 0.25 | ≥8, 4–8, 2–4, <2 | Supporting variable, Nobre 2011 |

TWI is half-weighted relative to HAND because TWI is documented as
noisier in flat urban DEMs (Sørensen 2006 explicitly states TWI is
site-specific and best percentile-binned). HAND remains the canonical
hydrology indicator (Aristizabal et al. 2023, *WRR* 59, NOAA NWM).

### 3.3 Empirical sub-index

Mix of binary observed-extent flags and banded count signals:

| Indicator                  | Weight | Citation |
|----------------------------|-------:|----------|
| Sandy 2012 inundation      | 1.00 + **floor** | NYC OD `5xsi-dfpx`; NYC HMP 2024 |
| USGS Ida HWM within 100 m  | 1.00 + **floor** | USGS STN Event 312 |
| USGS Ida HWM within 800 m  | 0.50   | USGS STN Event 312 |
| Prithvi-EO 2.0 Ida polygon | 0.75   | Jakubik et al., 2025 (NASA/IBM Prithvi-EO 2.0); semi-empirical |
| 311 complaint count band   | 0.75   | NYC OD `erm2-nwe9`; NYC 311-as-flood-proxy literature |
| FloodNet trigger (3 yr)    | 0.75   | FloodNet NYC; NPCC4 Ch.3 references |

The 311 and FloodNet weights are capped at 0.75 because both signals
have documented coverage and reporting bias. 311 reflects civic
engagement as well as flooding, FloodNet has uneven spatial coverage.
Sandy and HWMs are 1.0 because they're engineered ground-truth
observations.

Bands for 311 count (200 m buffer, 5-year window):

| Count   | Value |
|---------|------:|
| ≥10     | 1.00  |
| 3–9     | 0.66  |
| 1–2     | 0.33  |
| 0       | 0     |

## 4. Max-empirical floor

If **Sandy 2012 inundation** OR **a USGS Ida HWM within 100 m** fired,
the tier is capped at **2 (Elevated)**. It cannot be worse, regardless
of the additive composite.

This recovers the *important* multiplicative behaviour Balica 2012
argues for: empirical, ground-truth observations should not be
cancelled out by terrain or modeled scenarios. We implement it as a
floor (a `min(tier, 2)` after composition) rather than a full
multiplicative form so the composite remains additive and auditable.

The 100 m radius is chosen because USGS HWM positional uncertainty is
typically 5–30 m horizontal. 100 m gives ~3σ headroom for a confident
"this address was inundated" signal.

## 5. Composite → tier mapping

The composite is the sum of the three normalized sub-indices (range 0–3):

| Composite | Tier | Label                |
|-----------|-----:|----------------------|
| ≥ 1.50    | 1    | High exposure        |
| ≥ 1.00    | 2    | Elevated exposure    |
| ≥ 0.50    | 3    | Moderate exposure    |
| > 0       | 4    | Limited exposure     |
| 0         | 0    | No flagged exposure  |

Then floor: `Sandy or HWM<100m → tier ≤ 2`.

## 6. Live signals are NOT in the score

NWS active alerts, NOAA tide residual (surge), and NWS hourly precip
are **not** part of the static tier. Per **IPCC AR6 WG II** glossary
and **NPCC4** Ch. 3, exposure is a quasi-stationary property of place;
event occurrence is time-varying. Mixing the two would produce a tier
that flickers every six minutes and that residents could interpret as
neither "is my building exposed?" nor "is it flooding right now?".

Live signals are surfaced separately in the UI as a **"Current
conditions"** badge, with their own provenance (NOAA station ID, NWS
alert URL, ASOS station code), and they expire on their own cadence.
Static tier is unaffected.

This mirrors how First Street separates Flood Factor (static, 30-yr
horizon) from event-day Flood Lab products, and how Fathom separates
Global Flood Map from real-time intelligence.

## 7. Honest scope

Riprap's tier is **not**:

- A flood-damage probability or expected loss.
- A flood-insurance rating. For that, see **FEMA Risk Rating 2.0**
  (FEMA 2021), which uses claims-driven GLMs over decades of labeled
  outcome data we do not have.
- A vulnerability assessment. Engineering fragility (foundation type,
  electrical hardening, drainage), social capacity, and financial
  absorption are out of scope.
- A prediction. Future-scenario layers (DEP 2050/2080, FEMA 0.2%) are
  bounding scenarios, not forecasts.

It **is**:

- An exposure prior. A literature-grounded, deterministic, reproducible
  index of how many publicly-documented flood signals overlap this
  address.
- Auditable end-to-end: every term has a published source; every weight
  has a rationale; the floor rule has a stated motivation; the tier
  breakpoints are documented above.
- Forkable: a researcher who disagrees with any weight can edit
  `app/score.py` and rerun. The UI methodology panel makes this
  invitation explicit.

## 8. Caveats foregrounded in UI copy

These appear next to the tier badge and in the methodology disclosure:

> **Riprap tiers are not flood-damage probabilities.** They reflect
> publicly-documented exposure indicators only.

> **311 counts are influenced by neighborhood reporting habits** and
> may under-represent flooding in lower-engagement areas
> (Agonafir et al. and the broader 311-as-civic-engagement literature).

> **DEP 2050/2080 and FEMA 0.2% are bounding scenarios, not forecasts.**
> The tier reads them as "if this scenario materialized, this address
> would be inside its footprint". Not "this is the expected future."

> **Compound flooding is not separately modeled.** Concurrence of rain
> + tide + groundwater is the residual research frontier (NPCC4 Ch. 3).

## 9. Sensitivity / future work

- **Tate-style Monte Carlo perturbation** of weights to characterize
  how sensitive each tier assignment is to weight choice. Not yet
  implemented; would be a natural next research output.
- **Calibration exercise** if a labeled dataset emerges (FEMA assistance
  records, building-level damage from Sandy/Ida insurance claims). Until
  then, "calibrated" is a word we do not use.
- **Block- or NTA-level aggregation** for neighborhood-grade scoring,
  with each indicator computed as an areal aggregate rather than a
  point sample.

## References

Aristizabal, F. et al. (2023). "Improving Continental Hydrologic
Modeling Using Height Above Nearest Drainage." *Water Resources
Research* 59.

Balica, S., Wright, N., & van der Meulen, F. (2012). "A Flood
Vulnerability Index for Coastal Cities and Its Use in Assessing
Climate Change Impacts." *Natural Hazards* 64: 73–105.

Beven, K. J., & Kirkby, M. J. (1979). "A Physically Based, Variable
Contributing Area Model of Basin Hydrology." *Hydrological Sciences
Bulletin* 24(1): 43–69.

Cutter, S. L., Boruff, B. J., & Shirley, W. L. (2003). "Social
Vulnerability to Environmental Hazards." *Social Science Quarterly*
84(2): 242–261.

FEMA (2021). *NFIP Risk Rating 2.0 Methodology and Data Sources.*

Jakubik, J. et al. (2025). "Prithvi-EO 2.0: A Versatile Multi-Temporal
Foundation Model for Earth Observation Applications." NASA/IBM.

Kim, S. et al. (2019). "Assessment of Aggregation Frameworks for
Composite Indicators in Measuring Flood Vulnerability to Climate
Change." *Scientific Reports* 9:18564.

Nobre, A. D. et al. (2011). "Height Above the Nearest Drainage. A
Hydrologically Relevant New Terrain Model." *Journal of Hydrology*
404(1–2): 13–29.

NYC HMP (2024). *NYC Hazard Mitigation Plan 2024.* NYC Emergency
Management.

NYC NPCC4 (2024). *4th NYC Climate Assessment.* New York City Panel
on Climate Change. Including Rosenzweig et al., Ch. 3, *Annals NYAS*
1539.

Sørensen, R., Zinko, U., & Seibert, J. (2006). "On the Calculation of
the Topographic Wetness Index." *Hydrology and Earth System Sciences*
10: 101–112.

Tate, E. (2012). "Social Vulnerability Indices: A Comparative
Assessment Using Uncertainty and Sensitivity Analysis." *Natural
Hazards* 63: 325–347.
