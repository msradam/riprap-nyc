# Load tests

Reproducible load-test scripts (k6) for the Riprap HTTP API. Three
scenarios cover the three classes of endpoint we care about:

| Script | What it tests | Key metric |
|---|---|---|
| `k6/baseline.js`           | Light read endpoints (`/api/pebbles`, `/api/backend`, `/`, `/api/layers/*`) | RPS ceiling + p95 latency |
| `k6/agent_concurrency.js`  | Heavy LLM-bound path (`/api/agent` JSON) ramping VUs 1 → 5 | `agent_wall_seconds` vs concurrent users |
| `k6/sse_streaming.js`      | SSE briefing stream — measures both time-to-first-evidence-card and time-to-final-briefing | `time_to_first_step_seconds`, `time_to_first_final_seconds` |

## Running

```bash
# 1. Install k6
brew install k6                  # macOS

# 2. Boot Riprap with Granian
RIPRAP_LLM_PRIMARY=ollama \
RIPRAP_USE_BURR_APP=1 \
RIPRAP_MELLEA_MAX_ATTEMPTS=4 \
.venv/bin/granian --interface asgi \
  --port 8765 --host 127.0.0.1 --workers 1 \
  web.main:app

# 3. Run the tests
k6 run load/k6/baseline.js
k6 run load/k6/agent_concurrency.js
k6 run load/k6/sse_streaming.js

# Override base URL for remote testing
k6 run -e BASE=https://your.host load/k6/baseline.js
```

## Where the curve bends

The expected bottleneck order is:

1. **LLM reconcile (Granite via Ollama)** — single-instance serialization. ~30 s
   per briefing, queues at 2+ concurrent users. This is the curve.
2. **uvicorn / Granian workers** — irrelevant under default `--workers 1`;
   bump to `--workers 4` for ~4× capacity on CPU-bound paths.
3. **External HTTP probes** — NOAA tides, NWS, FloodNet GraphQL have
   per-IP rate limits; expect 429s above ~10 concurrent.
4. **Filesystem reads** — `lru_cache` on geojson + per-thread rasterio
   handles. Cold-load is slow; warm is sub-ms.

## UX framing

The briefing prose is the slowest output (~30 s), but the user sees
**evidence cards stream in via SSE within 5-10 s** as each pebble
completes. So the perceived-latency budget is the
`time_to_first_step_seconds` metric, not `agent_wall_seconds`. Most
of the user value is delivered well before the Granite paragraph lands.

## Scaling moves (in increasing order of investment)

1. Granian `--workers 4` — free, ~4× throughput on light paths.
2. Remote vLLM endpoint (`RIPRAP_LLM_BASE_URL`) — vLLM batches concurrent
   reconciles, ~4-8× more briefings per minute on a single L4 GPU.
3. Briefing cache keyed on `(address, date)` — most repeat queries free.
   ~1 day of work.
4. Async pebble adapters — pebbles are mostly I/O bound, asyncio.gather()
   beats threadpool past 50 concurrent users. ~2-3 days of work.
5. Queue + worker pool (Redis + RQ / SQS + workers) — decouples HTTP
   ingest from inference. The right answer for thousands of users.
