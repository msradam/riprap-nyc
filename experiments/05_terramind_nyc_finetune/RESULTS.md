# TerraMind-NYC fine-tune — results & next-session handoff

This file is the canonical handoff to whoever picks up integration after
the experiment completes. Read this first; everything else is
supporting detail.

## Summary

We ran two-phase TerraMind fine-tunes on AMD MI300X via AMD Developer Cloud:

- **Phase 1** — reproduce IBM-ESA's `TerraMind-base-Flood` recipe on AMD.
  Checkpoint: `<handle>/TerraMind-base-Flood-AMD-reproduction` ({{verdict_p1}}).
- **Phase 2** — continuation fine-tune on NYC chips with Phase-1
  Prithvi-EO water-mask pseudo-labels.
  Checkpoint: `<handle>/TerraMind-base-Flood-NYC` ({{verdict_p2}}).

Eval spec governing the publication decisions: `eval/eval_spec_v2.md`.
Eval-spec v1 was abandoned mid-Sunday for documented reasons —
postmortem in `eval/v1_synth_sar_postmortem.md`.

## Should this land in production Riprap?

**Phase-1 checkpoint:** {{integrate_p1}}

- **If "yes":** swap `app/specialists/terramind.py`'s base model id from
  `ibm-esa-geospatial/TerraMind-1.0-base` to
  `<handle>/TerraMind-base-Flood-AMD-reproduction`. Same
  `LightningInferenceModel.from_config` call signature; behaviour
  should be identical to base TerraMind plus the IBM-Flood task head.
  Estimated dev time: **15 min** (model id swap + smoke test on a
  single Riprap query).
- **If "no":** Phase-1 is a hardware-reproduction artifact, not a model
  upgrade. Riprap stays on base TerraMind for now.

**Phase-2 checkpoint:** {{integrate_p2}}

- **If "yes":** swap `app/specialists/terramind.py` to use the Phase-2
  checkpoint specifically for NYC queries (the only place it has been
  validated). Add a guard: if the query is outside NYC bbox, fall
  back to the Phase-1 or base checkpoint. Estimated dev time:
  **30–45 min** (model swap + bbox guard + Riprap-side smoke
  across 3 NYC test queries: dense urban, waterfront, lower-density).
- **If "no":** publish the Phase-2 checkpoint with honest
  no-measurable-lift framing; do not integrate.

## Caveats for the integrating session

1. **Static asset cache.** Riprap's frontend caches JS bundles hard.
   If the integration changes any frontend behaviour, hard-reload
   needed (⌘⇧R). The TerraMind specialist is backend-only so this
   shouldn't bite, but worth a check.

2. **Hardware label pill.** `web/main.py:/api/backend` uses
   `RIPRAP_HARDWARE_LABEL` to set the UI's hardware pill. If the
   demo runs on AMD MI300X, set it accordingly:
   ```bash
   RIPRAP_HARDWARE_LABEL="AMD MI300X" \
   RIPRAP_ENGINE_LABEL="vLLM (Granite 4.1) + TerraMind-NYC" \
   RIPRAP_LLM_PRIMARY=vllm RIPRAP_LLM_BASE_URL=... \
   .venv/bin/uvicorn web.main:app --host 0.0.0.0 --port 7860
   ```

3. **Specialist trace UI.** The frontend's `STEP_LABELS` in
   `web/static/agent.js` will show the specialist by name. If we
   want users to see "TerraMind-NYC" instead of "TerraMind base," the
   step label needs updating. Trivial change.

4. **Cost discipline.** If the production deploy uses MI300X for
   inference, per-query latency is meaningfully better than NVIDIA T4
   on HF Spaces but burns AMD Developer Cloud credit at $1.99/hr.
   The fallback path is local Ollama (`granite4.1:8b`) — see the
   "Running locally" section of the root `README.md`.

5. **TerraMind-base-Flood-AMD vs TerraMind-base-Flood (IBM's).** Even
   if our Phase-1 reproduction is statistically indistinguishable from
   IBM's checkpoint, Riprap should likely cite **both** — IBM's as the
   "trusted upstream baseline" and ours as the "we-verified-it-on-AMD
   variant." Pick one for the actual integration; cite both in the
   model-cite footnote in the Riprap UI.

## Files in this experiment directory

| Path | What it is |
|---|---|
| `eval/eval_spec_v2.md` | Locked spec; superseded v1 |
| `eval/eval_spec.md` | v1 (synth-SAR), shelved; see postmortem |
| `eval/v1_synth_sar_postmortem.md` | Why we pivoted from v1 to v2 |
| `eval/phase1_baseline_amd.md` | IBM checkpoint inferred on AMD = our reproduction target (mIoU 0.6663) |
| `eval/phase1_results.md` | Final Phase-1 numbers (post-training) |
| `eval/phase2_results.md` | Final Phase-2 NYC numbers (post-training) |
| `data/build_manifest.py` | STAC manifest builder (Phase 2; salvageable from v1) |
| `data/extract_chips.py` | NYC chip extractor (Phase 2; needs anchor-presence-test fix) |
| `data/manifest_holdout.jsonl` | Cloudy April 2026 holdout records |
| `training/terramind_v1_base_impactmesh_flood_amd.yaml` | Phase-1 reproduction config |
| `training/verify_phase1.py` | 10-test verification battery; emits `report.md` |
| `training/smoke_encoder.py` | Encoder forward smoke (passes; pre-flight) |
| `restore/backup.sh` | Pull critical state to local |
| `restore/RESTORE.md` | Recovery procedure if droplet dies |
| `publish/MODEL_CARD_template.md` | Auto-fillable card from verifier output |
| `NOTES.md` | Session log; droplet state, container layout, anomalies |

## Lessons that generalize beyond this experiment

1. **Curated benchmark > bespoke STAC pipeline** when the deliverable
   is "we fine-tuned a model on this hardware." Use ImpactMesh-Flood,
   Sen1Floods11, or BurnScars; don't build a chip pipeline from STAC
   for a hackathon-budget project unless the bespoke data is the
   entire scientific contribution.
2. **MGRS bbox metadata is loose.** Use `raster.bounds`, not scene
   bbox, for any future Sentinel-2 chip-extraction.
3. **PC API flakiness is bursty.** Heavy retries with backoff +
   manifest-pre-signed-URL fallback are mandatory.
4. **Publish negative results.** Even if a fine-tune underperforms,
   the artifact + honest model card are valuable to the field.
5. **Reproduction-style fine-tunes are easier to verify than bespoke
   ones.** The model card writes itself.
