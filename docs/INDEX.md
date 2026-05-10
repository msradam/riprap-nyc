# Docs index

One-line map of everything under `docs/`. Read in this order if
you're new; jump directly if you know what you need.

| Doc | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full system shape: Burr FSM, Five-Stone taxonomy, Granite + Mellea synthesis path, SvelteKit + FastAPI surface. Start here. |
| [METHODOLOGY.md](METHODOLOGY.md) | How each Stone scores exposure — joins, thresholds, citation provenance, edge-case handling. |
| [DEPLOY.md](DEPLOY.md) | Five-piece deployment topology (lablab UI Space, L4 vLLM Space, Ollama fallback, droplet, local). Routing matrix and env vars. |
| [DROPLET-RUNBOOK.md](DROPLET-RUNBOOK.md) | Single-command MI300X bring-up on DigitalOcean — bake, snapshot, redeploy. |
| [EMISSIONS.md](EMISSIONS.md) | Per-query NVML energy ledger — proxy sampler, response-header contract, `app/emissions.py` tracker, measured-vs-estimated semantics. |
| [BENCHMARKS.md](BENCHMARKS.md) | Live measurements on the canonical four addresses: Stone-fire counts, latency, energy, token totals. |
| [RESEARCH.md](RESEARCH.md) | Landscape research — what existing flood-risk tools do and how Riprap diverges. |

Top-level docs that complement these:

- [`README.md`](../README.md) — project overview, quickstart, Five Stones, fine-tunes, citations.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — dev setup, probe scripts, PR flow.
- [`CHANGELOG.md`](../CHANGELOG.md) — version history (`v0.5.0` = hackathon submission).
- [`SECURITY.md`](../SECURITY.md) — vulnerability disclosure.
- [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) — Contributor Covenant 2.1.
