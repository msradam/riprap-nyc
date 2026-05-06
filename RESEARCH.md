# Riprap: landscape research

Captured 2026-05-06 as part of the AMD x lablab.ai hackathon polish
phase. This document underpins the pitch deck (`slides/deck.md`) and
the demo-script choices. Re-validate against the live web before
re-using any specific figure.

---

## What Riprap is, distinctly

A citation-grounded LLM that writes audit-quality flood-exposure
briefings for NYC addresses by fusing live, historical, modeled, and
projected data sources. Mellea rejection sampling refuses to publish
a numeric claim it can't cite. The output isn't a score. It's a
four-section prose briefing with `[doc_id]` citations on every
numeric assertion, where each `doc_id` resolves to one specific
dataset (Sandy 2012 zone, NYC DEP scenario, USGS HWM, Sentinel-2
chip, NOAA gauge reading, NPCC4 SLR projection).

Granite 4.1 8B drives the prose. Granite Embedding 278M plus GLiNER
drive policy-doc retrieval. Prithvi-EO 2.0, TerraMind LULC and
Buildings, and Granite TTM r2 drive the EO and forecast probes,
with three Apache-2.0 NYC fine-tunes trained on AMD MI300X published
on HF Hub.

Architectural commitments other tools don't make:

1. **Silence over confabulation.** When a probe returns no data, the
   briefing omits the section rather than papering over it.
2. **Five-stone epistemic structure.** The user can see what's
   empirical vs modeled vs proxy vs synthetic.
3. **Fully open-source pipeline.** Apache-2.0 end-to-end on public-
   record data, no commercial APIs touched at runtime.
4. **Deployable on either local Ollama or AMD MI300X via vLLM** with
   auto-failover.

Stack as of 2026-05-06: SvelteKit UI on HF Spaces (cpu-basic) at the
AMD-hackathon org, FastAPI agent FSM, two-container droplet (vLLM
plus riprap-models) on MI300X, full address probe suite at 5/5 PASS
in 5.8 to 13.1 s end-to-end.

---

## Landscape map

### Direct comps: score-based property risk tools

| Tool | What it gives | Who it serves | Hidden cost |
|---|---|---|---|
| **First Street Risk Factor** (Flood Factor) | Score 1 to 10 plus 30-yr risk narrative; powers Redfin, Realtor.com (until Dec 2025 also Zillow) | Homebuyers; some lenders | Closed model; commercial partnerships; Zillow removed it under industry pressure in Dec 2025 |
| **ClimateCheck** | Score 1 to 100 plus around 30-page property report; 2050 projections | Homeowners plus REIT/PE diligence | Subscription tiers; methodology behind paywall |
| **Jupiter ClimateScore Global** | Enterprise SaaS / API; financial metrics (CapEx, OpEx, credit risk) | Banks, insurers, asset managers | Enterprise pricing; not consumer-facing |
| **Cervest / Climate X / ICEYE** | Variants of above for ESG / reinsurance | Corporate finance and insurance | Same |

Score-based tools all converge on the same shape: one number, one
chart, an explainer paragraph. None show what claim is grounded in
which dataset. None expose the audit trail.

### NYC-specific government tools

- **FloodHelpNY** (City plus State, IDEO-designed). Address lookup
  to flood-zone label plus insurance plus free resiliency audit.
  Forms-based, consumer-facing, doesn't fuse live signals.
- **NYC Flood Hazard Mapper.** ArcGIS web map of FEMA, NPCC, Sandy,
  and future scenarios. Static visualization, no narrative.
- **NYC OEM Flood Maps page.** Index of the above.
- **EJNYC Flood Vulnerability Index** (released 2024-04 by Mayor's
  Office of Climate and EJ). First-ever city FVI, used to direct
  spending under NY's "Disadvantaged Communities" framework (35% of
  climate spend by law).
- **FloodNet NYC** (NYU plus CUNY plus city). Over 350 ultrasonic
  sensors at 1-min cadence, growing to 500 by end-2026. Has a public
  dashboard but no narrative layer.

### Federal / authoritative

- **FEMA Flood Map Service Center / NFHL.** Official; covers 90%+
  of population; static GIS layer plus PDFs. The disclosure-of-
  record but not a synthesis tool.

### Real-estate platforms (the volatile zone)

- **Redfin.** Still shows First Street Flood Factor on every
  listing.
- **Realtor.com.** Still shows it on 110M+ listings.
- **Zillow.** Removed climate risk display in December 2025 under
  California Regional MLS pressure. Still links out, but it's
  hidden. This created a vacuum that an open citation-grounded
  alternative could fill.

### Closest academic / AI comps

- **Flood-LLM** (Brisbane, MDPI Sustainability 2026). Multi-source
  LLM for property-level flood risk, validated on Brisbane against
  official labels. Academic, not deployed; no Mellea-style citation
  discipline; no live signals.
- **GIS-Integrated Flood LLM** (Tandfonline 2024). LLM constrained
  by a flood knowledge graph plus GIS interaction. Research artefact.
- **FloodLense** (arXiv 2024). UNet/RDN/ViT plus LLM for satellite
  flood detection. Research; image-only.

---

## Where Riprap fits: differentiators that demo well

Ranked by visibility in a 3-minute demo:

1. **Citation prose vs scores.** Riprap returns *"Hurricane Sandy
   flooded this address on October 29 to 30, 2012, according to the
   empirical inundation zone [sandy]. 19 flood-related 311 service
   requests were logged within 200 m over five years [nyc311]."*
   Every number cites a doc; each doc resolves to a footer source
   row. First Street returns "Flood Factor 8/10". This gap is the
   demo.
2. **Live, historical, modeled, projected: in one paragraph.** Sandy
   2012 (empirical), DEP 2080 stormwater scenarios (modeled), 311
   last 5 years (proxy), FloodNet last 3 years (empirical,
   hyperlocal), NPCC4 SLR (projected), Granite TTM r2 surge nowcast
   (96-h forecast). No comp combines all four temporal modes.
3. **Open-source NYC fine-tunes.** Three Apache-2.0 models
   (`Prithvi-EO-2.0-NYC-Pluvial`, `TerraMind-NYC-Adapters`,
   `Granite-TTM-r2-Battery-Surge`) trained on AMD MI300X. Anyone can
   reproduce, fork to other cities, or audit. First Street's model
   is closed; ClimateCheck's methodology is behind a paywall.
4. **AMD hardware story.** The whole stack runs on MI300X via vLLM
   (LLM) plus a sibling ROCm container (probes). All Apache-2.0.
   This is the AMD hackathon track's preferred narrative: open
   models, open infra, open data, real GPU acceleration.
5. **Mellea grounding receipts.** The four checks
   (`numerics_grounded`, `no_placeholder_tokens`, `citations_dense`,
   `citations_resolve`) are the audit. The meta card surfaces "4/4
   grounding checks passed, 1 reroll". That's audit credibility no
   consumer comp shows.
6. **Self-aware silence.** Touchstone shows "FloodNet sensor: 0
   events in 3 years" with `silent_by_design`. Lodestone shows "TTM
   Battery surge forecast: peak |residual| < 0.3 m, omitted." Most
   tools always render a value. Riprap's silence is a feature.

---

## Stakeholder demos to craft

Six concrete personas, each with a query that exercises a different
part of the system. These are the demo arcs to rehearse.

### 1. Resident / homebuyer (the FloodHelpNY swap-in)

> *"I'm thinking about renting an apartment at 80 Pioneer Street,
>  Brooklyn. Should I worry?"*

**Demo arc.** Type the address. Watch the planner classify
`single_address`, then 19 step events fire across the four data
Stones in around 13 s. Briefing names Sandy 2012 inundation, 65 311
complaints, 2 FloodNet sensors with 4 events including a 51 mm peak
on a specific date, Ida 2021 HWM 130 m away, microtopo HAND 3.81 m
plus TWI 14.79 (very high saturation propensity). Footer shows 7+
named primary sources.

**Demo hook.** "Compare what we just generated to First Street's
number-and-bar-chart for the same address. Which would you trust to
make a $4,000/month decision?"

### 2. Real-estate attorney / disclosure compliance

> *"Does 100 Gold Street, Manhattan need to disclose flood risk
>  under RPL §462(2)?"*

**Demo arc.** Same single_address path. Briefing produces a citable
narrative covering FEMA designation, prior flood claims (where
present), terrain, recent complaints. Mellea grounding check is the
qualifier: "this prose is grounded against four invariants and
passed 4/4."

**Demo hook.** New York's March-2024 amended Property Condition
Disclosure Statement requires sellers to disclose flood history and
FEMA-floodplain status. RPL §231-b requires every residential lease
to disclose prior flood damage. Riprap is the citable narrative
tool. Show how the briefing maps line-by-line to the disclosure
requirements.

### 3. NYC OEM / DEP planner

> *"Hollis, Queens"*

**Demo arc.** Neighborhood intent fires (9 step events), produces an
NTA-level briefing. 434 flood-related 311 over 3 years (87 catch-
basin clogged, 42 street-flooding), 4.3% of neighborhood projected
to flood under DEP moderate-2050 scenario, 25% of cells with HAND<1
m. RAG retrieval pulls relevant DEP/NPCC4 policy paragraphs.

**Demo hook.** DEP just announced a $30B stormwater priority list
(86 locations) and a $68M Brooklyn Bluebelt expansion in Prospect
Park. Riprap supports the prioritization argument with citable per-
NTA evidence. Pair with the EJNYC Flood Vulnerability Index for the
EJ-spending overlay (35%-to-disadvantaged-communities legal
mandate).

### 4. Insurance underwriter / actuary

> *"442 East Houston Street, Manhattan"*

**Demo arc.** Same as resident demo, but emphasize the **provenance
trace** UI. Every Stone row, every doc_id, every source URL,
vintage, and tier glyph.

**Demo hook.** When an underwriter writes a risk memo, the audit
chain matters. First Street's "we used a proprietary catastrophe
model" doesn't survive a regulator review the way "we used FEMA
Sandy 2012 polygon, NYC DEP 2021 stormwater scenario, USGS Ida HWM
Event 312, NOAA gauge 8518750, NWS station KNYC, Granite TTM r2
fine-tune (test MAE 0.1091 m vs 0.1467 zero-shot, citable)" does.

### 5. Climate journalist / advocacy

> *"Coney Island, Brooklyn"*

**Demo arc.** Neighborhood briefing. 87.5% of NTA in 2012 Sandy
zone, 382 flood complaints over 3 years, 7.8% projected flooded
under 2050 moderate, 38.9% of DEM cells with HAND<1 m, DEP extreme-
2080 at 44.2% flooded.

**Demo hook.** ProPublica/NYTimes/THE CITY-style data journalism.
Every claim in a Riprap briefing is reproducible. Anyone can paste
the same query and get a near-identical narrative. The journalist
can publish the briefing as the methods section.

### 6. Architect / developer

> *"What are they building in Gowanus and is it risky"*

**Demo arc.** Planner classifies `development_check`. FSM pulls DOB
filings plus flood layers for the project sites. Briefing comments
on which proposed buildings sit inside Sandy 2012, which intersect
DEP extreme-2080, what the microtopo says.

**Demo hook.** Pre-design siting check. The Gowanus rezoning is one
of NYC's largest active development zones, well known to flood. Show
how the tool surfaces flood concerns before architects pour
concrete.

---

## Lateral and unexpected use cases

Ten bets, ordered roughly from most-buildable to most-speculative.

1. **Pre-storm cohort briefings.** Subscribe Riprap to NWS flood-
   watch alerts. When a watch lands, fan out one briefing per
   affected NTA plus push to OEM, press, and advocacy lists. Citable
   evidence on demand for the press cycle that follows.
2. **Climate-grant evidence sections.** HUD CDBG-DR and FEMA BRIC
   applications need an auditable evidence base. Riprap auto-
   generates the "vulnerability assessment" section so a community
   group can apply for resilience funding without hiring a
   consultant.
3. **Local Law disclosure boilerplate.** Plug into a brokerage's
   listing flow. When an agent enters an address, auto-generate the
   NY RPL §231-b lease addendum or §462(2) disclosure draft. ROI is
   high since the law took effect 2024 and many landlords are still
   figuring out compliance.
4. **MTA station-hardening prioritization.** Riprap already has the
   MTA-entrance probe (KEY-001 in the demo). Run the FSM across all
   subway entrances; rank by exposure × ridership. The MTA's
   October-2025 Climate Resilience Roadmap Update is the policy
   hook.
5. **DOE school siting.** When DOE reviews proposed school sites or
   selects schools for retrofit, Riprap briefings (with `expect_311_ge`
   plus Sandy plus DEP overlays) would catch flood exposure that
   form-style screens miss.
6. **Time-machine variant.** Re-run the FSM with snapshot data from
   a past date. *"What would Riprap have said about Hollis on August
   31, 2021, the day before Ida?"* Useful for retrospective analysis,
   expert testimony, and stress-testing the system.
7. **Cross-city scaffold.** The architecture is NYC-specific by data
   choice, not by code. Port to Houston (post-Harvey plus Hurricane
   Beryl 2024), Miami (king tides), Boston (CSO floods), Charleston
   (chronic tidal), with a per-city probe set plus RAG corpus.
8. **Federation with FloodNet alerts.** When a sensor triggers a
   flood event NOW, fire a Riprap live_now briefing for the
   surrounding NTA: *"what's at stake in the next 6 hours."*
   Connects FloodNet's hyperlocal sensor reads to the OEM decision
   loop.
9. **EJNYC × Riprap pairing.** Rank all 188 NTAs by Riprap-detected
   exposure, intersect with state DAC designations. Output: a map of
   "underserved plus underwater". The most underfunded high-exposure
   neighborhoods.
10. **Court testimony / expert witness.** Citable, reproducible
    flood narrative as a court exhibit. The Mellea passes-record
    plus provenance trace are the kind of artefact a regulator or
    judge can audit. Especially relevant after the December-2025
    Zillow controversy created public discussion of climate-data
    integrity.

---

## Risks and framing

- **Real-estate industry pushback.** December 2025: Zillow removed
  First Street's climate scores under MLS pressure because the data
  was hurting transaction volume. A free, citation-grounded
  alternative could face the same reflex. Riprap's defence is that
  it's a narrative tool for professional analytical work, not a
  buy/don't-buy verdict. Keep the disclaimer footer prominent.
- **Redlining hazard.** Exposure narratives can be misused by
  landlords or insurers to discriminate against high-flood-risk
  (often disproportionately disadvantaged) neighborhoods.
  Mitigations: (a) the citation transparency makes biased reasoning
  auditable, (b) the EJNYC pairing in lateral-use #9 reframes
  exposure data as a tool *for* affected communities, not against
  them, (c) keep "for professional analytical work, not personal
  property decisions" front and center.
- **Disclosure-status liability.** A briefing is *evidence* but
  probably not *the* §462(2) disclosure under New York real-estate
  law. Don't position it as legal disclosure-of-record without a
  real-estate-attorney review.
- **Cold-start latency.** First query after droplet redeploy is
  around 30 s while models warm. For demos, ping the Space and run
  one warm-up query 5 minutes before showtime.
- **Geocoder edge cases.** "PS 188, Lower East Side" geocoded to a
  Brooklyn PS 188 in our test suite. For demos, pick fully-qualified
  street addresses; document the disambiguation behavior.

---

## Polish punch-list (deck-driven)

Concrete polish items the research surfaces, ranked by demo value:

1. **Sample-query pills on landing.** Six clickable pills below the
   search bar, one per persona above. Let the audience demo
   themselves.
2. **A "What this is" bar at the top of the landing.** Three lines:
   *"Citation-grounded NYC flood briefings. Every number cites a
   primary source. Open-source, public data, audit-grade synthesis."*
3. **Compare-mode link from the briefing.** Once Riprap delivers a
   single_address briefing, surface "compare with another address"
   as a one-click affordance. The compare intent already exists in
   the planner.
4. **EJNYC-FVI overlay** on the map sidebar (#9 above). Riprap's
   exposure × DAC designation, two clicks to a powerful editorial
   demo.
5. **First-query warm-up message** during the cold start: *"loading
   probes on AMD MI300X. First query after redeploy takes around 30
   s; subsequent queries 5 to 13 s."*

---

## Sources

- [First Street Foundation: Flood Factor methodology](https://firststreet.org/methodology/flood)
- [FloodHelpNY: NYC and IDEO consumer tool](https://www.floodhelpny.org/en)
- [ClimateCheck: flood risk methodology](https://climatecheck.com/risks/flood)
- [Jupiter Intelligence: ClimateScore Global / FloodScore](https://www.jupiterintel.com/climatescore-global)
- [FEMA Flood Map Service Center](https://msc.fema.gov/)
- [NY State: RPL §231-b residential lease flood disclosure (2023)](https://www.nysenate.gov/legislation/bills/2021/S5472)
- [NYSBA: Property Condition Disclosure flood-risk amendment (Mar 2024)](https://nysba.org/breaking-news-new-rules-on-property-condition-disclosure-and-flood-risk-go-into-effect-today/)
- [CNN: Zillow removes climate risk data under industry pressure (Dec 2025)](https://www.cnn.com/2025/12/02/climate/zillow-climate-data-extreme-weather-first-street-redfin)
- [NYC Stormwater Resiliency Plan](https://www.nyc.gov/assets/orr/pdf/publications/stormwater-resiliency-plan.pdf)
- [FloodNet NYC: methodology and sensor network](https://www.floodnet.nyc/methodology)
- [FloodNet WRR 2024: peer-reviewed sensor paper](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2023WR036806)
- [EJNYC Report: Mayor's Office of Climate and Environmental Justice](https://climate.cityofnewyork.us/ejnyc-report/the-state-of-environmental-justice-in-nyc/)
- [Flood-LLM: Brisbane case study (MDPI 2026)](https://www.mdpi.com/2071-1050/18/6/2957)
- [GIS-Integrated Flood LLM (Tandfonline 2024)](https://www.tandfonline.com/doi/full/10.1080/13658816.2024.2306167)
- [THE CITY: Disadvantaged Communities flood funding (NY Climate Law)](https://www.thecity.nyc/2022/05/02/billions-ny-climate-law-disadvantaged-communities-flood/)
- [Inman: Redfin First Street integration](https://www.inman.com/2021/02/18/redfin-starts-displaying-flood-risk-data-on-listings/)
- [FACTUM: citation-hallucination detection in long-form RAG](https://arxiv.org/pdf/2601.05866)
- [AMD x lablab.ai Developer Hackathon (May 4 to 10, 2026)](https://lablab.ai/ai-hackathons/amd-developer)
