# Riprap — Demo Video Transcript
## AMD × lablab.ai Developer Hackathon · May 4–10 2026
## Target: ~5 minutes

---

### [SLIDE 1 — Title card] · ~0:00–0:10

**SCREEN:** Slide 1. Riprap logo. "Citation-grounded NYC flood-exposure briefings, on AMD MI300X."

> Climate risk is one of the most consequential datasets in real estate and urban planning right now.
> But the tools that exist today give you a score. A number from one to ten. No explanation. No sources. Just a black box.
> We built Riprap to be the audit trail behind that number.

---

### [SLIDE 2 — The problem] · ~0:10–0:30

**SCREEN:** Slide 2. "Climate risk data is a black box." Two boxes: market scores vs Zillow pulling climate data.

> First Street gives you a flood factor. ClimateCheck gives you a percentile. Jupiter charges enterprise rates for a proprietary model.
> In November 2025, Zillow removed climate risk scores from listings entirely — under pressure from the real-estate industry.
> When a number meets resistance, the only defense is the audit trail. Riprap *is* the audit trail.

---

### [SLIDE 3 — Solution] · ~0:30–0:40

**SCREEN:** Slide 3. Screenshot of the Riprap UI — briefing prose with citation chips, map panel, stone trace.

> Type any address in New York City. Get back a written briefing where every numeric claim — every flood depth, every complaint count, every risk percentage — links to its primary public-record source.
> Federal data. City data. Apache-2.0 models. Nothing proprietary.

---

### [SLIDE 4 — Civic-tech case] · ~0:40–1:00

**SCREEN:** Slide 4. Four boxes: NY Disclosure Law, DEP Stormwater Plan, EJNYC FVI, No commercial APIs.

> New York's property disclosure law — March 2024 — requires sellers to disclose flood history. Riprap is the citable narrative that makes that disclosure meaningful.
> The DEP's $30 billion stormwater priority list covers 86 sites. Riprap provides the per-neighborhood evidence layer that backs up that ranking.
> And because every model is Apache-2.0 and every dataset is public record, environmental justice advocates can audit the same system that a developer uses. No commercial gatekeeping.

---

### [SLIDE 5 — Architecture] · ~1:00–1:30

**SCREEN:** Slide 5. "Five Stones fan out. One cited briefing comes back." Four evidence cards (Cornerstone, Keystone, Touchstone, Lodestone) + Capstone bar at bottom.

> The architecture is called Five Stones. A natural-language query hits the Planner — Granite 4.1 3B — which classifies intent and selects a specialist roster.
> Each Stone is a class of evidence. Cornerstone reads the hazard record: Sandy inundation zones, FEMA flood maps, USGS high-water marks, Prithvi satellite imagery. Keystone reads what's exposed: MTA stations, schools, hospitals, building footprints from our TerraMind NYC fine-tune. Touchstone reads what's happening now: live FloodNet sensors, 311 flood complaints, NOAA tide gauges. Lodestone looks forward: NPCC4 sea-level projections, our Granite TTM Battery surge nowcast.
> Then Capstone — Granite 4.1 8B on vLLM — synthesizes everything into a four-section briefing. Every numeric claim must cite its source, or the Mellea rejection sampler rerolls it. The briefing doesn't publish until all four grounding checks pass.

---

### [SLIDE 6 — Fine-tuning] · ~1:30–1:50

**SCREEN:** Slide 6. Three fine-tune cards: Prithvi-EO-2.0-NYC-Pluvial · TerraMind-NYC-Adapters · Granite-TTM-r2-Battery-Surge.

> We trained three NYC-specialized models on AMD MI300X hardware, all published Apache-2.0 on Hugging Face Hub.
> Prithvi-EO-2.0-NYC-Pluvial detects pluvial flooding from Sentinel-2 imagery — 0.60 IoU on the Ida test set, a 6× lift over the baseline. TerraMind-NYC-Adapters adds LoRA adapters for building footprint and land-use classification, plus 6 points of mIoU in 18 minutes of training. And Granite TTM r2 fine-tuned on the Battery tide gauge gives us a 9.6-hour surge residual nowcast at 35% lower RMSE than persistence.
> These aren't experiments. They're in production in every briefing.

---

### [SLIDE 7 — Demo intro] · ~1:50–2:00

**SCREEN:** Slide 7. "Live demo." Query text: *"I'm thinking about renting an apartment at 80 Pioneer Street, Brooklyn. Should I worry?"*

> Let's run it live. Three queries, three different intents.

---

### [DEMO CLIP 1 — Pioneer Street, single address] · ~2:00–2:40

**SCREEN:** Cut to recording `riprap-demo-20260506-234537.webm` at **t≈62s**.
- Left panel: briefing fully rendered. Title "Flood-exposure briefing · 80 Pioneer Street, Red Hook."
- Sections 01 Status through 04 Policy context visible with inline `[1]` `[2]` `[3]` citation chips.
- Right panel: Sandy flood map showing Pioneer Street pinned inside the inundation zone (blue overlay).
- Status bar: `intent: single_address · 19 specialists · attempt 1 · done`

> Thirteen seconds end-to-end. Nineteen specialists fired. The briefing tells you: Pioneer Street sits inside Hurricane Sandy's 2012 inundation zone, 0.82 metres above the nearest drainage channel, in the 78th percentile for water accumulation risk. FloodNet sensor FN-BK-018 — two blocks away — has logged four flood events since 2023. The DEP's high-intensity scenario puts the site under six inches of standing water. Every number has a footnote. Every footnote resolves to a named public dataset.

**SCREEN:** Slow scroll of left briefing panel while voiceover continues. Citation chips `[1]` `[2]` `[3]` visible inline. Bottom of panel shows section 04 "Policy context" with RAG passages from NPCC4.

> The map on the right isn't decorative — it's live. The layers are grouped by Stone, so you can see exactly which evidence tier each visual comes from.

---

### [DEMO CLIP 2 — Mellea 4/4 grounding card] · ~2:40–3:05

**SCREEN:** Recording at **t≈270s**. Right panel scrolled to Capstone section.
- Capstone card: **"grounding checks: 4/4 passed"**, rerolls=0, passed=4, attempt=1.
- Four check items: `numerics_grounded` · `no_placeholder_tokens` · `citations_dense` · `citations_resolve`

> Here's the proof. Mellea ran four grounding checks on the completed briefing: every non-trivial number appears verbatim in a source document; no template fragments leaked through; every number has a citation in the same sentence; every cited ID resolves to an actual input document.
> Four of four. First attempt. Zero rerolls.
> This is what "every number cites its source" looks like as a machine-verifiable claim, not a marketing promise.

---

### [DEMO CLIP 3 — Hollis, Queens · neighborhood intent] · ~3:05–3:30

**SCREEN:** Recording at **t≈510s**. New query: "Hollis, Queens."
- Status bar: `intent: neighborhood · 9 specialists · attempt 1 · done`
- Left panel: neighborhood briefing — NTA-level statistics, DEP stormwater scenario percentages, 311 flood complaint counts.
- Right panel: Cornerstone section with Sandy inundation percentage for the NTA + FEMA layer.

> Same system, different intent. "Hollis, Queens" is a neighborhood query — nine specialists instead of nineteen, NTA-level aggregates instead of point data. The planner classified it in under a second and dispatched the right Stone roster automatically.
> Hollis is a stormwater-flooding neighborhood, not a coastal one. The briefing reflects that: Sandy inundation is low; the DEP moderate-intensity scenario covers 22% of impervious surface; 311 flood complaints cluster around the 180th Street drainage corridor. Different geography, different risk profile, same citation standard.

---

### [DEMO CLIP 4 — Compare · Pioneer vs Gold Street] · ~3:30–4:00

**SCREEN:** Screenshot `compare-hf.jpg` — the live HF Space compare result.
- Title: "COMPARE 80 PIONEER STREET BROOKLYN TO 100 GOLD STREET MANHATTAN"
- **Key differences bar** at top: `Status: 80 vs 100` · `Empirical: 65 vs 26` · `Modeled Drainage (HAND): 3.81m vs 38.2m`
- Side-by-side Status sections — Pioneer: "exposed to flood risk, Sandy inundation zone, TWI 14.79." Gold St: "moderate flood exposure, HAND 6.42m, mid-slope position."
- Status bar: `intent: compare · 11 specialists · attempt 1 · done`

> One more. "Compare 80 Pioneer Street Brooklyn to 100 Gold Street Manhattan." The planner routes this as a compare intent — two full specialist runs, results merged side by side.
> The key differences bar surfaces the contrast immediately: Pioneer Street sits 3.81 metres above its nearest drainage channel. Gold Street at 100 is 38.2 metres. Pioneer has 65 empirical flood signals in the record; Gold Street has 26. Same city. Same storm history. Radically different exposure.
> This is the query a developer, an insurer, or a disclosure attorney actually wants to run.

---

### [SLIDE 8 — What's next] · ~4:00–4:20

**SCREEN:** Slide 8. Three boxes: Break out the Stones · Other flood-impacted cities · Historical-event mode.

> The architecture is NYC-specific by data choice, not by code.
> The five-Stone pattern generalizes: Houston, Miami, Jakarta — swap the probe sets and RAG corpus, the FSM is the same. Each Stone is already isolated enough to ship as a standalone package.
> And we want to add historical-event mode: re-run the FSM against snapshot data from before Sandy, before Ida. Validation against measured outcomes as a first-class feature, not an afterthought.

---

### [SLIDE 9 — CTA] · ~4:20–4:30

**SCREEN:** Slide 9. Dark background. "github.com/msradam/riprap-nyc" large. "Apache-2.0 · public data · AMD MI300X · IBM Granite 4.1 · Mellea grounding."

> Everything is open. Apache-2.0, public data, MIT and Apache models.
> Riprap on AMD MI300X. Try it at the link in the description.

---

## Segment map

| Segment | Source | Timestamp / asset |
|---------|--------|-------------------|
| Slides 1–7 | `slides/deck.pdf` | screen-record slide deck |
| Demo clip 1 — Pioneer briefing + map | `assets/video/riprap-demo-20260506-234537.webm` | t≈62–90s |
| Demo clip 2 — Mellea 4/4 card | `assets/video/riprap-demo-20260506-234537.webm` | t≈265–290s |
| Demo clip 3 — Hollis neighborhood | `assets/video/riprap-demo-20260506-234537.webm` | t≈505–545s |
| Demo clip 4 — Compare result | `compare-hf.jpg` (static screenshot or re-record) | n/a |
| Slides 8–9 | `slides/deck.pdf` | screen-record slide deck |

## Total runtime estimate
~4:30 — comfortable under 5 min with natural pauses.
