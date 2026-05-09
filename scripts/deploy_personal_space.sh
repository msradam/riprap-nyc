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
# IMPORTANT: HF redirects <username>/<repo-name> back to the canonical
# org Space if the repo doesn't exist on the personal account. So the
# personal Space MUST have a different repo name (e.g. -mirror or -l4)
# than the org Space, or this script will push to the org Space and
# overwrite the official submission. Configure here.
PERSONAL_URL="https://huggingface.co/spaces/msradam/riprap"
PERSONAL_BRANCH="hf-personal"
LABLAB_NAME_PATTERN="AMD-hackathon|lablab-ai"

guard_against_lablab () {
    # Layer 1: the configured PERSONAL_URL must not contain the org name.
    if echo "$PERSONAL_URL" | grep -qE "$LABLAB_NAME_PATTERN"; then
        echo "FATAL: PERSONAL_URL ($PERSONAL_URL) matches the lablab org pattern."
        exit 1
    fi
    # Layer 2: HF's redirect resolution. Follow redirects on the URL
    # and check the final landing URL too. This is the layer that
    # catches the <username>/<repo-name> shorthand redirect.
    final=$(curl -sIL -o /dev/null -w "%{url_effective}" "$PERSONAL_URL")
    if echo "$final" | grep -qE "$LABLAB_NAME_PATTERN"; then
        echo "FATAL: PERSONAL_URL ($PERSONAL_URL) redirects to a lablab-org URL"
        echo "       (resolved to: $final)."
        echo "       The personal Space must have a repo name that does NOT"
        echo "       collide with the org Space. Pick a unique name and"
        echo "       create the Space on HF before re-running this."
        exit 1
    fi
    # Layer 3: configured remotes.
    for r in $(git remote); do
        url=$(git remote get-url "$r" 2>/dev/null || echo "")
        if [ "$r" = "$PERSONAL_REMOTE" ] && echo "$url" | grep -qE "$LABLAB_NAME_PATTERN"; then
            echo "FATAL: remote '$PERSONAL_REMOTE' points at the lablab Space ($url)."
            exit 1
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

# Build a deploy branch with NO history — HF Spaces scans the full
# branch ancestry for binary files and rejects the push if any commit
# anywhere in history contains an unmigrated binary. So we orphan a
# fresh branch from the current tree, prune non-app artifacts, swap
# the Dockerfile and entrypoint, and force-push that single commit.
DEPLOY_TMP="$(git rev-parse --show-toplevel)/.deploy-tmp-l4"
rm -rf "$DEPLOY_TMP"
git worktree add --detach "$DEPLOY_TMP" HEAD

(
    cd "$DEPLOY_TMP"

    # Orphan branch — single commit, no ancestry.
    git checkout --orphan "$PERSONAL_BRANCH"

    # Strip artifacts that don't ship to the running Space. Keep
    # corpus/ — it's the policy-document RAG corpus the FSM reads at
    # runtime, and the Dockerfile COPYs it.
    rm -rf slides/ submission/ docs/ pitch/ research/ \
           assets/screenshots/ \
           assets/cover.png assets/cover-*.png assets/cover-v*.png \
           assets/logo-paper@2x.png assets/logo@2x.png \
           assets/video/ \
           ARCHITECTURE.md METHODOLOGY.md RESEARCH.md \
           NOTICE LICENSE \
           tests/ experiments/ \
           Dockerfile.app docker-compose.yml \
           README.md
    # Swap Dockerfile + entrypoint to the L4 variants.
    cp Dockerfile.l4    Dockerfile
    cp entrypoint.l4.sh entrypoint.sh
    chmod +x entrypoint.sh
    rm -f Dockerfile.l4 entrypoint.l4.sh

    # Minimal Space-facing README with HF Space frontmatter.
    cat > README.md <<'README'
---
title: Riprap NYC (Personal Mirror, L4)
emoji: 🌊
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
short_description: NYC flood-exposure briefings on L4 (self-contained).
---

# Riprap — NYC flood-exposure briefings (L4 self-contained mirror)

This Space is a self-contained mirror of
[`github.com/msradam/riprap-nyc`](https://github.com/msradam/riprap-nyc).

It runs on a single L4 GPU and co-hosts everything in one container:
Granite 4.1 8B (via Ollama), Prithvi-EO 2.0 NYC-Pluvial, TerraMind
LULC + Buildings LoRAs, and Granite TTM r2 — no external droplet
dependency. Sleeps on idle; first request after sleep takes ~45–60 s
to wake.

The hackathon submission Space (CPU UI, droplet proxy) lives at
[`AMD-hackathon/riprap-nyc`](https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space).

Apache 2.0. See the GitHub repo for full source, architecture
deep-dive, methodology, and licence map.
README

    git add -A
    git -c user.email=msrahmanadam@gmail.com -c user.name="Adam Munawar Rahman" \
        commit -m "deploy(l4): self-contained Riprap mirror"

    echo "[deploy] pushing $PERSONAL_BRANCH → $PERSONAL_REMOTE main ..."
    git push --force "$PERSONAL_REMOTE" "${PERSONAL_BRANCH}:main"
)

git worktree remove --force "$DEPLOY_TMP"
git branch -D "$PERSONAL_BRANCH" 2>/dev/null || true
echo "[deploy] done. Watch build at: ${PERSONAL_URL}"
