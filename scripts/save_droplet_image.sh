#!/usr/bin/env bash
# Riprap droplet image fallback — save the bootstrap droplet's
# riprap-models image to a portable tarball.
#
# Use this when the public-base Dockerfile (services/riprap-models/Dockerfile)
# can't be reproduced — e.g. when AMD's public ROCm release diverges from
# the bootstrap droplet's ABI in a way that breaks our specialists. The
# saved tarball is byte-identical to the running container's image, so
# `docker load` on a fresh droplet gives you the exact env that worked.
#
# Caveats:
# - Tarballs are huge (~15 GB compressed, ~35 GB raw)
# - Needs the droplet to still be alive (run BEFORE you destroy it)
# - Can't be uploaded to a public registry without redacting any
#   embedded auth tokens; recommend you scp it to backup storage
#
# Usage:
#   scripts/save_droplet_image.sh <droplet-ip> [out-dir]
#
# Default out-dir: ~/riprap-backups/
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <droplet-ip> [out-dir]" >&2
    exit 64
fi

DROPLET_IP="$1"
OUT_DIR="${2:-$HOME/riprap-backups}"
SSH_USER="${SSH_USER:-root}"
SSH_KEY_FLAG=""
if [ -n "${SSH_KEY:-}" ]; then SSH_KEY_FLAG="-i $SSH_KEY"; fi
SSH="ssh $SSH_KEY_FLAG -o StrictHostKeyChecking=accept-new ${SSH_USER}@${DROPLET_IP}"
SCP="scp $SSH_KEY_FLAG -o StrictHostKeyChecking=accept-new"

mkdir -p "$OUT_DIR"
STAMP=$(date -u +%Y%m%d-%H%M%S)
TAR="$OUT_DIR/riprap-droplet-base-${STAMP}.tar"

echo "==> 1. Commit running terramind container as image"
$SSH 'docker commit terramind riprap-droplet-base:latest'

echo "==> 2. Save image to droplet-local tarball"
$SSH "docker save riprap-droplet-base:latest -o /workspace/riprap-droplet-base.tar"
SIZE=$($SSH 'stat -c %s /workspace/riprap-droplet-base.tar')
echo "    droplet-local tarball: $SIZE bytes"

echo "==> 3. Compress (zstd preferred; gzip fallback)"
if $SSH 'command -v zstd > /dev/null'; then
    $SSH 'zstd -3 --rm /workspace/riprap-droplet-base.tar'
    REMOTE="/workspace/riprap-droplet-base.tar.zst"
else
    $SSH 'gzip /workspace/riprap-droplet-base.tar'
    REMOTE="/workspace/riprap-droplet-base.tar.gz"
fi
CSIZE=$($SSH "stat -c %s $REMOTE")
echo "    compressed: $CSIZE bytes ($(awk "BEGIN { printf \"%.1f\", $CSIZE/$SIZE*100 }")% of raw)"

echo "==> 4. scp to local: $TAR$(basename $REMOTE | sed 's|riprap-droplet-base.tar||')"
$SCP "${SSH_USER}@${DROPLET_IP}:${REMOTE}" "${TAR}$(echo $REMOTE | sed 's|.*\.tar||')"

echo "==> 5. Cleanup droplet tarball"
$SSH "rm -f $REMOTE"

ls -lh "${TAR}"*
echo
echo "Restore on a fresh droplet:"
echo "  scp ${TAR}* root@<new-ip>:/workspace/"
echo "  ssh root@<new-ip> 'zstd -d /workspace/riprap-droplet-base.tar.zst -o /tmp/img.tar && docker load -i /tmp/img.tar'"
echo "  Then docker run with the original device flags (see CLAUDE.md)."
