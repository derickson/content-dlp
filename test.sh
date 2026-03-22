#!/usr/bin/env bash
set -euo pipefail

SERVER_URL="http://localhost:7055"

echo "=== Health check ==="
curl -s "$SERVER_URL/health" | jq .

echo ""
echo "=== YouTube with forced transcription ==="
curl -s -X POST "$SERVER_URL/youtube" \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://www.youtube.com/watch?v=yLUKVHH3X8I", "transcript": true, "force": true}' | jq .
