# Riprap rebrand brief — small, surgical

A brief for Claude Design (or any designer). The visual system holds;
only the positioning copy is misaligned with what the project has
become.

## What changed in the last 14 days

Riprap started as the AMD × lablab.ai hackathon submission: a single
NYC flood-briefing app, hardcoded for one city and one hazard.

It's now an **open civic-tech framework** with:

- **5 live deployments** sharing one codebase: NYC, Chicago, Seattle,
  San Francisco, Boston. Each is a directory of YAML.
- **3 hazards** validated: flood (NYC reference), heat (`deployments/heat/`),
  air (`deployments/air/`).
- **2 open-data platforms** covered: Socrata (most US Open Data portals)
  + CKAN (Boston, Philly, Toronto, EU portals). One adapter per platform,
  ~150 LOC each.
- **BYOD** (Bring Your Own Data): drop a YAML into `${CWD}/.riprap/`
  or set `RIPRAP_EXTRA_MANIFESTS=path` and your pebble layers onto any
  deployment without forking. Worked example uses real NYC FDNY data.
- **Two-tier reconciler:** Granite 4.1 8B + Mellea rejection sampling
  for the full LLM path; deterministic templated reconciler for the
  no-LLM offline path. Same compliance audit on both.

The framework claim is no longer rhetorical — it's backed by five
working artifacts in `deployments/` and a 7-test coverage suite for
BYOD.

## What's in scope for the rebrand

Six surfaces. Two paragraphs. Don't open the can of "full identity
refresh" — the visual system was hard-won and the palette + type +
mark + tier system are all load-bearing for the civic-tech
positioning. Touch only the positioning copy.

| # | Surface | Today | What it needs |
|---|---|---|---|
| 1 | Browser title (`app.html <title>`) | `Riprap — flood-exposure briefing` | Hazard-agnostic; mention the active deployment dynamically |
| 2 | Meta description (`app.html <meta description>`) | `Riprap — citation-grounded NYC flood-exposure briefings` | Reframe as framework |
| 3 | Hero H1 (landing) | `A flood exposure briefing for any place in New York City.` | Generalise to the active deployment; keep the "any place" + "citation-grounded" voice |
| 4 | Hero deck (landing) | `Type an address. Get a written briefing where every numeric claim links to its primary public-record source.` | Holds up. Maybe lengthen by one sentence to acknowledge framework. |
| 5 | Header context chip | `Flood Exposure Briefing · NYC` | Pulls from the active deployment's `stones.yaml` |
| 6 | README banner / `## Flood risk analysis for any NYC address.` | NYC-specific | Reframe as framework; surface the five deployments + BYOD prominently |

## What's NOT in scope

- The dam mark logo (it's literal riprap — keep)
- The Civic Hydrology palette
- IBM Plex everywhere
- The Five Stones taxonomy + their taglines (cornerstone / keystone /
  touchstone / lodestone / capstone — these are *system-level* names
  and apply to any hazard or city)
- The tier glyphs (EMP / MOD / PRX / SYN)
- Card layouts + evidence-card grammar
- Print stylesheet behavior
- The `/q/<address>` URL pattern

## Candidate copy directions

Three voice options. Pick one, mix, or counter-propose:

### Option A — Civic-engineering register (preserves current voice)

> **Riprap**
> Composable, citation-grounded climate briefings for any place.
>
> *Open framework. Five cities live. Drop in your own data.*

- H1: `A climate-exposure briefing for any place.`
- Deck: `Type an address. Get a written briefing where every numeric
        claim links to its primary public-record source. Same code,
        any city: NYC, Chicago, Seattle, San Francisco, Boston.`
- Header chip: `Climate-Exposure Briefing · {deployment_name}` —
  pulls from `stones.yaml` so e.g. `· Boston` swaps in automatically.

### Option B — Framework-first register (leans into OSS framework)

> **Riprap**
> Manifests in. Briefings out.
>
> *An open civic-tech framework for grounded climate intelligence.*

- H1: `Open framework for grounded climate briefings.`
- Deck: `One codebase, five working cities (NYC, Chicago, Seattle,
        San Francisco, Boston). Drop your data in via .riprap/ — no
        fork. Every claim cites a primary public-record source.`
- Header chip: `Riprap · {city} · {hazard}` — fully dynamic.

### Option C — Stay tight to the metaphor

> **Riprap**
> Small stones, stacked carefully, hold the shoreline.
>
> *A civic framework that composes public-record evidence into
> citation-grounded climate briefings, one pebble at a time.*

- H1: `Citation-grounded briefings for any place.`
- Deck: `Riprap stacks small pieces — sensor readings, agency reports,
        FEMA panels, NOAA gauges — into a single grounded briefing for
        any address. Five cities run on it today. Yours could be next.`
- Header chip: `{deployment.tagline} · {deployment.city}` —
  e.g. `Flood-Exposure Briefing · Boston` or `Heat-Exposure Briefing · NYC`.

My instinct: **A is the safest** — it preserves the federal-civic
voice the palette and type already commit to. **C is the most
distinctive** but risks reading as poetic. **B is the most
honest** about what changed but loses the "for any place" hook
that hooks a first-time visitor.

## Dynamic deployment copy — implementation note

For surfaces 1, 3, 5: pull the active deployment's `stones.yaml`
description and city name. The browser title and header chip should
read differently depending on `RIPRAP_DEPLOYMENT`:

| `RIPRAP_DEPLOYMENT` | Header chip | Browser title |
|---|---|---|
| `deployments/nyc` | `Flood-Exposure Briefing · NYC` | `Riprap NYC — flood briefing for 189 Atlantic Ave` |
| `deployments/boston` | `Flood-Exposure Briefing · Boston` | `Riprap Boston — flood briefing for City Hall Square` |
| `deployments/heat` | `Heat-Exposure Briefing · NYC` | `Riprap NYC — heat briefing for ...` |

Backend already serves `/api/pebbles` which includes the five `stones`.
Add the deployment's `city` + `hazard` to that payload (or to a new
`/api/deployment` endpoint) and the SvelteKit shell can wire it.

## Open questions for the designer

1. **Should the wordmark add a small "framework" qualifier?**
   E.g. `riprap // framework` in mono, similar to how Sentry,
   Linear, Fastly use thin secondary marks. Or stay clean.
2. **Is `Climate-Exposure Briefing` the right cross-hazard parent
   term?** Alternatives: `Hazard-Exposure Briefing`, `Public-Record
   Briefing`, `Civic Briefing`. I lean Climate because heat/air/flood
   all roll up there, but a designer/writer may have a better word.
3. **How prominent should "open source" be in the hero?** Civic-tech
   audiences trust open more than they trust polished marketing.
   But too much OSS-signaling reads as "this is a side project, not
   a tool I'd actually use." The README banner can be loud; the
   hero should probably be quieter.
4. **Should the landing surface a city picker?** Today
   `/q/<address>` is the only entry; you have to know an address to
   start. A `Try a city: [NYC] [Chicago] [Seattle] [SF] [Boston]`
   row above the address input would showcase the five-deployment
   claim without requiring text input.

## Scope estimate (for self / Claude Design)

- Update copy in `app.html`, `src/lib/components/shell/AppHeader.svelte`,
  `LandHeader.svelte`, `src/routes/+layout.svelte`, the hero
  components, README banner, CONTRIBUTING opener: ~30 lines of
  text edits across ~8 files.
- Backend: extend `/api/pebbles` to include `deployment.city` +
  `deployment.hazard` (~5 LOC).
- Optional: city picker on landing (~40 LOC svelte component).

Half a working day if A is chosen. Less if no city picker.

## Out-of-scope follow-ups (different brief, different session)

- Domain decision (riprap.dev? riprap-civic.org?).
- README hero image — currently `assets/screenshots/hero.png` is
  Brooklyn DUMBO. Should be a multi-city carousel or stay NYC for
  visual continuity?
- Repo name `riprap-nyc`. The GitHub URL is `msradam/riprap-nyc`.
  Rename to `riprap`? Keep as `riprap-nyc` since it's a known URL?
  Add a `riprap` GitHub org and move? — all org-level decisions.
- HF Spaces account. `msradam/riprap` Space could land as the
  framework demo; existing `lablab-ai-amd-developer-hackathon-riprap-nyc`
  stays as the NYC reference.

---

**Action requested:** pick one of A / B / C (or counter-propose), and
say yes/no to the dynamic-deployment header chip + the optional city
picker. From there it's text edits.
