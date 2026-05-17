#!/usr/bin/env bash
# Runs the full UI test harness — three layers, no browser:
#
#   1. Python unit tests        — backend routing seal
#   2. Vitest unit tests        — cardAdapter renders the right pebbles
#                                 per manifest (the user-reported bug seal)
#   3. UI ↔ backend scaffold     — chip/scaffold/run alignment across cities
#      diff (live HTTP)            (requires a running uvicorn on :7860)
#
# Usage:
#   scripts/test_ui_harness.sh                 # all three layers
#   scripts/test_ui_harness.sh --skip-server   # 1 + 2 only (no uvicorn needed)
#
# Exit 0 iff every layer passes. Print is short and demo-safe.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

SKIP_SERVER=0
if [[ "${1:-}" == "--skip-server" ]]; then
  SKIP_SERVER=1
fi

PY=.venv/bin/python
fail=0

step() { printf '\n\033[1m▌ %s\033[0m\n' "$1"; }

step "1/3  Python routing tests (tests/test_deployment_routing.py)"
if $PY -m pytest tests/test_deployment_routing.py -q 2>&1 | tail -5; then
  echo "       PASS"
else
  echo "       FAIL"; fail=1
fi

step "2/3  Vitest cardAdapter (web/sveltekit/tests/unit)"
if ( cd web/sveltekit && npm run test:unit --silent 2>&1 | tail -8 ); then
  echo "       PASS"
else
  echo "       FAIL"; fail=1
fi

if [[ $SKIP_SERVER -eq 1 ]]; then
  step "3/3  UI ↔ backend diff — SKIPPED (--skip-server)"
else
  step "3/3  UI ↔ backend scaffold diff"
  if ! curl -sf http://127.0.0.1:7860/api/deployment >/dev/null 2>&1; then
    echo "       (no uvicorn on :7860; start it with:"
    echo "        RIPRAP_RECONCILER_TIER=no_llm RIPRAP_HEAVY_SPECIALISTS=0 \\"
    echo "          $PY -m uvicorn web.main:app --host 127.0.0.1 --port 7860)"
    echo "       SKIPPED"
  else
    if $PY scripts/ui_scaffold_diff.py 2>&1 | tail -25; then
      echo "       PASS"
    else
      echo "       FAIL"; fail=1
    fi
  fi
fi

echo
if [[ $fail -eq 0 ]]; then
  echo "▌ HARNESS PASS"
else
  echo "▌ HARNESS FAIL"
  exit 1
fi
