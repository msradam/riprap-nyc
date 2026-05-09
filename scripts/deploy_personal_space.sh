#!/usr/bin/env bash
# Deploy to the personal HF Space (msradam/riprap-nyc) only.
#
# This script intentionally never touches the lablab Space (which is
# the AMD-judging artifact). It pushes to the `personal` git remote;
# if that remote does not exist, it creates it. It also swaps
# Dockerfile.l4 → Dockerfile in the working tree on the push branch
# only — the main branch keeps the canonical T4 Dockerfile.
#
# Usage:
#   scripts/deploy_personal_space.sh           # push current HEAD
#   scripts/deploy_personal_space.sh --setup   # one-time: add remote, set secrets

set -euo pipefail

PERSONAL_REMOTE="personal"
PERSONAL_URL="https://huggingface.co/spaces/msradam/riprap-nyc"
PERSONAL_BRANCH="hf-personal"
LABLAB_NAME_PATTERN="AMD-hackathon|lablab-ai"

guard_against_lablab () {
    # Refuse to run if the working tree's "origin" or any remote whose
    # URL matches the lablab Space is the push target.
    for r in $(git remote); do
        url=$(git remote get-url "$r" 2>/dev/null || echo "")
        if echo "$url" | grep -qE "$LABLAB_NAME_PATTERN"; then
            if [ "$r" = "$PERSONAL_REMOTE" ]; then
                echo "FATAL: remote '$PERSONAL_REMOTE' points at the lablab Space ($url)."
                echo "       This script will not push there. Re-add the personal Space remote."
                exit 1
            fi
        fi
    done
}

if [ "${1:-}" = "--setup" ]; then
    guard_against_lablab
    if ! git remote | grep -q "^${PERSONAL_REMOTE}$"; then
        echo "[deploy] adding remote '$PERSONAL_REMOTE' → $PERSONAL_URL"
        git remote add "$PERSONAL_REMOTE" "$PERSONAL_URL"
    else
        existing=$(git remote get-url "$PERSONAL_REMOTE")
        if [ "$existing" != "$PERSONAL_URL" ]; then
            echo "FATAL: remote '$PERSONAL_REMOTE' exists but points at $existing"
            echo "       expected: $PERSONAL_URL"
            exit 1
        fi
    fi
    echo "[deploy] set the following secrets in the personal Space (Settings → Variables and secrets):"
    echo "         HF_TOKEN              <your Hugging Face token>"
    echo "         RIPRAP_LLM_PRIMARY    ollama"
    echo "         RIPRAP_ML_BACKEND     remote"
    echo "         (optional) any GLiNER / embedding HF tokens"
    exit 0
fi

guard_against_lablab

if ! git remote | grep -q "^${PERSONAL_REMOTE}$"; then
    echo "FATAL: remote '$PERSONAL_REMOTE' is not configured. Run with --setup first."
    exit 1
fi

# Build a deploy branch that uses Dockerfile.l4 as Dockerfile and
# entrypoint.l4.sh as entrypoint.sh. We never modify main.
DEPLOY_TMP="$(git rev-parse --show-toplevel)/.deploy-tmp-l4"
rm -rf "$DEPLOY_TMP"
git worktree add -B "$PERSONAL_BRANCH" "$DEPLOY_TMP" HEAD

(
    cd "$DEPLOY_TMP"
    cp Dockerfile.l4    Dockerfile
    cp entrypoint.l4.sh entrypoint.sh
    chmod +x entrypoint.sh
    git add Dockerfile entrypoint.sh
    git commit -m "deploy(l4): swap Dockerfile.l4 → Dockerfile for personal Space" || true

    echo "[deploy] pushing $PERSONAL_BRANCH → $PERSONAL_REMOTE main ..."
    git push --force-with-lease "$PERSONAL_REMOTE" "${PERSONAL_BRANCH}:main"
)

git worktree remove --force "$DEPLOY_TMP"
echo "[deploy] done. Watch build at: ${PERSONAL_URL}"
