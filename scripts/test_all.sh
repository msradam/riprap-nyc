#!/usr/bin/env bash
# Full Riprap test stack — every layer in one command.
#
#   1. Python unit            tests/                        backend logic
#   2. Vitest unit/integration web/sveltekit/tests/unit/     UI logic, no browser
#   3. UI ↔ backend diff       scripts/ui_scaffold_diff.py   live HTTP
#   4. Playwright real queries web/sveltekit/tests/e2e/      real browser + backend
#
# Layers 3 + 4 require a running uvicorn on :7860. The script starts
# one if absent and tears it down at exit. Layers 1 + 2 run offline.
#
# Usage:
#   scripts/test_all.sh                     # all four layers
#   scripts/test_all.sh --offline           # 1 + 2 only
#   scripts/test_all.sh --skip-e2e          # 1 + 2 + 3
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

PY=.venv/bin/python
OFFLINE=0
SKIP_E2E=0
for arg in "$@"; do
  case "$arg" in
    --offline)   OFFLINE=1;;
    --skip-e2e)  SKIP_E2E=1;;
  esac
done

step()   { printf '\n\033[1m▌ %s\033[0m\n' "$1"; }
ok()     { printf '       \033[32m✓ %s\033[0m\n' "$1"; }
err()    { printf '       \033[31m✗ %s\033[0m\n' "$1"; }

STARTED_UVICORN=0
cleanup() {
  if [[ $STARTED_UVICORN -eq 1 ]]; then
    pkill -f 'uvicorn web.main:app' 2>/dev/null || true
  fi
}
trap cleanup EXIT

fail=0

# ─── 1. Python unit tests ──────────────────────────────────────────
step "1/4  Python tests (tests/)"
if $PY -m pytest tests/test_deployment_routing.py tests/test_pebble_*.py tests/test_stones.py tests/test_burr*.py -q 2>&1 | tail -3; then
  ok "Python pass"
else
  err "Python fail"; fail=1
fi

# ─── 2. Vitest UI unit / integration ───────────────────────────────
step "2/4  Vitest UI (web/sveltekit/tests/unit/)"
if ( cd web/sveltekit && npm run test:unit --silent 2>&1 | tail -6 ); then
  ok "Vitest pass"
else
  err "Vitest fail"; fail=1
fi

if [[ $OFFLINE -eq 1 ]]; then
  step "3/4 + 4/4  Skipped (--offline)"
  [[ $fail -eq 0 ]] && echo -e "\n▌ \033[32mTEST STACK PASS (offline)\033[0m" || { echo -e "\n▌ \033[31mTEST STACK FAIL\033[0m"; exit 1; }
  exit 0
fi

# Ensure uvicorn is running for layers 3 + 4.
if ! curl -sf http://127.0.0.1:7860/api/deployment >/dev/null 2>&1; then
  step "[boot]  Starting uvicorn on :7860 (no_llm tier)"
  RIPRAP_RECONCILER_TIER=no_llm RIPRAP_HEAVY_SPECIALISTS=0 \
    $PY -m uvicorn web.main:app --host 127.0.0.1 --port 7860 --log-level warning \
    > /tmp/riprap_test.log 2>&1 &
  STARTED_UVICORN=1
  # Wait up to 3 minutes (NYC deployment cold-load is slow).
  for _ in $(seq 1 180); do
    if curl -sf http://127.0.0.1:7860/api/deployment >/dev/null 2>&1; then
      ok "uvicorn ready"
      break
    fi
    sleep 1
  done
  if ! curl -sf http://127.0.0.1:7860/api/deployment >/dev/null 2>&1; then
    err "uvicorn never came up — see /tmp/riprap_test.log"
    exit 1
  fi
fi

# ─── 3. UI ↔ backend scaffold diff ─────────────────────────────────
step "3/4  UI ↔ backend scaffold diff (live HTTP)"
if $PY scripts/ui_scaffold_diff.py 2>&1 | tail -3; then
  ok "Scaffold diff pass"
else
  err "Scaffold diff fail"; fail=1
fi

if [[ $SKIP_E2E -eq 1 ]]; then
  step "4/4  Skipped (--skip-e2e)"
  [[ $fail -eq 0 ]] && echo -e "\n▌ \033[32mTEST STACK PASS (no e2e)\033[0m" || { echo -e "\n▌ \033[31mTEST STACK FAIL\033[0m"; exit 1; }
  exit 0
fi

# ─── 4. Playwright real-query e2e ──────────────────────────────────
step "4/4  Playwright e2e (real browser, real backend)"
if ( cd web/sveltekit && npx playwright test --reporter=line 2>&1 | tail -15 ); then
  ok "Playwright pass"
else
  err "Playwright fail"; fail=1
fi

echo
if [[ $fail -eq 0 ]]; then
  echo -e "▌ \033[32mTEST STACK PASS\033[0m"
else
  echo -e "▌ \033[31mTEST STACK FAIL\033[0m"
  exit 1
fi
