#!/bin/sh
# Quick server start to sync Turso embedded replica locally
cd /home/filki/workspace/panstwa-miasta
.venv/bin/uvicorn src.panstwa_miasta.main:app --host 0.0.0.0 --port 8765 &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# Wait for lifespan + sync
sleep 12

# Quick health check
curl -s -o /dev/null -w "Healthz HTTP %{http_code}\n" http://localhost:8765/healthz

# Kill server
kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
echo "Server stopped"
