# Riprap Models — droplet inference service

GPU inference microservice that runs alongside vLLM on the AMD MI300X
droplet. Exposes one HTTP endpoint per model class consumed by the
Riprap FastAPI app's specialists, so all GPU-accelerable forward
passes (Prithvi-NYC-Pluvial, TerraMind LULC + Buildings, Granite TTM
r2, Granite Embedding 278M, GLiNER) run on the MI300X regardless of
which surface — laptop or HF Space — hosts the FastAPI process.

## Service contract

| Method | Path | Purpose |
|---|---|---|
| GET   | `/healthz`            | reachability probe + which models are warm |
| POST  | `/v1/prithvi-pluvial` | Prithvi-NYC-Pluvial v2 segmentation |
| POST  | `/v1/terramind`       | TerraMind LULC / Buildings / Synthesis (adapter-dispatched) |
| POST  | `/v1/ttm-forecast`    | Granite TTM r2 (zero-shot Battery, fine-tune Battery, weekly 311, FloodNet recurrence) |
| POST  | `/v1/granite-embed`   | Granite Embedding 278M batch encode |
| POST  | `/v1/gliner-extract`  | GLiNER typed-entity extraction |

Auth: bearer token on every `/v1/*` route via `RIPRAP_MODELS_API_KEY`.
Same shape as vLLM. `/healthz` is open so liveness probes don't need
auth.

## Deploy

The droplet's existing `terramind` container already has
`torch+ROCm 7.0`, `terratorch 1.2.7`, `granite-tsfm 0.3.6`,
`transformers 4.57`, `peft`, `safetensors`, `fastapi`, `uvicorn`. The
service code lands under `/workspace/riprap-models/`; only deltas
need installing.

```bash
# Copy code (run from project root)
ssh root@129.212.181.238 'mkdir -p /workspace/riprap-models'
rsync -av --delete services/riprap-models/ \
    root@129.212.181.238:/workspace/riprap-models/

# Install deltas + start uvicorn inside the terramind container
ssh root@129.212.181.238 bash <<'REMOTE'
docker cp /workspace/riprap-models terramind:/workspace/
docker exec -d -e RIPRAP_MODELS_API_KEY="$RIPRAP_MODELS_API_KEY" terramind \
  bash -c "cd /workspace/riprap-models && \
           pip install --no-cache-dir -r requirements.txt && \
           uvicorn main:app --host 0.0.0.0 --port 7860 --log-level info \
                  > /workspace/riprap-models.log 2>&1"
REMOTE
```

Service binds inside the container at `:7860`; the host port
mapping was set when the `terramind` container was created
(`docker run -p 7860:7860 ...`), so externally the service is at
`http://129.212.181.238:7860`.

## Local app config

Set in either env or HF Space variables:

```
RIPRAP_ML_BACKEND   = remote
RIPRAP_ML_BASE_URL  = http://129.212.181.238:7860
RIPRAP_ML_API_KEY   = <bearer>
```

`app/inference.py` posts to those endpoints; specialists fall back
to local in-process model loads when the service is unreachable.
