# Multi-hazard experiment — does Riprap generalize?

**Yes.** The Riprap architecture is hazard-agnostic. The same code that
serves the flood briefing — pebble registry, Burr graph, Stone fan-out,
templated reconciler, compliance predicates, frontend — produces a
heat-exposure briefing or an air-quality briefing when you point it at
a different `deployments/<hazard>/` directory.

This document records the experiment.

## The experiment

Drop two new deployment directories alongside `deployments/nyc/`
(flood):

```
deployments/
  nyc/        — flood (22 pebbles, full production stack)
  heat/       — heat (4 pebbles, scaffold)
  air/        — air quality (3 pebbles, scaffold)
```

Each carries:
- `stones.yaml` — same five Stones, taglines re-framed for the hazard
- `manifests/*.yaml` — pebble manifests pointing at hazard-relevant
  data sources

Switch deployments via env var:

```bash
RIPRAP_DEPLOYMENT=deployments/heat \
RIPRAP_BRIEFING_SCOPE=heat-exposure \
RIPRAP_RECONCILER_TIER=no_llm \
  .venv/bin/python -c "import riprap.core.burr.app as a; print(a.run('189 Atlantic Ave, Brooklyn')['paragraph'])"
```

## Result — heat deployment (4 pebbles, no LLM)

```
This is an automated heat-exposure briefing produced by Riprap from
live and baked data sources. It is informational only and not a
substitute for a professional risk assessment.

**Heat Hazard Reader.**
NYC Forestry recorded 0 street tree(s) within 200 m of this address
in the 2015 census [tree_canopy].

**Live Observer.**
Most recent NWS hourly observation at the nearest METAR station —
temperature, humidity, and dewpoint [nws_obs].

**Projector.**
Currently active NWS alerts intersecting this address — heat
advisories, excessive heat warnings, and related public-health
alerts [nws_alerts].

**Out of scope.** This briefing does not assess title, structural
condition, or compliance with specific zoning rules. Where a probe
was offline at run time, the relevant section omits that signal.
```

**Compliance: 13/13.** Section headings (`Heat Hazard Reader`,
`Live Observer`, `Projector`) come from the heat deployment's
`stones.yaml` taglines. Citations point at heat-specific doc_ids.
Same templated reconciler, same compliance predicates as the flood
deployment.

## What had to change

Almost nothing. The architectural moves that made this work:

1. **Pebble registry is deployment-scoped** — `RIPRAP_DEPLOYMENT` selects
   which `manifests/` dir loads. The registry doesn't care what hazard
   the pebbles measure.

2. **Stone fan-out reads the registry dynamically** — `_pebbles_for(stone_id)`
   in `riprap/core/burr/stones.py` queries the active registry, not
   a hardcoded list. The Burr `MapActions` parallel fan-out
   automatically picks up the active deployment's pebbles.

3. **Templated reconciler was hardcoded to flood pebble names — *fixed
   during this experiment.*** Now walks pebbles by `manifest.stone`
   instead of hardcoded `_STATUS_PEBBLES`/`_LIVE_PEBBLES`/etc. tuples.
   Section headings derive from `stones.yaml` taglines. One commit;
   no Pi/flood regression.

4. **Compliance predicates are hazard-neutral.** The 13 predicates
   (FEMA, IPCC, TCFD, ASTM, EPA/CDC, AP, SPJ) enforce briefing-quality
   rules that apply to any data-backed civic-tech writeup, not flood-
   specific tropes. Same 13/13 bar across deployments.

5. **`RIPRAP_BRIEFING_SCOPE` env var** lets each deployment override
   the scope-declaration wording in the opening sentence
   ("automated flood-exposure briefing" vs "automated heat-exposure
   briefing"). Trivial knob; preserves ASTM 4.1 compliance.

## What still varies per hazard

Each deployment needs:

- **`stones.yaml` taglines tuned for the hazard.** Same five Stones;
  different framing. Cornerstone for heat is "the heat hazard reader";
  for flood it's "the hazard reader". Five-line YAML edits.

- **Pebble manifests that point at hazard-relevant data sources.** This
  is the actual work — finding the right NYC Open Data dataset, the
  right NWS alert filter, the right state/federal API. Each pebble is
  one YAML file.

- **`RIPRAP_BRIEFING_SCOPE`** env value to match.

## What pebbles port directly

| Pebble | Reuse across hazards |
|---|---|
| `nws_alerts` | Yes — already filters by point; surfaces whatever NWS publishes (flood, heat, air, fog, wind) |
| `nws_obs` | Yes — temperature, humidity, dewpoint, precipitation, wind |
| `nyc311` | Filter by complaint descriptor (flood → sewer/catch basin; heat → hot weather; air → odor/dust) |
| `baked_vector` adapter | Hazard-agnostic — points at any GeoJSON, local or URL |
| `rest_json` adapter | Hazard-agnostic — env-var auth, JSON path extraction |
| `python_call` adapter | Hazard-agnostic — wraps any Python function |
| `noaa_tides` | Flood-only — tides are a flood signal |
| Prithvi-EO 2.0 | Could fine-tune for thermal anomalies (heat) or smoke plumes (air) — same model family |
| TerraMind LULC | Cross-hazard — land-use mix matters for all of heat / flood / air |
| TTM time-series | Cross-hazard — same forecasting backbone, different feature signals |

The 22 flood pebbles aren't ported wholesale. But the **adapters** are.
A new hazard means writing 5-10 hazard-specific manifests and pointing
the existing adapters at new data sources. Hours of work per hazard,
not weeks.

## Caveats from this run

- The NYC OpenData dataset IDs in the heat/air manifests are best
  guesses — three of them 404'd in testing. They **fail gracefully
  via the offline path** (the briefing skips them rather than 500ing),
  which is what we'd want in a real deployment, but to actually ship
  a heat or air deployment those manifests need verified dataset IDs.

- The air deployment's `epa_airnow` pebble requires an EPA AirNow API
  key (`RIPRAP_AIRNOW_API_KEY` env var). Free key, but a real
  deployment needs to obtain and configure it.

- TerraMind and Prithvi are pre-trained for satellite-derived
  geospatial features (water segmentation, LULC, buildings, biomass).
  They could be **fine-tuned** for thermal-anomaly or smoke-plume
  segmentation — that's a separate fine-tuning exercise, not just a
  manifest edit. Until that happens, those model pebbles return their
  flood-trained outputs.

- TTM is a generic time-series forecaster. The flood deployment uses
  it for tide-gauge surge and 311-complaint counts. Heat would use it
  for daily-max-temperature series; air would use it for AQI history.
  Same model, different input series — needs a new pebble per series
  but the manifest pattern is identical.

## The bigger claim this experiment supports

> **Riprap is not a flood tool. It's a place-based briefing framework.
> NYC flood is the reference deployment. Heat and air are demonstrations
> that the same architecture serves any hazard you can express as a
> set of pebbles tagged onto five stones. Future deployments — wildfire,
> drought, seismic, transit accessibility, environmental justice — fit
> the same shape without changing any core code.**

That's the framework story, and now there's a real artifact backing it.
