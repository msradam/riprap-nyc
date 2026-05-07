# Riprap — Demo Narration (Final)
## AMD × lablab.ai Developer Hackathon · May 4–10 2026
## Target: 5 minutes · Voice-over recorded in post-production

---

### Pre-roll (0:00–0:20) — Stakes

**SCREEN:** Title card. Riprap logo. "Flood risk analysis for any NYC address."

> In October 2012, Hurricane Sandy killed 43 New Yorkers. In September 2021, Hurricane Ida killed 13 more, mostly in basement apartments.
>
> The flood evidence existed both times. Scattered across eight federal, state, and city data sources. Nobody synthesized it for the people exposed.
>
> Riprap is a multi-agent AI system that does.

---

### Query 1 — 80 Pioneer Street, Brooklyn (0:20–1:30)

**SCREEN:** Browser. Riprap UI. Type "80 Pioneer Street, Brooklyn" into the query field.

> Here is an address in Red Hook, Brooklyn. 80 Pioneer Street. Ground zero for Sandy in 2012.

**SCREEN:** Stream begins. Stone trace appears on the right. Progress events: geocode, Sandy zone, DEP scenarios, Ida marks, FloodNet, 311, NOAA, TTM surge.

> The system fans out across five specialist agents. Cornerstone reads what the ground remembers: Sandy inundation, Ida high-water marks, USGS microtopography. Touchstone watches what is happening now: FloodNet sensors on the block, NYC 311 history, NOAA tide gauge.

**SCREEN:** Briefing fully renders. Left panel shows four sections with inline citation chips [1] [2] [3]. Right panel: Sandy flood map with Pioneer Street pinned inside the blue inundation zone.

> Thirteen seconds. Every numeric claim cites its source.
>
> Sandy zone. 65 flood-related 311 complaints in the record. FloodNet sensor two blocks away logged four flood events since 2023. HAND value of 0.82 meters: this address sits lower than 78 percent of its surrounding terrain, which is exactly the topographic signature that channels water.
>
> Every number has a footnote. Every footnote resolves to a named public dataset.
>
> This is what the people who lived here in 2012 should have had.

---

### Query 2 — Hollis, Queens (1:30–2:45)

**SCREEN:** Clear query. Type "Hollis, Queens."

> Different shape. A planner at NYC DEP scoping where the next stormwater priority investment should land. Neighborhood scale, not a single address.

**SCREEN:** Stream begins. Fewer steps in the trace: 9 specialists instead of 19. Status bar shows "intent: neighborhood."

> Same five agents. Different evidence weights at the neighborhood level.

**SCREEN:** Briefing renders. NTA-level statistics: DEP stormwater scenario percentages, 311 complaint counts, no coastal Sandy zone.

> 434 flood-related 311 complaints over three years in this neighborhood. The DEP moderate-2050 scenario projects 4.3 percent of cells flooding. Hollis is a stormwater-flooding neighborhood, not a coastal one. The briefing reflects that: Sandy inundation is low; the risk is interior drainage.
>
> Six seconds. The system adapted to who was asking and what the evidence actually says.

---

### Query 3 — Two Bridges grant application (2:45–4:00)

**SCREEN:** Clear query. Type: "Generate the vulnerability assessment section for a HUD CDBG-DR application for the Two Bridges NTA, Manhattan."

> And the longer query. A community group writing a HUD CDBG-DR vulnerability assessment for Two Bridges in Lower Manhattan. Natural language, not an address lookup.

**SCREEN:** Stream begins. Planner routes as single address or neighborhood intent. Specialists fire: TerraMind LULC, NPCC4 sea-level projections, EJNYC Flood Vulnerability Index, 311, FloodNet, tide gauge.

> TerraMind LULC classifies the land-use footprint from satellite imagery. NPCC4 sea-level-rise projections give the policy-horizon numbers. EJNYC Flood Vulnerability Index situates the NTA in the city's equity landscape.

**SCREEN:** Briefing renders in policy-grade language: four sections, citations dense throughout.

> The briefing format reads as planning evidence, written for the people who write the grants and carry the stamps.
>
> This is civic-tech infrastructure for the work of building resilience.

---

### Architecture beat (4:00–4:30)

**SCREEN:** Slide: "Three Apache-2.0 NYC fine-tunes on MI300X."

> Three Apache-2.0 fine-tunes did the heavy ML lifting, all trained on AMD MI300X.
>
> Prithvi-EO 2.0 for satellite-attributable flood detection: IoU 0.598, six times the baseline. TerraMind-NYC for land-use and building footprints: mIoU 0.587, 18 minutes of training. Granite-TTM-r2 for surge nowcasts: RMSE 0.157 meters, 35 percent below persistence.
>
> Five specialist agents. Three fine-tunes doing the sensing. One cited briefing per query. Public-record data only. No commercial APIs at runtime.

---

### Closing (4:30–5:00)

**SCREEN:** CTA slide. Dark background. "github.com/msradam/riprap-nyc."

> Riprap refuses to stay silent about evidence the people exposed deserve to see. It also refuses to make things up. When a Stone has no evidence, the UI says so. When the system cannot cite a claim, it does not ship the claim.
>
> Open-source. Apache-2.0. github.com/msradam/riprap-nyc.
>
> NYC flooding is the first domain.

---

## Segment map

| Segment | What is on screen | Duration |
|---|---|---|
| Pre-roll | Title card slide | 0:00–0:20 |
| Query 1 — Pioneer Street | Live browser: query to rendered briefing | 0:20–1:30 |
| Query 2 — Hollis | Live browser: neighborhood intent | 1:30–2:45 |
| Query 3 — Two Bridges | Live browser: long policy query | 2:45–4:00 |
| Architecture | Slide: Three fine-tunes on MI300X | 4:00–4:30 |
| Closing | CTA slide | 4:30–5:00 |

Total: 5:00 with natural pauses.

---

*This narration is voiced over the recorded browser footage. The recording has no live audio. Read at a comfortable engineering cadence: confident, not rushed.*
