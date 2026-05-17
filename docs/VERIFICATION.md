# Verification — 2026-05-16

Snapshot of what's been verified deterministically against the
`pebble-refactor` branch.

## Sweep (5 cities × real APIs, no-LLM tier)

```
DEPLOYMENT          ADDRESS                                           COMPLIANCE  CITY PEBBLE       WALL
─────────────────   ──────────────────────────────────────────────    ──────────  ────────────────  ──────
nyc                 189 Atlantic Ave, Brooklyn                        13/13 ✓     nyc311=29         101 s
chicago             233 S Wacker Dr, Chicago, IL                      13/13 ✓     chicago_311=200   1.2 s
seattle             2100 5th Ave, Seattle, WA                         13/13 ✓     (none, by design) 0.6 s
sf                  1 Dr Carlton B Goodlett Pl, San Francisco, CA     13/13 ✓     sf_311=200        2.6 s
boston              1 City Hall Square, Boston, MA                    13/13 ✓     boston_311=396    0.6 s
```

5/5 PASS. Probe results saved to `outputs/probe_cities.json`. Reproduce with
`.venv/bin/python scripts/probe_cities.py`.

## Pytest

```
42 passed, 6 skipped, 1 warning in 34s
```

Skipped tests need a live backend (`test_integration.py`,
`test_sample_queries.py`, `test_agent_e2e.py`) — run separately when
the server is up.

New tests this round (in `tests/test_byod_load.py`):

- `test_base_registry_excludes_byod_pebble` — no env, no `.riprap/`, no override
- `test_extra_manifests_env_merges_pebble` — env var path merges
- `test_extra_manifests_single_file_entry` — env var accepts a single yaml
- `test_dotriprap_auto_discovery` — `${CWD}/.riprap/*.yaml` auto-merges
- `test_byod_manifest_resolves_paths_against_manifest_dir` — the key portability guarantee
- `test_byod_pebble_portable_across_deployments` — same manifest, NYC vs Boston base
- `test_byod_id_collision_overrides_base` — override + stderr warning

## Lint (ruff)

All touched files clean. Real bugs fixed during this pass:

- `web/main.py:_run_compare` — B023 loop-variable capture in the per-target
  trace wrapper. The captured `_q` and `_label` were defined in the loop
  body and used inside a class method, so a future change that lets the
  `_TaggedQ` instance outlive the iteration would silently bind to the
  last-iteration values. Fixed by binding via `__init__` parameters.
- `tests/test_stone_envelope.py::test_step_to_stone_mapping_covers_known_steps`
  — was grepping `web/main.py` source for literal `"floodnet"` etc., but
  the pebble refactor moved `_STEP_TO_STONE` to a runtime dict comp. The
  test now asserts against the imported `_STEP_TO_STONE` directly, which
  is what we actually want to verify.

## UI (Playwright smoke, inference-offline)

Drove `http://127.0.0.1:8765/` with `189 Atlantic Avenue, Brooklyn`:

- SvelteKit landing page renders cleanly (search form, methodology, sources)
- Form submit routes to `/q/<address>`
- SSE stream connects; trace envelope frames all 5 Stone regions
- With vLLM Space paused: surfaces "All routing targets exhausted" inline
  with a link to status, no broken UI states. **Graceful offline path verified.**
- Cornerstone shows all 5 specialist functions in the provenance list,
  each reporting why they didn't fire (`query outside NYC bounds`, `no marks
  within 800m`, etc.)

The full LLM happy-path needs `RIPRAP_LLM_BASE_URL` pointing at a live
Granite 4.1 endpoint. Tested separately when the RunPod pod is warm.

## BYOD demonstration (NYC + Boston deployments)

`examples/byod/fdny_firehouses.{yaml,csv}` (real NYC Open Data, 219 records):

| Loading path | Deployment | Address | Result |
|---|---|---|---|
| `RIPRAP_EXTRA_MANIFESTS=examples/byod` | NYC | 189 Atlantic Ave | 4 in 1.5 km radius, nearest Engine 224 @ 274 Hicks (454 m), 13/13 compliance |
| `cp into ./.riprap/ && cd ./.riprap/..` | NYC | 80 Pioneer St, Red Hook | 2 in 1.5 km, nearest Battalion 32/Engine 202/Ladder 101, 13/13 compliance |
| `RIPRAP_EXTRA_MANIFESTS=examples/byod` | Boston | 1 City Hall Square | 0 in radius (correct — NYC-only CSV), nearest 282 km away in Manhattan, Boston-native pebbles still flow (`boston_311=396`), 13/13 compliance |

## Adapters in the registry

```
ADAPTERS = {
  "baked_vector",       # GeoJSON / GeoTIFF / Parquet
  "ckan_records",       # NEW — Boston, Philly, EU portals
  "csv_points",         # Tabular point data
  "local_corpus_with_ner",  # RAG + NER consolidated
  "python_call",        # Escape hatch for custom Python
  "rest_json",          # Generic REST + JMESPath
  "socrata_records",    # NYC, Chicago, Seattle, SF, DC, ...
}
```

## What's still pending

- **LLM happy-path UI smoke** — gated on RunPod L4 reaching healthz green
  (pod `9qziz4l893tbkq`, bring-up in progress at writing).
- **Triton bring-up runbook** — once the pod is verified, document the
  one-command spin-up + env propagation back to `RIPRAP_LLM_BASE_URL`.
- **Token hygiene** — the `runpodctl pod get` response surfaces the
  `HF_TOKEN` and `RIPRAP_PROXY_TOKEN` env vars in plaintext; rotate
  after teardown.
