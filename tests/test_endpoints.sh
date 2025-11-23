#!/bin/bash

# Test script for Internet Measurement Network API endpoints
# Usage: ./test_endpoints.sh

set -e  # Exit on any error

BASE_URL="http://localhost:8000"
AGENT_ID=""
REQUEST_ID=""

echo "=== Internet Measurement Network API Endpoint Testing ==="
echo ""

# Check if server is running
echo "1. Checking if server is running..."
if curl -s $BASE_URL > /dev/null; then
    echo "✅ Server is running"
    echo ""
else
    echo "❌ Server is not responding"
    exit 1
fi

# Test basic health check endpoints
echo "2. Testing basic health check endpoints..."
echo "   Testing root endpoint..."
curl -s $BASE_URL | jq .
echo ""

echo "   Testing /agents endpoint..."
curl -s $BASE_URL/agents | jq .
echo ""

echo "   Testing /agents/alive endpoint..."
curl -s $BASE_URL/agents/alive | jq .
echo ""

echo "   Testing /agents/dead endpoint..."
curl -s $BASE_URL/agents/dead | jq .
echo ""

# Get an agent ID for further testing
echo "3. Getting agent ID for testing..."
AGENT_ID=$(curl -s $BASE_URL/agents | jq -r 'keys[0]')
if [ "$AGENT_ID" != "null" ] && [ -n "$AGENT_ID" ]; then
    echo "✅ Got agent ID: $AGENT_ID"
else
    echo "❌ Failed to get agent ID"
    exit 1
fi
echo ""

# Test agent-specific endpoints
echo "4. Testing agent-specific endpoints..."
echo "   Testing /agents/{agent_id} endpoint..."
curl -s $BASE_URL/agents/$AGENT_ID | jq .
echo ""

# Test module execution
echo "5. Testing module execution..."
echo "   Executing ping_module..."
RESPONSE=$(curl -s -X POST $BASE_URL/agent/$AGENT_ID/ping_module \
    -H "Content-Type: application/json" \
    -d '{"host": "8.8.8.8", "count": 3}')
    
echo "Response: $RESPONSE"
REQUEST_ID=$(echo $RESPONSE | jq -r '.id')
echo "Request ID: $REQUEST_ID"
echo ""

# Wait a moment for the task to complete
echo "   Waiting for module execution to complete..."
sleep 3
echo ""

# Test result endpoints
echo "6. Testing result endpoints..."
echo "   Testing /agents/{agent_id}/results endpoint..."
curl -s $BASE_URL/agents/$AGENT_ID/results | jq .
echo ""

if [ "$REQUEST_ID" != "null" ] && [ -n "$REQUEST_ID" ]; then
    echo "   Testing /agents/{agent_id}/results/{request_id} endpoint..."
    curl -s $BASE_URL/agents/$AGENT_ID/results/$REQUEST_ID | jq .
    echo ""
    
    echo "   Testing /agents/{agent_id}/results/list endpoint..."
    curl -s $BASE_URL/agents/$AGENT_ID/results/list | jq .
    echo ""
else
    echo "   Skipping specific result tests - no request ID available"
    echo ""
fi

# Test module state endpoints
echo "7. Testing module state endpoints..."
echo "   Testing /modules/states endpoint..."
curl -s $BASE_URL/modules/states | jq .
echo ""

if [ "$REQUEST_ID" != "null" ] && [ -n "$REQUEST_ID" ]; then
    echo "   Testing /modules/states/{request_id} endpoint..."
    curl -s $BASE_URL/modules/states/$REQUEST_ID | jq .
    echo ""
    
    echo "   Testing /modules/states/{request_id}/version endpoint..."
    curl -s $BASE_URL/modules/states/$REQUEST_ID/version | jq .
    echo ""
fi

echo "   Testing /modules/states/list/{agent_id}/{module_name} endpoint..."
curl -s $BASE_URL/modules/states/list/$AGENT_ID/ping_module | jq .
echo ""

# Test event endpoints
echo "8. Testing event endpoints..."
echo "   Testing /events endpoint..."
curl -s $BASE_URL/events | jq .
echo ""

echo "   Testing /events?limit=5 endpoint..."
curl -s "$BASE_URL/events?limit=5" | jq .
echo ""

# Test task endpoints (if we have a request ID)
echo "9. Testing task endpoints..."
if [ "$REQUEST_ID" != "null" ] && [ -n "$REQUEST_ID" ]; then
    echo "   Testing /tasks/{task_id} endpoint..."
    curl -s $BASE_URL/tasks/$REQUEST_ID | jq .
    echo ""
else
    echo "   Skipping task tests - no request ID available"
    echo ""
fi

echo "=== All endpoint tests completed ==="