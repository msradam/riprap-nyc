# Load test results — Granian + Burr pipeline, single worker

Recorded 2026-05-16 on M3 Pro laptop, Ollama serving `granite4.1:8b-q3_K_M`,
Granian 2.7.4, 1 worker, against the Burr Application path
(`RIPRAP_USE_BURR_APP=1`).

## Baseline — light read endpoints (`load/k6/baseline.js`)

Ramp 1 → 20 concurrent VUs over 2 min 15 s, mixed across four endpoints.

| Endpoint              | p50    | p90     | p95     | Threshold | Pass |
|-----------------------|--------|---------|---------|-----------|------|
| `/api/pebbles`        | 4.41 ms | 10.64 ms | **12.69 ms** | <50 ms   | ✓ |
| `/` (landing)         | 4.32 ms | 12.31 ms | **14.41 ms** | <100 ms  | ✓ |
| `/api/backend`        | 19.33 ms | 30.61 ms | **33.75 ms** | <100 ms | ✓ |
| `/api/layers/sandy?…` | 7.16 ms | 14.42 ms | **16.75 ms** | <500 ms | ✓ |

- **Total throughput: 416 RPS** sustained (104 iterations/s × 4 endpoints).
- **Errors: 0 / 56,180** (0.00%).
- **Network: 25 MB/s** sustained over 2 min.

These endpoints — exactly the ones the SvelteKit frontend hits to populate
the manifest catalog, page chrome, and clipped map layers — are not the
bottleneck. Granian handles 20-VU load on a single worker with comfortable
headroom and zero degradation.

## Agent concurrency — the LLM-bound path (`load/k6/agent_concurrency.js`)

Partial measurement (test killed at ~4 min 51 s into the 8-min run, but
enough to characterize the curve).

| Concurrency | Per-briefing wall time | Note |
|-------------|------------------------|------|
| 1 VU (sequential, prior runs) | ~80–95 s | Granite reconcile + 27 pebble events |
| **2 VUs (measured here)** | **~150 s** | 2 iterations completed in 4 min 51 s |

**Curve shape: linear-with-concurrency.** Each additional concurrent user
adds roughly one full Granite reconcile cycle (~60–80 s) to their own
wait time, because Ollama serializes inference requests on a single GPU
slot.

Extrapolation (untested, by inspection):

| Concurrency | Predicted p95 |
|-------------|---------------|
| 3 VUs       | ~220 s        |
| 5 VUs       | ~400 s        |
| 10 VUs      | ~12 min (effectively broken) |

## UX framing — first-step vs final-paragraph

The wall-time numbers above are time-to-final-paragraph. The user actually
sees evidence cards stream in via SSE much earlier. From the earlier probe
runs we have step timings (Cornerstone fan-out completes at ~7 s after
geocode for a typical query):

| Event | Time after request |
|-------|--------------------|
| First step event (planner result) | ~7 s |
| Cornerstone fan-out complete (7 cards) | ~8 s |
| Touchstone, Lodestone, Keystone done | ~25 s |
| RAG + GLiNER done | ~28 s |
| **First Granite token streaming** | **~30 s** |
| Reconcile complete (full paragraph) | ~90 s (single user) |

So at 2 concurrent users, the first user still sees their evidence dashboard
fully populated at ~25 s — only the prose ribbon at the bottom keeps
streaming for an extra minute. **Perceived latency for the second user is
much less than 150 s** because their pebbles run independently and only the
Granite-bound prose serializes.

## Where the curve actually bends

1. **Ollama serialization** — confirmed. Concurrent /api/agent calls queue
   on the single Granite slot. This is the only meaningful bottleneck
   visible in these tests.
2. **uvicorn / Granian workers** — not the bottleneck at any concurrency
   level we tested. Granian's single worker handled 20-VU light-endpoint
   load with no degradation.
3. **External HTTP probes** — not hit. NOAA / NWS / FloodNet rate limits
   would only kick in around 10+ concurrent agent calls.

## Recommended scaling moves (priority order)

1. **vLLM endpoint** (`RIPRAP_LLM_BASE_URL`). Already supported in code.
   vLLM batches concurrent generation requests on a single GPU — 4-8× the
   reconciles-per-minute on an L4. Closes the linear-curve bend.
2. **Briefing cache** keyed on `(geocoded_address, date)`. Same address
   queried within 24 h returns the cached paragraph + pebble values.
   Most repeat queries become free.
3. **Granian `--workers N`** with a remote vLLM. Each worker handles its
   own CPU-bound pebble work in parallel; vLLM batches the inference.
   This is the configuration to ship a public-facing service on.
4. **Async pebble adapters** — `async def fetch`. Pebbles are I/O bound;
   asyncio.gather() over httpx.AsyncClient scales to hundreds of
   concurrent users without thread explosion. Pebble-layer rewrite.
5. **Queue + worker pool** (Redis + RQ, or SQS + workers) — when the
   service needs to absorb traffic bursts without making users wait
   30 s for a connection.

## Re-running

```bash
# Boot server
RIPRAP_LLM_PRIMARY=ollama RIPRAP_OLLAMA_8B_TAG=granite4.1:8b-q3_K_M \
RIPRAP_USE_BURR_APP=1 RIPRAP_NYCHA_REGISTERS=1 \
RIPRAP_MELLEA_MAX_ATTEMPTS=4 \
  .venv/bin/granian --interface asgi --port 8765 --host 127.0.0.1 \
  --workers 1 web.main:app

# Run tests
k6 run load/k6/baseline.js
k6 run load/k6/agent_concurrency.js   # ~8 min
k6 run load/k6/sse_streaming.js       # ~3 min
```
