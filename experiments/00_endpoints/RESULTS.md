# Phase 0 — Endpoints smoke tests

8/8 endpoints reachable from local dev machine. Run with:

```bash
/Users/amsrahman/riprap-nyc/.venv/bin/python run_all.py
```

| Endpoint | Status | Latency | Notes |
|----------|:------:|--------:|-------|
| Microsoft PC STAC (Sentinel-2 L2A search) | PASS | 1.2 s | keyless; 3 items in S2 Brooklyn bbox |
| NYC Open Data Socrata (311, PLUTO, Sandy) | PASS | 5.8 s | each dataset returns its row keys |
| USGS NWIS (Bronx River at NYBG) | PASS | 0.3 s | 2 series, 190 obs/24h |
| NOAA Tides (Battery 8518750) | PASS | 0.1 s | latest WL=1.056 ft |
| NOAA NWPS (gauges in NY+PA bbox) | PASS | 4.1 s | 750 gauges; **needs `srid=EPSG_4326`** |
| NWS API (NY active alerts) | PASS | 0.5 s | 10 active alerts (cold day) |
| FEMA OpenFEMA (FimaNfipClaims, NY) | PASS | 0.1 s | 1-row probe; aggregated only per project policy |
| HF Hub (small Apache-2.0 model) | PASS | 0.3 s | sentence-transformers/all-MiniLM-L6-v2 metadata |

## Sharp edges discovered

1. **NWPS silently empty without `srid=EPSG_4326`.** Default `srid` is
   apparently a non-WGS84 system; bbox in geographic coords matches no
   gauges. Endpoint returns `200 OK` with an empty array — no error
   signal. Recorded in the smoke test comments so the next person
   doesn't lose 20 minutes.

2. **NYC Open Data Socrata is slow on cold connection.** ~6 s for three
   sequential single-row fetches. Probably PoP-routing or DNS warmup.
   Cache aggressively and batch.

3. **NWS API requires User-Agent.** The smoke test sets one; without a
   UA you'd get HTTP 403 (NWS docs say so but it's a quiet failure
   mode in production).

4. **OpenFEMA FimaNfipClaims schema is wide.** First-row keys include
   `amountPaidOnBuildingClaim`, `amountPaidOnContentsClaim`,
   `baseFloodElevation`, etc — these are the property-level fields we
   are NOT allowed to surface. Specialists using OpenFEMA must
   aggregate (e.g., `$select=count(*)&$filter=...&$apply=...`) before
   ingesting, never store property-level rows.

## Cache contents

`.cache/*.json` — one per smoke test, holds the parsed first row /
metadata so subsequent dev iterations don't re-hit the endpoint.

## Conclusion

All eight data sources are usable. Proceed to Phase 1 (Prithvi-EO
live water segmentation). No blocking issues.
