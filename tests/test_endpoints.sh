#!/bin/bash
BASE_URL="http://localhost:8000"
AGENT_ID="c3115849-bc4d-4d63-a896-96ca8eb3b796"

echo "=== Enhanced Agent Debug Test ==="

echo -e "\n1. Test Echo Module (should work):"
ECHO_RESPONSE=$(curl -s -X POST "$BASE_URL/agent/$AGENT_ID/echo_module" \
  -H "Content-Type: application/json" \
  -d '{"message": "debug test"}')
echo $ECHO_RESPONSE | jq

ECHO_ID=$(echo $ECHO_RESPONSE | jq -r '.id')

echo -e "\n2. Wait and check echo result:"
sleep 3
curl -s "$BASE_URL/agents/$AGENT_ID/results/$ECHO_ID" | jq

echo -e "\n3. Test Ping with different targets:"
for TARGET in "8.8.8.8" "1.1.1.1" "127.0.0.1" "google.com"; do
  echo -e "\nTesting ping to: $TARGET"
  PING_RESPONSE=$(curl -s -X POST "$BASE_URL/agent/$AGENT_ID/ping_module" \
    -H "Content-Type: application/json" \
    -d "{\"host\": \"$TARGET\", \"count\": 2}")
  echo "Response: $PING_RESPONSE"
  
  PING_ID=$(echo $PING_RESPONSE | jq -r '.id')
  echo "Waiting 5 seconds for ping result..."
  sleep 5
  echo "Result:"
  curl -s "$BASE_URL/agents/$AGENT_ID/results/$PING_ID" | jq
done

echo -e "\n4. Check all recent results:"
curl -s "$BASE_URL/agents/$AGENT_ID/results" | jq

echo -e "\n5. Check module states:"
curl -s "$BASE_URL/modules/states" | jq

echo -e "\n6. Debug cache state:"
curl -s "$BASE_URL/debug/cache" | jq