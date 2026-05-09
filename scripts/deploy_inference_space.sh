#!/usr/bin/env bash
# Deploy the Riprap inference Space (msradam/riprap-inference) — the
# headless GPU API both UI Spaces (lablab + personal) call into.
#
# Same orphan-branch pattern as deploy_personal_space.sh: the full
# git history of the source repo would trip HF Spaces' binary-file
# gate, so we push a single fresh commit containing only what the
# inference Space needs to run.

set -euo pipefail

REMOTE="inference"
URL="https://huggingface.co/spaces/msradam/riprap-inference"
BRANCH="hf-inference"
LABLAB_NAME_PATTERN="AMD-hackathon|lablab-ai"

guard_against_lablab () {
    if echo "$URL" | grep -qE "$LABLAB_NAME_PATTERN"; then
        echo "FATAL: URL ($URL) matches the lablab org pattern."
        exit 1
    fi
    final=$(curl -sIL -o /dev/null -w "%{url_effective}" "$URL")
    if echo "$final" | grep -qE "$LABLAB_NAME_PATTERN"; then
        echo "FATAL: URL ($URL) redirects to a lablab-org URL ($final)"
        exit 1
    fi
}

if [ "${1:-}" = "--setup" ]; then
    guard_against_lablab
    if ! git remote | grep -q "^${REMOTE}$"; then
        echo "[deploy.inf] adding remote '$REMOTE' → $URL"
        git remote add "$REMOTE" "$URL"
    fi
    echo "[deploy.inf] set the following secrets in the inference Space"
    echo "             (Settings → Variables and secrets):"
    echo "         RIPRAP_PROXY_TOKEN    <a long random secret>"
    echo "         HF_TOKEN              <your HF token, if any model is gated>"
    echo "[deploy.inf] then set the same RIPRAP_PROXY_TOKEN as RIPRAP_LLM_API_KEY"
    echo "             on both the lablab-org Space and msradam/riprap."
    exit 0
fi

guard_against_lablab

DEPLOY_TMP="$(git rev-parse --show-toplevel)/.deploy-tmp-inf"
rm -rf "$DEPLOY_TMP"
git worktree add --detach "$DEPLOY_TMP" HEAD

(
    cd "$DEPLOY_TMP"
    git checkout --orphan "$BRANCH"

    # Strip everything except what the inference container needs.
    rm -rf slides/ submission/ docs/ pitch/ research/ corpus/ \
           assets/ \
           tests/ experiments/ \
           data/ \
           web/ app/ scripts/ \
           Dockerfile Dockerfile.app Dockerfile.l4 \
           docker-compose.yml entrypoint.sh entrypoint.l4.sh \
           pyproject.toml uv.lock \
           agent.py riprap.py helios_nyc.py \
           ARCHITECTURE.md METHODOLOGY.md RESEARCH.md \
           LICENSE NOTICE README.md requirements*.txt

    # Inference Dockerfile + entrypoint + proxy go to the repo root
    # (HF Spaces convention — Dockerfile + entrypoint.sh + proxy.py at
    # top level).
    mv inference/Dockerfile     ./Dockerfile
    mv inference/entrypoint.sh  ./entrypoint.sh
    mv inference/proxy.py       ./proxy.py
    rmdir inference 2>/dev/null || true
    chmod +x entrypoint.sh

    # The Dockerfile COPYs services/riprap-models/{main.py,requirements.txt}
    # so keep that path. Trim everything else under services/.
    find services -mindepth 1 -maxdepth 1 -not -name riprap-models -exec rm -rf {} +
    find services/riprap-models -mindepth 1 \
         -not -name main.py -not -name requirements.txt -exec rm -rf {} +

    cat > README.md <<'README'
---
title: Riprap Inference (Headless GPU API)
emoji: 🌊
colorFrom: indigo
colorTo: blue
sdk: docker
pinned: false
short_description: Headless GPU API for Riprap. Bearer-auth proxy on L4.
---

# Riprap Inference Space

Headless GPU API for [Riprap](https://github.com/msradam/riprap-nyc).
Runs Granite 4.1 (Ollama, OpenAI-compatible) and the riprap-models
specialist service (Prithvi-EO 2.0 NYC-Pluvial, TerraMind LULC +
Buildings + Synthesis, Granite TTM r2, Granite Embedding, GLiNER)
behind a single FastAPI bearer-auth proxy on port 7860.

Two UI Spaces consume this:

- `lablab-ai-amd-developer-hackathon/riprap-nyc` — official AMD
  hackathon submission (CPU UI).
- `msradam/riprap` — personal mirror (CPU UI).

Both pass `Authorization: Bearer <RIPRAP_PROXY_TOKEN>` and call
`/v1/chat/completions`, `/v1/embeddings`, `/v1/prithvi-pluvial`,
`/v1/terramind`, `/v1/ttm-forecast`, `/v1/gliner-extract`.

Apache 2.0. Source: https://github.com/msradam/riprap-nyc.
README

    git add -A
    git -c user.email=msrahmanadam@gmail.com -c user.name="Adam Munawar Rahman" \
        commit -m "deploy(inference): headless GPU API on L4"

    echo "[deploy.inf] pushing $BRANCH → $REMOTE main ..."
    git push --force "$REMOTE" "${BRANCH}:main"
)

git worktree remove --force "$DEPLOY_TMP"
git branch -D "$BRANCH" 2>/dev/null || true
echo "[deploy.inf] done. Watch build at: ${URL}"
