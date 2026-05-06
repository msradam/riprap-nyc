#!/usr/bin/env bash
# Smoke test the AMD GPU droplet (vLLM + riprap-models).
# Usage: bash scripts/smoke_test_gpu.sh <ip> <token>
set -euo pipefail

IP="${1:?Usage: smoke_test_gpu.sh <ip> <token>}"
TOKEN="${2:?Usage: smoke_test_gpu.sh <ip> <token>}"
VLLM_URL="http://${IP}:8001"
ML_URL="http://${IP}:7860"

PASS=0
FAIL=0

check() {
  local label="$1"; shift
  local status
  if status=$(eval "$@" 2>&1); then
    echo "  PASS  $label"
    PASS=$((PASS+1))
  else
    echo "  FAIL  $label"
    echo "        $status"
    FAIL=$((FAIL+1))
  fi
}

echo "=== Smoke test: $IP ==="
echo ""

echo "--- vLLM (port 8001) ---"
check "vLLM /v1/models" \
  "curl -sf -H 'Authorization: Bearer $TOKEN' $VLLM_URL/v1/models | python3 -c 'import sys,json; d=json.load(sys.stdin); assert len(d[\"data\"]) > 0'"

check "vLLM /v1/chat/completions" \
  "curl -sf -H 'Authorization: Bearer $TOKEN' -H 'Content-Type: application/json' \
    -d '{\"model\":\"granite-4.1-8b\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":5}' \
    $VLLM_URL/v1/chat/completions | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d[\"choices\"][0][\"message\"][\"content\"]'"

echo ""
echo "--- riprap-models (port 7860) ---"
check "riprap-models /healthz" \
  "curl -sf $ML_URL/healthz | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d.get(\"ok\") == True'"

check "riprap-models /v1/granite-embed" \
  "curl -sf -H 'Authorization: Bearer $TOKEN' -H 'Content-Type: application/json' \
    -d '{\"texts\":[\"flood risk in NYC\"]}' \
    $ML_URL/v1/granite-embed | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d.get(\"ok\") and len(d[\"vectors\"]) == 1 and len(d[\"vectors\"][0]) > 0'"

check "riprap-models /v1/gliner-extract" \
  "curl -sf -H 'Authorization: Bearer $TOKEN' -H 'Content-Type: application/json' \
    -d '{\"text\":\"Hurricane Sandy flooded 80 Pioneer Street in Red Hook Brooklyn.\",\"labels\":[\"location\",\"event\"]}' \
    $ML_URL/v1/gliner-extract | python3 -c 'import sys,json; d=json.load(sys.stdin); assert \"entities\" in d'"

echo ""
echo "=== Results: ${PASS} PASS, ${FAIL} FAIL ==="
[ "$FAIL" -eq 0 ]
