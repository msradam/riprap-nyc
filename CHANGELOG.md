# Changelog

All notable changes to Riprap. The hackathon submission tag is
`v0.5.0` (build 2026-05-07); subsequent dates record polish work
that landed on the hackathon-period production deploys.

## [Unreleased] — 2026-05-09 (Saturday)

### Added
- **Per-query inference energy ledger** with real NVML readings off
  the L4 GPU. The status row on the Findings region now reports
  total Wh + total tokens for every briefing, with a leading icon
  (`✓` / `◐` / `~`) disclosing whether the number was measured or
  estimated. Full breakdown documented in
  [`docs/EMISSIONS.md`](docs/EMISSIONS.md).
- `inference-vllm/proxy.py`: 100 ms-cadence NVML sampler, response
  headers `X-GPU-Power-W` / `X-GPU-Energy-J` on every forwarded
  POST, and a `GET /v1/power` endpoint for bracket-sampling clients.
- `app/emissions.py` — new module with a thread-local `Tracker` that
  records every LLM and ML inference call (model, hardware, tokens,
  duration, joules) with a `measured: bool` flag per row.
- `scripts/probe_stones_fire.py` — programmatic CI that runs an
  address query against the lablab UI and asserts all five Stones
  fire, no `torchvision::nms` / `deps unavailable` dep regression,
  and the `emissions` block carries `nvidia_l4` hardware.
- `scripts/probe_benchmarks.py` — collects the canonical
  four-address verification set into `outputs/benchmarks.json`
  for the `docs/BENCHMARKS.md` page.
- `docs/EMISSIONS.md`, `docs/DEPLOY.md`, `docs/BENCHMARKS.md`,
  `CHANGELOG.md`, `CONTRIBUTING.md`.

### Changed
- The `RunHealthStrip` chip dropped the cloud-energy comparison
  (the sign convention was misleading and the comparison is now
  redundant given real measurements). New format:
  `<icon> X.X Wh / Y.YK tok inference`.
- `app/llm.py:_default_hardware_label` defaults to `"NVIDIA L4"`
  when remote vLLM is configured (was `"AMD MI300X"`, a stale
  string from the droplet days).
- `app/llm.py:chat()` now brackets every completion with two GETs
  to the inference Space's `/v1/power` endpoint; the average powers
  the LLM-call energy reading instead of the data-sheet estimate.
- `app/inference.py:_post()` reads NVML headers off the proxy
  response and forwards real joules into `emissions.record_ml`.

### Fixed
- `app/flood_layers/prithvi_live.py`: when the configured remote
  inference call fails (`RemoteUnreachable`), the specialist no
  longer falls through to the local terratorch path. The local
  path crashes with `RuntimeError: operator torchvision::nms does
  not exist` on the cpu-basic UI Space; surfacing a clean
  `remote prithvi-pluvial unreachable` skip is correct.
- `app/context/terramind_nyc.py:_try_remote()`: returns a
  `{"ok": False, "skipped": "remote terramind/<adapter>: ..."}`
  sentinel on remote failure, instead of `None` which was
  silently masked as `deps unavailable on this deployment`.
- `web/main.py`: explicit `/favicon.svg`, `/favicon.png`,
  `/favicon.ico`, `/robots.txt` routes — they were 404-ing under
  the SvelteKit SPA fallback because only `/_app` was mounted off
  the build directory.

### Documentation
- Full README rewrite reflecting the post-droplet L4 topology, the
  new emissions feature, and updated repo structure. Hackathon
  framing preserved.
- New `docs/DEPLOY.md` with the production topology, env-var
  reference, and per-Space deploy commands.
- New `docs/EMISSIONS.md` documenting what's measured vs. estimated,
  the NVML pipeline, and how to verify.

### Infrastructure note
- The DigitalOcean MI300X droplet was decommissioned 2026-05-06.
  All production inference now serves from `msradam/riprap-vllm`
  (NVIDIA L4). The MI300X runbook is preserved in
  [`docs/DROPLET-RUNBOOK.md`](docs/DROPLET-RUNBOOK.md) for anyone
  reproducing the AMD-judging setup; setting
  `RIPRAP_HARDWARE_LABEL=AMD MI300X` swaps the emissions profile
  back when redeploying to that hardware.

---

## [v0.5.0] — 2026-05-07

Hackathon submission tag.

### Added
- Five-Stone Burr FSM with Granite-native document-role messages
- Mellea four-check rejection sampling for the Capstone
- SvelteKit UI with SSE streaming, briefing prose, evidence-card
  grid, MapLibre overlay, citation drawer
- Three NYC-specialised foundation models published Apache-2.0:
  `msradam/TerraMind-NYC-Adapters` (LULC + Buildings + TiM LoRAs),
  `msradam/Prithvi-EO-2.0-NYC-Pluvial`,
  `msradam/Granite-TTM-r2-Battery-Surge`
- 30+ FSM specialists across hazard memory, asset registers, live
  observation, forecasting, and citation-grounded synthesis
