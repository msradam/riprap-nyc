#!/usr/bin/env bash
# Point the lablab HF Space at the msradam/riprap-vllm Space instead of a
# droplet IP.  Run this once when you want the official submission Space to
# use the persistent vLLM HF Space GPU backend.
#
# Usage: scripts/point_lablab_at_vllm_space.sh <proxy-token>
#
#   <proxy-token>  The RIPRAP_PROXY_TOKEN secret already set on
#                  msradam/riprap-vllm.  Both Spaces must share the same
#                  value — the UI Space sends it as the Bearer token in
#                  RIPRAP_LLM_API_KEY / RIPRAP_ML_API_KEY.
#
# Requires: huggingface_hub installed + `huggingface-cli login` (or HF_TOKEN)

set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <proxy-token>" >&2
    exit 1
fi

TOKEN="$1"

LABLAB_SPACE="lablab-ai-amd-developer-hackathon/riprap-nyc"
LABLAB_URL="https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space"
VLLM_SPACE_HOST="https://msradam-riprap-vllm.hf.space"

echo "==> Pointing lablab Space at msradam/riprap-vllm"
echo "    lablab space:  ${LABLAB_SPACE}"
echo "    vllm backend:  ${VLLM_SPACE_HOST}"
echo

python3 -c "
import sys, os
try:
    from huggingface_hub import HfApi
except ImportError:
    print('Error: huggingface_hub not installed', file=sys.stderr)
    sys.exit(1)

api = HfApi(token=os.environ.get('HF_TOKEN'))
space_id = '${LABLAB_SPACE}'
token = '${TOKEN}'
vllm_host = '${VLLM_SPACE_HOST}'

variables = {
    'RIPRAP_LLM_PRIMARY':    'vllm',
    'RIPRAP_LLM_BASE_URL':   f'{vllm_host}/v1',
    'RIPRAP_LLM_API_KEY':    token,
    'RIPRAP_ML_BACKEND':     'remote',
    'RIPRAP_ML_BASE_URL':    vllm_host,
    'RIPRAP_ML_API_KEY':     token,
    'RIPRAP_NYCHA_REGISTERS': '1',
}

for key, value in variables.items():
    display = '<redacted>' if 'KEY' in key else value
    print(f'    setting {key} = {display}')
    api.add_space_variable(repo_id=space_id, key=key, value=value)

print('[python] all 7 variables set')
"
echo

echo "==> Restarting lablab Space"
python3 -c "
import os
from huggingface_hub import HfApi
api = HfApi(token=os.environ.get('HF_TOKEN'))
rt = api.restart_space(repo_id='${LABLAB_SPACE}')
print(f'    stage after restart request: {rt.stage}')
"
echo

echo "==> Polling ${LABLAB_URL}/api/backend (up to 180 s)..."
DEADLINE=$((SECONDS + 180))
HEALTHY=0
while (( SECONDS < DEADLINE )); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 15 "${LABLAB_URL}/api/backend" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        HEALTHY=1
        break
    fi
    echo "    (${HTTP_CODE}) not ready yet — waiting 10 s..."
    sleep 10
done

if [ "$HEALTHY" -ne 1 ]; then
    echo "lablab Space did not become healthy within 180 s" >&2
    exit 1
fi

echo
echo "Done. lablab Space is live and pointing at ${VLLM_SPACE_HOST}"
