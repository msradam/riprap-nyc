#!/usr/bin/env bash
# Full redeploy to an existing AMD MI300X droplet.
#
#   1. Generate a fresh bearer token
#   2. scripts/deploy_droplet.sh <ip> <token>   (bring up vLLM + riprap-models)
#   3. scripts/update_hf_env.sh <ip> <token>    (update HF Space vars + restart)
#   4. .venv/bin/python scripts/probe_addresses.py  (5/5 must pass)
#
# Usage: scripts/redeploy.sh <droplet-ip>
#
# Requires:
#   HF_TOKEN  env var with write access to the HF Space
#   .venv     Python virtual environment with probe_addresses.py deps
#   SSH access to the droplet (ssh-agent or SSH_KEY env var)
#
# Exit codes:
#   0  all three steps passed
#   1  deploy_droplet.sh failed (HF Space NOT touched)
#   1  update_hf_env.sh failed (droplet is up but HF Space NOT updated)
#   1  probe_addresses.py failed (deploy + HF update succeeded; not rolled back)
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <droplet-ip>" >&2
    exit 1
fi

IP="$1"

if [ -z "${HF_TOKEN:-}" ]; then
    echo "Error: HF_TOKEN env var is required (write access to the HF Space)" >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
START_SECONDS=$SECONDS

DEPLOY_STATUS="FAIL"
HF_STATUS="FAIL"
PROBE_STATUS="FAIL"

# ---- 1. Generate a fresh bearer token ------------------------------------
# openssl rand -base64 24 produces 32 chars; strip +/= to keep URL-safe.
TOKEN=$(openssl rand -base64 24 | tr -d '/+=')
echo "==> Deploying to ${IP} with fresh token..."
echo

# ---- 2. deploy_droplet.sh ------------------------------------------------
if bash "${REPO_ROOT}/scripts/deploy_droplet.sh" "$IP" "$TOKEN"; then
    DEPLOY_STATUS="PASS"
else
    echo "deploy_droplet.sh failed" >&2
    # Print summary before exiting so the caller sees partial state.
    ELAPSED=$(( SECONDS - START_SECONDS ))
    echo
    echo "=== redeploy summary ==="
    echo "Droplet IP : ${IP}"
    echo "Token      : (not set — deploy failed before token was registered)"
    echo "Deploy     : ${DEPLOY_STATUS}"
    echo "HF Space   : ${HF_STATUS}"
    echo "E2E probe  : ${PROBE_STATUS}"
    printf "Total time : %dm%02ds\n" $(( ELAPSED / 60 )) $(( ELAPSED % 60 ))
    exit 1
fi

echo
echo "==> Deploy succeeded. Updating HF Space..."
echo

# ---- 3. update_hf_env.sh -------------------------------------------------
if bash "${REPO_ROOT}/scripts/update_hf_env.sh" "$IP" "$TOKEN"; then
    HF_STATUS="PASS"
else
    echo "update_hf_env.sh failed. HF Space NOT updated." >&2
    ELAPSED=$(( SECONDS - START_SECONDS ))
    echo
    echo "=== redeploy summary ==="
    echo "Droplet IP : ${IP}"
    echo "Token      : (regenerated, see HF Space vars)"
    echo "Deploy     : ${DEPLOY_STATUS}"
    echo "HF Space   : ${HF_STATUS}"
    echo "E2E probe  : ${PROBE_STATUS}"
    printf "Total time : %dm%02ds\n" $(( ELAPSED / 60 )) $(( ELAPSED % 60 ))
    exit 1
fi

echo
echo "==> HF Space updated. Running end-to-end probe..."
echo

# ---- 4. probe_addresses.py -----------------------------------------------
# probe_addresses.py exits 0 only when 5/5 pass (from docs/DROPLET-RUNBOOK.md).
# Disable set -e for this step so we can capture the exit code and still
# print the summary.
set +e
"${REPO_ROOT}/.venv/bin/python" "${REPO_ROOT}/scripts/probe_addresses.py"
PROBE_EXIT=$?
set -e

if [ "$PROBE_EXIT" -eq 0 ]; then
    PROBE_STATUS="PASS"
else
    PROBE_STATUS="FAIL"
fi

# ---- 5. Summary ----------------------------------------------------------
ELAPSED=$(( SECONDS - START_SECONDS ))
echo
echo "=== redeploy summary ==="
echo "Droplet IP : ${IP}"
echo "Token      : (regenerated, see HF Space vars)"
echo "Deploy     : ${DEPLOY_STATUS}"
echo "HF Space   : ${HF_STATUS}"
echo "E2E probe  : ${PROBE_STATUS}"
printf "Total time : %dm%02ds\n" $(( ELAPSED / 60 )) $(( ELAPSED % 60 ))

# Exit 1 if probe failed; deploy + HF update already succeeded, not rolling back.
[ "$PROBE_STATUS" = "PASS" ]
