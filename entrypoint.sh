#!/usr/bin/env sh
# Start Ollama daemon in the background, wait for it to be ready,
# then launch uvicorn on the HF Spaces default port.
set -e

ollama serve > /tmp/ollama.log 2>&1 &
OLLAMA_PID=$!

# Wait for Ollama to be reachable (up to 30 s)
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:11434/ > /dev/null 2>&1; then
    echo "[entrypoint] ollama up (pid $OLLAMA_PID)"
    break
  fi
  sleep 1
done

# Sanity check: Granite 4.1 model is present
ollama list | grep -q "granite4.1:3b" || {
  echo "[entrypoint] WARNING: granite4.1:3b not found in ollama; pulling..."
  ollama pull granite4.1:3b || true
}

exec uvicorn web.main:app --host 0.0.0.0 --port 7860 --log-level info
