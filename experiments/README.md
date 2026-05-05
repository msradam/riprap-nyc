# Riprap experiments

Exploratory model-prototyping scratch space. **Nothing here ships to
production until it has a `RESULTS.md` documenting double-gated
validation (Ollama + AMD vLLM) and an integration plan agreed
upstream.**

## Conventions

- Each experiment is `NN_<name>/` and is fully self-contained.
- `shared/` is the only cross-experiment code: backend client
  (`shared/backends.py`), doc_id helpers (`shared/doc_id.py`), trace
  renderer mock (`shared/trace_render.py`), and the running license
  ledger (`shared/licenses.md`).
- `.cache/` directories inside experiments hold downloaded HF models
  and cached HTTP responses; gitignored.
- `requirements-experiments.txt` (top-level) is the experiment-only
  dependency set. Production `requirements.txt` is **not** modified.
- All experiments call into Riprap's existing LLM abstraction via
  `from app import llm` (or `shared.backends`). Experiments do not
  fork the call surface.

## Test addresses

Three points used across all experiments — they exercise the three
NYC flood mechanisms and one each from Brooklyn / Queens / Bronx.

| Name | lat, lon | Mechanism |
|------|----------|-----------|
| Brighton Beach (Brooklyn) | 40.5780, -73.9617 | coastal |
| Hollis (Queens)           | 40.7115, -73.7681 | pluvial |
| Hunts Point (Bronx)       | 40.8155, -73.8830 | mixed   |

## Status

| Phase | Specialist | Status |
|------:|------------|--------|
| 0 | Endpoints smoke tests | done · 8/8 pass |
| 1 | Prithvi-EO live water segmentation | done · double-gated 3/3 addresses |
| 2 | GLiNER structured extraction | done · double-gated on real corpus PDF |
| 3 | Granite Embedding Reranker R2 | done · double-gated; reorders top-3 |
| 4 | TerraMind synthetic SAR | post-hackathon |
| 5 | SAM 2 promptable | post-hackathon |
| 6 | Chronos-Bolt forecast | post-hackathon |
