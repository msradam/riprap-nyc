#!/usr/bin/env bash
# Update HF Space env vars to point at a new droplet, restart the Space,
# and poll until the agent endpoint returns HTTP 200.
#
# Usage: scripts/update_hf_env.sh <droplet-ip> <bearer-token>
#
# Requires:
#   huggingface_hub >= 0.36 installed (provides the Python API used below;
#   note: 'huggingface-cli space variables' does not exist in this version)
#   Either:
#     - `huggingface-cli login` cached token (preferred), OR
#     - HF_TOKEN env var
#   HfApi() picks up the cached login automatically; HF_TOKEN overrides.
#
# Space slug: lablab-ai-amd-developer-hackathon/riprap-nyc
# Variables set (from docs/DROPLET-RUNBOOK.md §Required secrets):
#   RIPRAP_LLM_PRIMARY    vllm
#   RIPRAP_LLM_BASE_URL   http://<ip>:8001/v1
#   RIPRAP_LLM_API_KEY    <token>
#   RIPRAP_ML_BACKEND     remote
#   RIPRAP_ML_BASE_URL    http://<ip>:7860
#   RIPRAP_ML_API_KEY     <token>
#   RIPRAP_NYCHA_REGISTERS 1
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <droplet-ip> <bearer-token>" >&2
    exit 1
fi

IP="$1"
TOKEN="$2"

SPACE_ID="lablab-ai-amd-developer-hackathon/riprap-nyc"
SPACE_URL="https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space"
VLLM_PORT=8001
MODELS_PORT=7860

echo "==> Updating HF Space variables"
echo "    space:        ${SPACE_ID}"
echo "    droplet ip:   ${IP}"
echo "    vLLM port:    ${VLLM_PORT}"
echo "    models port:  ${MODELS_PORT}"
echo

# ---- 1. Set all six Space variables via the huggingface_hub Python API ----
# huggingface-cli space variables does not exist in huggingface_hub 0.36.x;
# add_space_variable is the documented programmatic interface.
python3 -c "
import sys, os
try:
    from huggingface_hub import HfApi
except ImportError:
    print('Error: huggingface_hub not installed', file=sys.stderr)
    sys.exit(1)

api = HfApi(token=os.environ.get('HF_TOKEN'))  # None → cached CLI login
space_id = '${SPACE_ID}'
ip = '${IP}'
token = '${TOKEN}'
vllm_port = ${VLLM_PORT}
models_port = ${MODELS_PORT}

variables = {
    'RIPRAP_LLM_PRIMARY':  'vllm',
    'RIPRAP_LLM_BASE_URL': f'http://{ip}:{vllm_port}/v1',
    'RIPRAP_LLM_API_KEY':  token,
    'RIPRAP_ML_BACKEND':   'remote',
    'RIPRAP_ML_BASE_URL':  f'http://{ip}:{models_port}',
    'RIPRAP_ML_API_KEY':   token,
    # Heavy register specialists (NYCHA / DOE schools / DOH hospitals).
    # Pre-warmed at boot via web/main.py:_warm_caches when this is set;
    # without it the FSM never adds these step functions, so the demo
    # never sees register cards even when the underlying data is loaded.
    'RIPRAP_NYCHA_REGISTERS': '1',
}

for key, value in variables.items():
    display = '<redacted>' if 'KEY' in key else value
    print(f'    setting {key} = {display}')
    api.add_space_variable(repo_id=space_id, key=key, value=value)

print('[python] all 6 variables set')
"
echo

# ---- 2. Restart the Space ------------------------------------------------
echo "==> Restarting HF Space"
python3 -c "
import os
from huggingface_hub import HfApi
api = HfApi(token=os.environ.get('HF_TOKEN'))  # None → cached CLI login
rt = api.restart_space(repo_id='${SPACE_ID}')
print(f'    stage after restart request: {rt.stage}')
"
echo

# ---- 3. Poll /api/backend until HTTP 200 (max 120 s) ---------------------
# /api/backend is documented in docs/DROPLET-RUNBOOK.md §Destroy checklist
# as the endpoint to verify the Space is serving.
echo "==> Polling ${SPACE_URL}/api/backend (up to 120 s)..."
DEADLINE=$((SECONDS + 120))
HEALTHY=0
while (( SECONDS < DEADLINE )); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 10 "${SPACE_URL}/api/backend" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        HEALTHY=1
        break
    fi
    echo "    (${HTTP_CODE}) not ready yet — waiting 10 s..."
    sleep 10
done

if [ "$HEALTHY" -ne 1 ]; then
    echo "HF Space did not become healthy within 120s" >&2
    exit 1
fi

echo
echo "HF Space updated and healthy. IP=${IP}"
