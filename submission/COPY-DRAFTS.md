# Submission copy drafts — AMD x lablab.ai hackathon

Prepared 2026-05-07. Voice: civic-tech-clean, precise, understated.
Numbers from RESEARCH.md and probe_addresses.py. No invented statistics.

---

## Project title (max 50 characters)

Three options, each fits in 50 chars:

**Option A (recommended):** `Riprap — Cited NYC flood briefings on AMD`
(42 chars) — Names the project, names the output type, names the
platform. No adjectives. The word "cited" is load-bearing: it's the
differentiator in one word.

**Option B:** `Riprap: citation-grounded flood briefings`
(41 chars) — "Citation-grounded" is the project's defining
term; it front-loads the architectural commitment. Slightly more
technical than A.

**Option C:** `Riprap — NYC flood risk, every claim cited`
(41 chars) — Plain English, consumer-accessible. Weaker for a
technical hackathon audience.

---

## Short description (max 255 characters)

Three options:

**Option A (recommended):**
Riprap writes NYC flood-exposure briefings where every numeric claim cites its source — or doesn't appear. Granite 4.1 8B on AMD MI300X, three Apache-2.0 NYC fine-tunes, Mellea citation grounding. 5/5 addresses, 4/4 checks every run.
(237 chars)

Rationale: leads with the output, names the citation discipline in
plain English, names the GPU platform and the three fine-tune
artifacts, closes with the receipts. No adjectives. Ends on a
verifiable number.

**Option B:**
Three AMD MI300X fine-tuned models. Five evidence layers. One cited briefing. Riprap takes any NYC address, fans out across Sandy 2012 data, live FloodNet sensors, 311 history, and surge forecasts, then returns a 4-section paragraph with doc_id citations on every number.
(255 chars — exact limit)

Rationale: leads with the Fine-Tuning track evidence (the AMD
hardware claim), then explains the system. Denser; may be harder
to parse at a skim.

**Option C:**
Type a NYC address. Riprap runs five data probes — Sandy 2012 inundation, live sensors, 311 history, DEP scenarios, surge forecasts — and writes a cited flood briefing. IBM Granite 4.1 on AMD MI300X. Apache-2.0. Public data only.
(229 chars)

Rationale: most conversational, demo-first. Weakest on the
hackathon-track argument.

---

## Long description (~250–300 words)

Riprap is a citation-grounded flood-exposure briefing tool for NYC
addresses, built on IBM Granite 4.1 8B running on AMD MI300X via vLLM.
Type any address or neighborhood. Within 6–13 seconds, five evidence
layers fan out across NYC's public flood record and return a four-
section prose briefing — every numeric claim followed by a [doc_id]
citation that resolves to a named primary source.

The system refuses to publish a number it cannot cite. Mellea rejection
sampling enforces four invariants on every response: numeric claims
grounded in source documents, no placeholder tokens, citation density
per sentence, and all cited doc_ids resolve to inputs. If the briefing
fails any check, the model rerolls. The meta card shows which checks
passed and how many attempts it took.

Three Apache-2.0 NYC-specialized fine-tunes were trained on AMD MI300X
and published on HF Hub: `msradam/Prithvi-EO-2.0-NYC-Pluvial` (pluvial
flood segmentation from Sentinel-2), `msradam/TerraMind-NYC-Adapters`
(LULC and building-stock adapters), and `msradam/Granite-TTM-r2-Battery-
Surge` (96-hour surge residual nowcast, test MAE 0.1091 m vs 0.1467 m
zero-shot). All training code and reproduction recipes are in the repo.

The data pipeline is entirely public-record: Hurricane Sandy 2012
inundation zone, NYC DEP stormwater scenarios, USGS Ida 2021 high-water
marks, FloodNet ultrasonic sensors, NYC 311 complaint history, NOAA
tide gauge, NWS METAR, NPCC4 SLR projections, five NYC policy PDFs in
a Granite Embedding 278M RAG corpus. No commercial APIs are contacted
at runtime.

Five addresses across four NYC boroughs, verified with the address probe
suite: 5 of 5 pass, 4/4 Mellea grounding checks, 5.8–13.1 seconds
wall-clock on AMD MI300X.

The stack runs on both AMD MI300X (vLLM) and local Ollama with
auto-failover. Apache-2.0 end-to-end.

---

## Cover image — design brief

**Target artifact:** `submission/cover-16x9.png`
**Dimensions:** 1920×1080 px or 1280×720 px, 16:9 ratio, PNG

**Visual system (must match deck cover exactly):**
- Background: `#F4F6F9` (--paper, cool slate register)
- Dam mark (Noun Project "Dam" by Chintuza, CC-BY 3.0): positioned
  top-left at approximately 72px from edges, colored `#005EA2`
  (federal blue, --accent)
- Wordmark: "Riprap" in IBM Plex Sans 700, `#0F172A` (--ink), large
  display size (~96–120px equivalent at 1920-wide)
- Tagline line 1: "Citation-grounded NYC flood-exposure briefings"
  IBM Plex Sans 400, `#334155` (--ink-2)
- Tagline line 2: "AMD MI300X &middot; Granite 4.1 &middot; Apache-2.0"
  IBM Plex Mono 500, `#64748B` (--ink-3), smaller (14–16px equivalent)
- Bottom strip (meta bar): thin rule at `#CBD5E1` (--rule-soft),
  below the rule: "AMD × lablab.ai Developer Hackathon · May 4–10 2026"
  in IBM Plex Mono, `#64748B`, 12px equivalent, uppercase

**What to avoid:**
- No bold color blocks in the background (the thumbnail reads fine
  on paper register)
- No gradient, shadow, or decorative water imagery — the dam mark
  carries the water metaphor
- No subtitle text beyond what's listed above

**Status:** The cover image requires an SVG/HTML renderer or design
tool. Automated generation is not feasible in this environment without
a headless browser for SVG-to-PNG export. Adam should generate this
from the brief above using:
  - Figma (design file already has the tokens)
  - The deck's cover slide exported at 1920×1080 via Marp
    (`--allow-local-files --image png --output cover-16x9.png`)
  - Or: `slides/logo.svg` + a simple HTML page exported via
    headless Chrome / Puppeteer

**Quickest path:** re-export the cover slide from deck.pdf as a PNG at
1920×1080. The cover slide already has the correct design.

---

## Recommended submission combination

**Title (go with A):** `Riprap — Cited NYC flood briefings on AMD`

**Short description (go with A):**
Riprap writes NYC flood-exposure briefings where every numeric claim cites its source — or doesn't appear. Granite 4.1 8B on AMD MI300X, three Apache-2.0 NYC fine-tunes, Mellea citation grounding. 5/5 addresses, 4/4 checks every run.

**Long description:** the version above (no changes needed).

**Runner-up title:** `Riprap: citation-grounded flood briefings`

**Runner-up short (option B):**
Three AMD MI300X fine-tuned models. Five evidence layers. One cited briefing. Riprap takes any NYC address, fans out across Sandy 2012 data, live FloodNet sensors, 311 history, and surge forecasts, then returns a 4-section paragraph with doc_id citations on every number.
