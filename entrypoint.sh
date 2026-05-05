#!/usr/bin/env sh
# Start Ollama daemon in the background, wait for it to be ready,
# then launch uvicorn on the HF Spaces default port.
#
# HF Spaces locks down /tmp for unprivileged users — write logs to
# $HOME (which we own) instead.
set -e

LOG_FILE="$HOME/ollama.log"
ollama serve > "$LOG_FILE" 2>&1 &
OLLAMA_PID=$!

# Wait for Ollama to be reachable (up to 60 s — first start can be slow
# on a cold container with persistent storage being mounted)
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:11434/ > /dev/null 2>&1; then
    echo "[entrypoint] ollama up (pid $OLLAMA_PID) after ${i}s"
    break
  fi
  if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
    echo "[entrypoint] FATAL: ollama serve died. Last 40 lines of $LOG_FILE:"
    tail -40 "$LOG_FILE" || true
    exit 1
  fi
  sleep 1
done

if ! curl -sf http://127.0.0.1:11434/ > /dev/null 2>&1; then
  echo "[entrypoint] FATAL: ollama did not become ready within 60s"
  tail -40 "$LOG_FILE" || true
  exit 1
fi

# Sanity check: Granite 4.1 model is present (baked in during build)
if ! ollama list | grep -q "granite4.1:3b"; then
  echo "[entrypoint] WARNING: granite4.1:3b not found; pulling now (slow!)..."
  ollama pull granite4.1:3b || echo "[entrypoint] pull failed; reconciler will fail"
fi

ollama list

exec uvicorn web.main:app --host 0.0.0.0 --port 7860 --log-level info
