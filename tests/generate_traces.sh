#!/bin/bash

# Get active agent IDs
AGENT_IDS=$(curl -s localhost:8000/agents/alive | jq -r 'keys[]')
echo "Found active agents:"
echo "$AGENT_IDS"

# Select first agent for testing
AGENT_ID=$(echo "$AGENT_IDS" | head -1)
echo "Using agent ID: $AGENT_ID"

echo "===== Generating Traces for All Modules ====="

# 1. Trigger Ping Module
echo "1. Triggering Ping Module..."
PING_RESPONSE=$(curl -s -X POST "http://localhost:8000/agent/$AGENT_ID/ping_module" \
-H "Content-Type: application/json" \
-d '{"host": "8.8.8.8", "count": 3}')

echo "Ping response: $PING_RESPONSE"
PING_REQUEST_ID=$(echo "$PING_RESPONSE" | jq -r '.id')
echo "Ping request ID: $PING_REQUEST_ID"

# 2. Trigger Echo Module
echo "2. Triggering Echo Module..."
ECHO_RESPONSE=$(curl -s -X POST "http://localhost:8000/agent/$AGENT_ID/echo_module" \
-H "Content-Type: application/json" \
-d '{"message": "Test message for tracing"}')

echo "Echo response: $ECHO_RESPONSE"
ECHO_REQUEST_ID=$(echo "$ECHO_RESPONSE" | jq -r '.id')
echo "Echo request ID: $ECHO_REQUEST_ID"

# 3. Trigger Faulty Module (normal operation)
echo "3. Triggering Faulty Module (normal)..."
FAULTY_RESPONSE=$(curl -s -X POST "http://localhost:8000/agent/$AGENT_ID/faulty_module" \
-H "Content-Type: application/json" \
-d '{"message": "Normal test message"}')

echo "Faulty module response: $FAULTY_RESPONSE"
FAULTY_REQUEST_ID=$(echo "$FAULTY_RESPONSE" | jq -r '.id')
echo "Faulty request ID: $FAULTY_REQUEST_ID"

# 4. Trigger Faulty Module with delay
echo "4. Triggering Faulty Module with delay..."
FAULTY_DELAY_RESPONSE=$(curl -s -X POST "http://localhost:8000/agent/$AGENT_ID/faulty_module" \
-H "Content-Type: application/json" \
-d '{"message": "Delayed test message", "delay": 2}')

echo "Faulty delay response: $FAULTY_DELAY_RESPONSE"
FAULTY_DELAY_ID=$(echo "$FAULTY_DELAY_RESPONSE" | jq -r '.id')
echo "Faulty delay request ID: $FAULTY_DELAY_ID"

# Give some time for processing
echo "Waiting for module executions to complete..."
sleep 5

# 5. Check module states
echo "===== Checking Module States ====="
echo "Ping module state:"
curl -s "http://localhost:8000/modules/states/$PING_REQUEST_ID" | jq '.'

echo "Echo module state:"
curl -s "http://localhost:8000/modules/states/$ECHO_REQUEST_ID" | jq '.'

echo "Faulty module state (normal):"
curl -s "http://localhost:8000/modules/states/$FAULTY_REQUEST_ID" | jq '.'

echo "Faulty module state (delayed):"
curl -s "http://localhost:8000/modules/states/$FAULTY_DELAY_ID" | jq '.'

# 6. Check results
echo "===== Checking Results ====="
echo "Ping module result:"
curl -s "http://localhost:8000/agents/$AGENT_ID/results/$PING_REQUEST_ID" | jq '.'

echo "Echo module result:"
curl -s "http://localhost:8000/agents/$AGENT_ID/results/$ECHO_REQUEST_ID" | jq '.'

echo "Faulty module result (normal):"
curl -s "http://localhost:8000/agents/$AGENT_ID/results/$FAULTY_REQUEST_ID" | jq '.'

# 7. Trigger Faulty Module with crash to generate error traces
echo "===== Generating Error Traces ====="
echo "7. Triggering Faulty Module with crash..."
FAULTY_CRASH_RESPONSE=$(curl -s -X POST "http://localhost:8000/agent/$AGENT_ID/faulty_module" \
-H "Content-Type: application/json" \
-d '{"message": "Crash test message", "crash": true}')

echo "Faulty crash response: $FAULTY_CRASH_RESPONSE"
FAULTY_CRASH_ID=$(echo "$FAULTY_CRASH_RESPONSE" | jq -r '.id')
echo "Faulty crash request ID: $FAULTY_CRASH_ID"

# Give time for error processing
sleep 2

echo "Faulty module state (crashed):"
curl -s "http://localhost:8000/modules/states/$FAULTY_CRASH_ID" | jq '.'

# 8. Generate multiple heartbeat traces
echo "===== Generating Additional Heartbeat Traces ====="
echo "Triggering multiple heartbeat cycles..."
for i in {1..5}; do
    echo "Heartbeat cycle $i"
    sleep 5
done

echo "===== Trace Generation Complete ====="
echo "You can now check OpenSearch Dashboards for the generated traces."
echo "Service map should show communication between server and agents."
echo "Look for trace groups like:"
echo "  - nats.publish(agent.heartbeat_module)"
echo "  - nats.publish(agent.module.state)"
echo "  - nats.publish(agent.notif)"