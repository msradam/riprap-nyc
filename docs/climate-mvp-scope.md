# Climate-risk MVP scope for Riprap

> Working scope doc for "what hazards must Riprap cover to credibly call
> itself an open-source climate briefing tool." Sourced from
> authoritative frameworks (IPCC AR6 WG2, EPA, FEMA NRI, NPCC4, C40,
> TCFD) plus de-facto market consensus from commercial cat-modeling
> firms (First Street, ClimateCheck).

## 1. Canonical taxonomies (with sources)

### 1.1 IPCC AR6 WG2 — physical climatic impact-drivers

Authoritative scientific taxonomy:

- Temperature extremes — heatwaves, cold spells
- Precipitation extremes — heavy/extreme precipitation, shifting patterns
- Drought — hydrological + agricultural
- Wildfire — driven by heat + aridity
- Tropical cyclones / severe storms
- Floods — riverine, pluvial, coastal
- Sea level rise (chronic, distinct from acute coastal flooding)
- Cryosphere change — permafrost, glacier/snow loss
- Marine heatwaves / ocean acidification (mostly ecosystem-scale)
- Compound and cascading events (explicitly called out as emerging)

Source: [IPCC AR6 WG2 Technical Summary](https://www.ipcc.ch/report/ar6/wg2/chapter/technical-summary/)

### 1.2 FEMA National Risk Index — 18 natural hazards (13 climate-related)

US operational standard for place-based risk, county/tract resolution.
Of FEMA's 18 hazards, the **13 climate-related** ones are:

**coastal flooding, cold wave, drought, hail, heat wave, hurricane,
ice storm, inland (riverine) flooding, lightning, strong wind,
tornado, wildfire, winter weather.**

(Excluded as geologic: avalanche, earthquake, landslide, tsunami,
volcanic activity.)

Source: [FEMA NRI](https://hazards.fema.gov/nri/) · [methodology](https://www.fema.gov/sites/default/files/documents/fema_national-risk-index_methodology-hazards-overview.pdf)

### 1.3 EPA Climate Change Indicators in the United States

Organized by domain (Weather & Climate, Oceans, Snow & Ice, Health
& Society, Ecosystems). Place-relevant indicators: heat waves, heavy
precipitation, drought, river/coastal flooding, wildfires, Lyme/West
Nile, ragweed pollen, heat-related deaths.

Source: [EPA Climate Indicators](https://www.epa.gov/climate-indicators/view-indicators)

### 1.4 NPCC4 (New York City Panel on Climate Change, 4th Assessment, 2024)

NYC-specific. Scopes city's hazards to four primary stressors:

1. Sea level rise and storm surge
2. Inland and coastal flooding
3. Average and extreme temperature (heat dominant)
4. Extreme precipitation and drought

Adds equity, energy insecurity, and health as cross-cutting layers.

Source: [NPCC4 Climate Risk Summary](https://climateassessment.nyc/wp-content/uploads/2024/04/NPCC4_ClimateRiskSummary.pdf) · [climateassessment.nyc](https://climateassessment.nyc/panel/npcc4/) · [Braneon et al. 2024](https://nyaspubs.onlinelibrary.wiley.com/doi/10.1111/nyas.15116)

### 1.5 C40 City Climate Hazard Taxonomy

International city-scale. Groups: **meteorological** (storms, extreme
temperature), **hydrological** (floods, mass-movement), **climatological**
(drought, wildfire, heat/cold wave), **biological** (vector- and
water-borne disease outbreaks).

Source: [C40 City Climate Hazard Taxonomy](https://www.c40.org/researches/city-climate-hazard-taxonomy)

### 1.6 TCFD physical-risk categorization

Binary split used in finance/insurance:

- **Acute** — event-driven: hurricanes, floods, wildfires, heatwaves
- **Chronic** — long-term shifts: rising mean temperature, changing
  precipitation patterns, sea level rise, sustained drought

Source: [TCFD Hub physical risk PDF](https://www.tcfdhub.org/Downloads/pdfs/E06%20-%20Climate%20related%20risks%20and%20opportunities.pdf)

### 1.7 De-facto commercial consensus

What the leading place-based risk products ship:

| Provider | Hazards covered |
|---|---|
| **First Street Foundation** | Flood, Wildfire, Heat, Wind, Air quality (5) |
| **ClimateCheck** | Heat, Flood (pluvial/fluvial/surge/SLR), Precipitation, Drought, Wildfire, Wind/Hurricane (6) |
| **Munich Re NatCatSERVICE** | Storm, flood, wildfire, drought, extreme temperature, geophysical |
| **Verisk / AIR** | Tropical cyclone, severe thunderstorm, flood, wildfire, winter storm, extreme temperature |
| **RMS (Moody's)** | TC, flood, wildfire, severe convective storm, winter storm, climate-on-line |

Sources: [First Street methodology](https://firststreet.org/methodology) · [ClimateCheck methodology](https://climatecheck.com/our-methodologies)

**Consensus shortlist across all of the above: flood, heat, wildfire,
wind/storm, drought, air quality.**

## 2. Recommended MVP

### Tier 1 (MUST-have for a credible "climate briefing")

- **Flood** (pluvial + coastal + riverine + sewer/CSO backup) — universal across every framework. NYC reference deployment covers this. *Sources:* FEMA NFHL, NOAA Tides & Currents, USGS StreamStats/NWIS, local stormwater (NYC DEP), FloodNet-style sensors, NPCC SLR projections.

- **Extreme heat** — #1 weather-related cause of US mortality (CDC); covered by FEMA NRI, NPCC4, First Street, ClimateCheck. High equity salience. *Sources:* NOAA NWS heat indices, NLDAS-2/Daymet, Landsat/Sentinel LST, USFS Tree Canopy Cover, CDC Heat & Health Tracker, EPA EJScreen.

- **Air quality** (PM2.5, O3, wildfire smoke) — chronic + acute, equity-critical. *Sources:* EPA AirNow, EPA AQS, PurpleAir, NOAA HRRR-Smoke, NASA MAIAC AOD, OpenAQ for international.

- **Wildfire / wildfire smoke** — tier-1 across all frameworks. Even in non-fire-prone cities the smoke vector makes it nationally relevant (NYC June 2023 Canadian smoke). *Sources:* USFS Wildfire Hazard Potential, LANDFIRE, NIFC perimeters, NOAA HMS smoke plumes, USGS post-fire debris flow.

- **Severe wind / tropical & extratropical storms** — hurricane, derecho, tornado, nor'easter. Highest single-event property losses in cat-model data. *Sources:* NOAA NHC HURDAT/best-track, NWS storm events DB, ASCE 7 wind speeds, SPC tornado climatology.

- **Sea level rise** (chronic layer, separate from flood events) — listed separately by IPCC, NPCC4, TCFD. Drives horizon framing (2050/2080) that flood alone can't. *Sources:* NOAA Sea Level Rise Viewer, NASA Sea Level Change Portal, NPCC4 / regional panels, IPCC AR6 SROCC projections.

> 6 tier-1 hazards. Mirrors ClimateCheck/First Street consensus
> while adding SLR explicitly (per NPCC4 + IPCC's chronic/acute split).

### Tier 2 (next phase)

- **Drought** — tier-1 in IPCC and ClimateCheck; tier-2 here because address-level utility is lower in dense urban contexts. Required for credibility in western US deployments. *Sources:* US Drought Monitor, NOAA NIDIS, USGS groundwater.

- **Extreme cold / winter weather** (cold wave, ice storm, snow load) — cold extremes are declining in mean but persist as acute hazards; cold-related deaths still exceed heat in some northern cities. *Sources:* NWS cold/wind-chill advisories, NOHRSC snow, FEMA NRI cold-wave/ice-storm/winter-weather layers.

- **Vector-borne & climate-sensitive disease** (Lyme, West Nile, ragweed/pollen) — EPA Indicators + C40 biological category. Data is coarser. *Sources:* CDC ArboNET, CDC Lyme surveillance, NOAA pollen models.

- **Severe convective / hail** — separate FEMA NRI hazards; significant insured-loss driver. *Sources:* SPC storm reports, NOAA MRMS, ASCE 7 hail maps.

### Cross-cutting amplifiers (layers, not hazards)

- **Tree canopy / green coverage**, **shade** — features of heat & air-quality models, not standalone hazards.
- **Social vulnerability / equity** — CDC SVI, EPA EJScreen, NPCC4 equity overlays. Required as a cross-cutting layer to make any briefing credible.

## 3. The user's specific candidates — verdict

| Candidate | Verdict | Reasoning |
|---|---|---|
| **Flood** (pluvial, coastal, riverine, sewer) | **Tier 1.** Keep. | Universal. NPCC4 explicitly splits inland vs coastal — preserve in schema. |
| **Heat / extreme heat** | **Tier 1.** | Top-mortality climate hazard. |
| **Air quality** (PM2.5, O3, smoke) | **Tier 1.** | First Street's only non-event hazard. Trivially open-data. |
| **Cold / extreme cold** | **Tier 2.** | Skip for v1, add for any deployment north of ~40°N. |
| **Shade** | **Not a hazard. Feature of heat.** | Tree canopy + building-shadow are inputs to UHI/MRT, not a separate briefing dimension. |
| **Green coverage** | **Not a hazard. Vulnerability/adaptation layer.** | Modulates heat, air, pluvial flood. Expose as EJScreen-style index. |
| **Wildfire / wildfire smoke** | **Tier 1.** | Even in NYC the smoke vector is now permanent. Split "fire exposure" (low for NYC) from "smoke exposure" (real). |
| **Wind / severe storms** | **Tier 1.** | Highest insured-loss hazard nationally. |
| **Drought** | **Tier 2.** | Address-level salience is weak in dense urban contexts. |
| **Sea level rise** (separate from flood) | **Tier 1, as chronic layer.** | IPCC AR6, NPCC4, TCFD all treat SLR as distinct from flood events. |

## 4. What NOT to include in MVP

- **Ocean acidification / marine heatwaves** — ecosystem-scale, not address-relevant.
- **Agricultural impact / crop yield** — not a place-based property briefing concern.
- **Permafrost thaw / glacier / cryosphere** — geographically narrow; no useful US-urban deployment.
- **Earthquake, landslide, tsunami, volcanic, avalanche** — in FEMA NRI but **geologic, not climate**. Stay out to keep "climate briefing" framing honest.
- **Lightning** — too stochastic and low-decision-value at address scale.
- **Pollen / allergens as standalone hazard** — defer to tier-2 vector/health bundle.
- **Transition risk** (carbon policy, stranded assets) — TCFD covers it; this is a *physical*-risk briefing tool.
- **Subsidence / sinking land** — modulates SLR but data is research-grade; expose later as an SLR modifier.
- **Compound events as a tile** — IPCC AR6 emphasizes compound hazards, but they should be emergent in the LLM reconciliation narrative, not a separate category.

## 5. Comparison to existing closed-source tools

What an MVP must match for credibility:

| Hazard | First Street | ClimateCheck | RMS | Munich Re | **Riprap MVP** |
|---|---|---|---|---|---|
| Flood | ✓ | ✓ | ✓ | ✓ | **Tier 1** |
| Heat | ✓ | ✓ | climate-on-line | ✓ | **Tier 1** |
| Wildfire | ✓ | ✓ | ✓ | ✓ | **Tier 1** |
| Wind / storm | ✓ | ✓ | ✓ | ✓ | **Tier 1** |
| Air quality | ✓ | — | — | — | **Tier 1** (matches First Street; differentiator vs RMS/MunichRe) |
| Sea level rise | folded into flood | ✓ (separate) | climate-on-line | ✓ | **Tier 1** (separate, matches ClimateCheck + NPCC4) |
| Drought | — | ✓ | ✓ | ✓ | **Tier 2** |
| Cold / winter | — | — | ✓ | ✓ | **Tier 2** |
| Hail / SCS | — | — | ✓ | ✓ | **Tier 2** |
| **Equity overlay** | — | — | — | — | **Cross-cutting** (Riprap OSS differentiator; aligns with NPCC4 + C40) |

**Bottom line:** Tier-1 set matches/exceeds First Street, equals ClimateCheck on everything except drought. OSS + equity overlay is a defensible differentiator that no commercial provider currently surfaces.
