#!/usr/bin/env bash
set -e

PORT=8001
cd "$(dirname "$0")"

PID=$(lsof -ti :$PORT 2>/dev/null || true)
if [ -n "$PID" ]; then
    kill -9 $PID
    sleep 1
fi

echo "Starting server on http://127.0.0.1:$PORT"
echo "Open that in your browser. Press Ctrl+C here when you're done to stop it."
python3 -m uvicorn api:app --port $PORT
