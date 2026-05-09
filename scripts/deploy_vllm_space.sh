#!/usr/bin/env bash
# Deploy the Riprap vLLM Space (msradam/riprap-vllm) — primary inference
# backend, parallel to the Ollama-backed riprap-inference fallback.
#
# Same orphan-branch pattern as the other deploy scripts.

set -euo pipefail

REMOTE="vllm"
URL="https://huggingface.co/spaces/msradam/riprap-vllm"
BRANCH="hf-vllm"
LABLAB_NAME_PATTERN="AMD-hackathon|lablab-ai"
SOURCE_DIR="inference-vllm"

guard_against_lablab () {
    if echo "$URL" | grep -qE "$LABLAB_NAME_PATTERN"; then
        echo "FATAL: URL ($URL) matches the lablab org pattern."
        exit 1
    fi
    final=$(curl -sIL -o /dev/null -w "%{url_effective}" "$URL")
    if echo "$final" | grep -qE "$LABLAB_NAME_PATTERN"; then
        echo "FATAL: URL ($URL) redirects to lablab-org URL ($final)"
        exit 1
    fi
}

if [ "${1:-}" = "--setup" ]; then
    guard_against_lablab
    if ! git remote | grep -q "^${REMOTE}$"; then
        echo "[deploy.vllm] adding remote '$REMOTE' → $URL"
        git remote add "$REMOTE" "$URL"
    fi
    echo "[deploy.vllm] set RIPRAP_PROXY_TOKEN secret on the Space"
    exit 0
fi

guard_against_lablab

DEPLOY_TMP="$(git rev-parse --show-toplevel)/.deploy-tmp-vllm"
rm -rf "$DEPLOY_TMP"
git worktree add --detach "$DEPLOY_TMP" HEAD

(
    cd "$DEPLOY_TMP"
    git checkout --orphan "$BRANCH"

    rm -rf slides/ submission/ docs/ pitch/ research/ corpus/ \
           assets/ \
           tests/ experiments/ \
           data/ \
           web/ app/ scripts/ \
           inference/ \
           Dockerfile Dockerfile.app Dockerfile.l4 \
           docker-compose.yml entrypoint.sh entrypoint.l4.sh \
           pyproject.toml uv.lock \
           agent.py riprap.py helios_nyc.py \
           ARCHITECTURE.md METHODOLOGY.md RESEARCH.md \
           LICENSE NOTICE README.md requirements*.txt

    mv "${SOURCE_DIR}/Dockerfile"     ./Dockerfile
    mv "${SOURCE_DIR}/entrypoint.sh"  ./entrypoint.sh
    mv "${SOURCE_DIR}/proxy.py"       ./proxy.py
    rmdir "$SOURCE_DIR" 2>/dev/null || true
    chmod +x entrypoint.sh

    find services -mindepth 1 -maxdepth 1 -not -name riprap-models -exec rm -rf {} +
    find services/riprap-models -mindepth 1 \
         -not -name main.py -not -name requirements.txt -exec rm -rf {} +

    cat > README.md <<'README'
---
title: Riprap vLLM (Headless GPU API)
emoji: 🌊
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
short_description: vLLM-backed Granite 4.1 8B FP8 + EO stack for Riprap.
---

# Riprap vLLM Space

Primary headless GPU API for [Riprap](https://github.com/msradam/riprap-nyc).
Runs Granite 4.1 8B FP8 via vLLM (OpenAI-compatible) and the
riprap-models specialist service (Prithvi-EO 2.0 NYC-Pluvial,
TerraMind LULC + Buildings, Granite TTM r2, Granite Embedding,
GLiNER) behind a single FastAPI bearer-auth proxy on port 7860.

A parallel Ollama-backed Space (`msradam/riprap-inference`) serves
the same surface as a fallback when this one is paused or rebuilding.

Apache 2.0. Source: https://github.com/msradam/riprap-nyc.
README

    git add -A
    git -c user.email=msrahmanadam@gmail.com -c user.name="Adam Munawar Rahman" \
        commit -m "deploy(vllm): vLLM-backed Granite 4.1 8B FP8 inference Space"

    echo "[deploy.vllm] pushing $BRANCH → $REMOTE main ..."
    git push --force "$REMOTE" "${BRANCH}:main"
)

git worktree remove --force "$DEPLOY_TMP"
git branch -D "$BRANCH" 2>/dev/null || true
echo "[deploy.vllm] done. Watch build at: ${URL}"
