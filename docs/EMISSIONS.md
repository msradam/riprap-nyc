# Per-query inference energy ledger

Riprap surfaces the energy and token cost of every inference call it
makes during a briefing. The numbers are **measured off the L4 GPU**
when the inference Space is reachable — not data-sheet estimates.

```
5 Stones · 21 fired · 11 evidence cards · 14.0s wall-clock · ✓ 1.4 Wh / 6.9K tok inference
```

The chip on the Findings status row reports total energy (Wh) plus
total tokens. The leading icon discloses how the number was derived:

| Icon | Meaning |
|---|---|
| `✓` | All recorded calls came back with a real NVML reading from the L4 GPU |
| `◐` | Some calls measured, others fell back to the data-sheet estimate |
| `~` | All calls used the data-sheet estimate (proxy unreachable, NVML disabled, or local-only run) |

Hover the chip for the full breakdown — call count, hardware, prompt
vs completion split, and the method.

---

## What's measured vs. what's estimated

| Field | Source |
|---|---|
| `duration_s` | Real wallclock on the client side (`time.monotonic` around each call) |
| `prompt_tokens`, `completion_tokens` | Reported by the model server (LiteLLM `usage` block) for non-stream LLM calls |
| `completion_tokens` (streaming) | Estimated as `len(response_text) / 4` when the backend doesn't surface a final usage block (Ollama path) |
| `power_w` | **Measured** — `nvmlDeviceGetPowerUsage` on the L4 inference Space, sampled every 100 ms, mean of samples bracketing each call |
| `wh`, `joules` | `power_w × duration_s` (when `measured: true`) or `data-sheet_W × duration_s` (when `measured: false`) |

Each call record on the ledger carries a `measured: bool` flag plus
the exact `power_w` value used so a reviewer can audit any row.

---

## How the measurement works

The L4 inference Space (`msradam/riprap-vllm`) runs a FastAPI proxy
in front of vLLM (port 8000) and the riprap-models EO service
(port 7861). The proxy initialises NVML at startup and runs a
background sampler that reads `nvmlDeviceGetPowerUsage` every
100 ms into a 60-second ring buffer.

```
inference-vllm/proxy.py::_power_sampler
  ├── NVML init at startup, single L4 device handle
  ├── 100 ms ring buffer (600 samples = 60 s of history)
  └── degrades to no-op if NVML init fails
```

When the proxy forwards a POST to vLLM or riprap-models, it stamps
the upstream call window `(t0, t1)` and computes the mean power
across the samples that fall inside that window. The result lands
on the response as headers:

```
X-GPU-Power-W      mean draw in watts
X-GPU-Energy-J     energy in joules over the window
X-GPU-Duration-S   forwarded-call duration in seconds
X-GPU-Device       "NVIDIA L4"
```

`app/inference.py::_post()` reads those headers off the proxy
response and forwards them into `emissions.Tracker.record_ml`. The
tracker stamps `measured=True` and uses the exact joule value.

For the LLM client path (`app/llm.py::chat()`) we route through
LiteLLM, which doesn't surface response headers. So instead the
client brackets the call with two GETs to `/v1/power`:

```python
p0 = _sample_gpu_power_w()                # ~50 ms, returns 1 s avg
t0 = time.monotonic()
resp = _router.completion(...)            # the actual LLM call
duration_s = time.monotonic() - t0
p1 = _sample_gpu_power_w()                # ~50 ms, returns 1 s avg
avg = (p0 + p1) / 2
```

`avg` is the average power during the call; `avg × duration_s`
gives joules. The tracker records `power_w_real=avg`,
`joules_real=avg×duration_s`, and `measured=True`.

---

## Hardware profiles (`app/emissions.HARDWARE`)

The fallback path uses a sustained-power figure from the hardware
data sheet when no real measurement is available:

| Key | Label | Sustained W | Source |
|---|---|---|---|
| `nvidia_l4` | NVIDIA L4 | 60 | L4 data sheet (72 W TGP, Ada Lovelace) |
| `amd_mi300x` | AMD MI300X | 600 | MI300X data sheet (750 W TDP); used when `RIPRAP_HARDWARE_LABEL=AMD MI300X` |
| `nvidia_t4` | NVIDIA T4 | 50 | T4 data sheet (70 W max) |
| `apple_m` | Apple M-series | 20 | ml.energy / community measurements |
| `cpu_server` | x86 CPU | 30 | Typical sustained server-core load |

The fallback only fires when the proxy is unreachable, NVML init
failed, or the call streamed (we currently don't measure streamed
LLM calls precisely; they bracket-sample as best-effort).

---

## End-to-end shape

```
Lablab UI Space (cpu-basic, FastAPI + SvelteKit)
   │
   │  Tracker installed per-query in web/main.py:
   │  install(Tracker())
   │
   ├── planner       — app/llm.py::chat
   │                   ├─ GET /v1/power  (bracket-start)
   │                   ├─ POST /v1/chat/completions
   │                   └─ GET /v1/power  (bracket-end)
   │
   ├── FSM specialists — app/inference.py::_post
   │                     POST /v1/{prithvi-pluvial, terramind, ...}
   │                     ← X-GPU-Power-W, X-GPU-Energy-J headers
   │
   └── reconciler    — app/llm.py::chat (Mellea-validated)
                       same bracket pattern as planner
                  │
                  ▼
       Tracker.summarize() → emissions block on /api/agent/stream final
                  │
                  ▼
       SvelteKit RunHealthStrip — chip rendered with measured-icon
```

---

## Verifying

`scripts/probe_stones_fire.py` runs an end-to-end address query
against the lablab UI and asserts:

1. All five Stones fire
2. No specialist returns the legacy dep-regression strings
   (`torchvision::nms`, `deps unavailable on this deployment:
   terratorch`)
3. The final `emissions` block carries `nvidia_l4` hardware and
   non-zero tokens

```bash
PYTHONPATH=. uv run python scripts/probe_stones_fire.py --timeout 600
```

The first call after a Space restart pays a ~120 s vLLM CUDA-graph
compile penalty; warm queries land at < 0.5 Wh / ~7 K tokens.

---

## Why this matters

Inference cost is usually invisible. AI tools that publish a
"green" or "low-energy" claim mostly cite a vendor data sheet or a
research mean. Riprap reports the actual joules drawn off the
device under the load of a single user query — auditable down to
the row.

The raw ledger is shipped on the SSE `final` event under
`emissions.calls`, so any consumer (dashboard, billing model,
reproducibility check) can reuse the data without round-tripping
back through Riprap.
