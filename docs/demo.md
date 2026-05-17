# Riprap MVP demo — flood, heat, air

The "open-source climate briefing tool" MVP, in three deployments. Same
code, same Burr graph, same compliance predicates, same web UI. Three
hazards, three `deployments/` directories, zero core-code differences.

## What the demo shows

1. **Flood briefing** at an NYC address — the production deployment.
   22 pebbles across Cornerstone / Touchstone / Lodestone / Keystone,
   13/13 compliance, LLM tier or templated tier.
2. **Heat briefing** at the same address — `deployments/heat/`.
   NYC HVI + NYC Forestry + NWS observations + NWS alerts. Same UI,
   different stones-yaml taglines drive different section headings.
3. **Air-quality briefing** at the same address — `deployments/air/`.
   NWS air alerts + (optional) EPA AirNow. Same UI again.

Each is a real run end-to-end. Each passes 13/13 briefing-standards
compliance predicates sourced from FEMA, IPCC AR6, TCFD, ASTM E1527-21,
EPA/CDC CERC, AP Stylebook, SPJ Code of Ethics.

## Setup

```bash
# Bring up Granian
RIPRAP_LLM_PRIMARY=ollama \
RIPRAP_OLLAMA_8B_TAG=granite4.1:8b-q3_K_M \
RIPRAP_MELLEA_MAX_ATTEMPTS=4 \
RIPRAP_NYCHA_REGISTERS=1 \
  .venv/bin/granian --interface asgi \
    --port 8765 --host 127.0.0.1 --workers 1 \
    web.main:app
```

Open `http://127.0.0.1:8765/`.

## The demo flow

### 1. Flood — the production briefing

Default deployment (`deployments/nyc`). Open in browser:

```
http://127.0.0.1:8765/q/189%20Atlantic%20Ave%2C%20Brooklyn
```

Or via API:

```bash
curl "http://127.0.0.1:8765/api/agent?q=189%20Atlantic%20Ave%2C%20Brooklyn" \
  | jq '{intent, compliance, paragraph_chars: (.paragraph | length)}'
```

What lands: 22 pebbles fire, four-section briefing (Status / Empirical
evidence / Modeled scenarios / Live signals), 13/13 compliance.

### 2. No-LLM mode — same briefing, no Granite calls

Restart with the templated tier:

```bash
RIPRAP_RECONCILER_TIER=no_llm \
RIPRAP_BRIEFING_SCOPE=flood-exposure \
.venv/bin/granian --interface asgi --port 8765 --host 127.0.0.1 web.main:app
```

```bash
curl "http://127.0.0.1:8765/api/agent?q=189%20Atlantic%20Ave%2C%20Brooklyn" \
  | jq '{compliance, paragraph}'
```

Same compliance score (13/13). Briefing is templated prose
synthesized from each pebble's `narration.template` — no Granite,
no Mellea. Specialist ML (Prithvi, TerraMind, TTM, GLiNER, RAG
embeddings) still runs.

### 3. Heat deployment — same code, different YAML directory

Restart pointing at the heat manifests:

```bash
RIPRAP_DEPLOYMENT=deployments/heat \
RIPRAP_BRIEFING_SCOPE=heat-exposure \
RIPRAP_RECONCILER_TIER=no_llm \
RIPRAP_HEAVY_SPECIALISTS_ENABLED=0 \
.venv/bin/granian --interface asgi --port 8765 --host 127.0.0.1 web.main:app
```

```bash
curl "http://127.0.0.1:8765/api/agent?q=189%20Atlantic%20Ave%2C%20Brooklyn" \
  | jq '{compliance, paragraph}'
```

What lands:

```
This is an automated heat-exposure briefing produced by Riprap from live
and baked data sources. It is informational only and not a substitute
for a professional risk assessment.

**Heat Hazard Reader.**
NYC DOHMH Heat Vulnerability Index for the surrounding NTA, current
methodology [nyc_hvi]. NYC Forestry recorded 0 street tree(s) within
200 m of this address in the 2015 census [tree_canopy].

**Live Observer.**
Most recent NWS hourly observation at the nearest METAR station —
temperature, humidity, and dewpoint [nws_obs].

**Projector.**
Currently active NWS alerts intersecting this address — heat
advisories, excessive heat warnings, and related public-health alerts
[nws_alerts].

**Out of scope.** This briefing does not assess title, structural
condition, or compliance with specific zoning rules. Where a probe
was offline at run time, the relevant section omits that signal.
```

13/13 compliance. Section headings (`Heat Hazard Reader`, `Live Observer`,
`Projector`) auto-derived from `deployments/heat/stones.yaml`.

### 4. Air-quality deployment — third hazard, same architecture

```bash
RIPRAP_DEPLOYMENT=deployments/air \
RIPRAP_BRIEFING_SCOPE=air-quality \
RIPRAP_RECONCILER_TIER=no_llm \
.venv/bin/granian --interface asgi --port 8765 --host 127.0.0.1 web.main:app
```

```bash
curl "http://127.0.0.1:8765/api/agent?q=189%20Atlantic%20Ave%2C%20Brooklyn" \
  | jq '{compliance, paragraph}'
```

What lands:

```
This is an automated air-quality briefing produced by Riprap from live
and baked data sources. It is informational only and not a substitute
for a professional risk assessment.

**Live Observer.**
Currently active NWS alerts intersecting this address — air-quality,
smoke, and particulate advisories [nws_alerts].

**Out of scope.** ...
```

The air deployment is currently thinner (just `nws_alerts` working out
of the box). With an EPA AirNow API key set in `RIPRAP_AIRNOW_API_KEY`,
the `epa_airnow` pebble adds live AQI / PM2.5 / ozone for the address's
25-mile radius. Free key from [AirNow](https://docs.airnowapi.org/).

## What the demo proves

- **Architecture is hazard-agnostic.** Three deployments produce three
  briefings from one codebase. Adding a new hazard = a new
  `deployments/<hazard>/` directory.
- **Briefings are professional-grade.** All three pass 13 predicates
  sourced from FEMA / IPCC / TCFD / ASTM / EPA / AP / SPJ. The
  compliance audit ships in every response.
- **Two reconciler tiers ship side by side.** `llm` runs Granite +
  Mellea grounded rejection sampling; `no_llm` runs templated synthesis
  with no Granite calls — same compliance bar, same UI, sub-second
  prose, civic-tech audit clean.
- **Specialist ML stays on a clean lineage.** Granite (IBM, ISO/IEC
  42001:2023), Prithvi-EO 2.0 (NASA/IBM, public-domain HLS), TerraMind
  (IBM/ESA, public Copernicus), TTM r2 (IBM, NOAA), Flair NER
  (OntoNotes 5.0, human-labeled LDC), sentence-transformers (UKP-Lab,
  MS MARCO + NQ). No model in the stack was trained on closed-LLM
  synthetic data.
- **BYOD works.** Anyone can drop a new pebble YAML pointing at a REST
  API, CSV, or GeoJSON (local or URL) and add it to any deployment.

## Demo cheat-sheet — switching deployments

```
# Flood (the production reference)
RIPRAP_DEPLOYMENT=deployments/nyc

# Heat
RIPRAP_DEPLOYMENT=deployments/heat
RIPRAP_BRIEFING_SCOPE=heat-exposure

# Air quality
RIPRAP_DEPLOYMENT=deployments/air
RIPRAP_BRIEFING_SCOPE=air-quality
```

Restart Granian after any change.

## Known gaps in the MVP (worth saying out loud)

- **`nyc_hvi` pebble** in the heat deployment uses the canonical NYC
  Open Data HVI dataset but HVI is keyed by ZCTA, not point — the
  spatial join hasn't been built yet, so the pebble fires with zero
  features and falls back to the generic narration. Followup:
  ZCTA-boundary join adapter.
- **NYC Community Air Survey** (NYCCAS) is a raster dataset; raster
  adapter isn't built yet. Followup: `baked_raster` adapter.
- **Wildfire and wind** are tier-1 hazards per the research scoping
  doc; not in the MVP three. Followup: `deployments/wildfire/` and
  `deployments/wind/`.
- **Equity overlay** (CDC SVI + EPA EJScreen) is the unique OSS
  differentiator vs commercial closed-source tools. Not in MVP three.
  Followup: cross-cutting layer that runs alongside the active hazard
  deployment.
- **`/api/agent/stream` SSE path** still routes through the legacy
  `app.fsm` for non-flood deployments (the Burr `iter_steps_from_plan`
  is wired only for single_address intent). Smoke test is via the JSON
  `/api/agent` endpoint, which goes through the Burr app.

None of these are blockers for "demonstrate the three-hazard MVP."
They're the obvious next moves.
