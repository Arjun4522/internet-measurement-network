#!/bin/bash

# Chaos Engineering Test Script for Internet Measurement Network
# Tests durability, idempotency, and consistency under failure conditions

set -euo pipefail

BASE_URL="http://localhost:8000"
AGENT_1_ID=""
AGENT_2_ID=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Verbosity flag
VERBOSE=true

echo -e "${BLUE}=== Internet Measurement Network Chaos Engineering Tests ===${NC}"
echo ""

# Function to print section headers
print_header() {
    echo -e "${BLUE}--- $1 ---${NC}"
}

# Function to print test results
print_result() {
    if [ "$1" = "PASS" ]; then
        echo -e "${GREEN}✓ PASS: $2${NC}"
    else
        echo -e "${RED}✗ FAIL: $2${NC}"
    fi
}

# Function to check if service is running
check_service() {
    local service_name=$1
    local container_name=$2
    
    if [ "$VERBOSE" = true ]; then
        echo "Checking if $service_name ($container_name) is running..."
    fi
    
    if docker ps | grep -q "$container_name"; then
        echo -e "${GREEN}✓ $service_name is running${NC}"
        return 0
    else
        echo -e "${RED}✗ $service_name is not running${NC}"
        return 1
    fi
}

# Function to restart a service
restart_service() {
    local service_name=$1
    local container_name=$2
    
    echo "Restarting $service_name ($container_name)..."
    if [ "$VERBOSE" = true ]; then
        echo "Executing: docker restart $container_name"
    fi
    docker restart "$container_name" > /dev/null
    echo "Waiting for $service_name to restart..."
    sleep 5
}

# Function to stop a service
stop_service() {
    local service_name=$1
    local container_name=$2
    
    echo "Stopping $service_name ($container_name)..."
    if [ "$VERBOSE" = true ]; then
        echo "Executing: docker stop $container_name"
    fi
    docker stop "$container_name" > /dev/null
    echo "Waiting for $service_name to stop..."
    sleep 2
}

# Function to start a service
start_service() {
    local service_name=$1
    local container_name=$2
    
    echo "Starting $service_name ($container_name)..."
    if [ "$VERBOSE" = true ]; then
        echo "Executing: docker start $container_name"
    fi
    docker start "$container_name" > /dev/null
    echo "Waiting for $service_name to start..."
    sleep 5
}

# Wait for system to stabilize
wait_for_system() {
    echo "Waiting for system to stabilize..."
    if [ "$VERBOSE" = true ]; then
        echo "Sleeping for 10 seconds to allow system stabilization..."
    fi
    sleep 10
    check_server_health 30
}

# Function to check if server is responding
check_server_health() {
    local timeout=${1:-10}
    local count=0
    
    echo "Checking server health at $BASE_URL..."
    if [ "$VERBOSE" = true ]; then
        echo "Will try for up to $timeout seconds"
    fi
    while [[ $count -lt $timeout ]]; do
        if curl -s "$BASE_URL/" >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Server is responding${NC}"
            if [ "$VERBOSE" = true ]; then
                echo "Server health check successful"
            fi
            return 0
        fi
        echo "Server not responding, waiting... ($((count+1))/$timeout)"
        if [ "$VERBOSE" = true ]; then
            echo "Executing health check: curl -s $BASE_URL/"
        fi
        sleep 1
        count=$((count+1))
    done
    
    echo -e "${RED}✗ Server is not responding after $timeout seconds${NC}"
    return 1
}

# Test 1: Basic System Health Check
print_header "TEST 1: SYSTEM HEALTH CHECK"
echo "Checking if all required services are running..."

SERVICES_OK=true

check_service "Server" "server" || SERVICES_OK=false
check_service "DBOS" "dbos" || SERVICES_OK=false
check_service "Agent 1" "agent_1" || SERVICES_OK=false
check_service "Agent 2" "agent_2" || SERVICES_OK=false

if [ "$SERVICES_OK" = false ]; then
    echo -e "${RED}Some services are not running. Cannot proceed with tests.${NC}"
    exit 1
fi

echo ""

# Get agent IDs
print_header "GETTING AGENT INFORMATION"
echo "Retrieving agent IDs..."

# Get all agent IDs and filter for only alive ones
if [ "$VERBOSE" = true ]; then
    echo "Fetching all agents from $BASE_URL/agents"
fi
ALL_AGENTS=$(curl -s $BASE_URL/agents)
if [ "$VERBOSE" = true ]; then
    echo "Raw agents response: $ALL_AGENTS"
fi
ALIVE_AGENT_IDS=()

# Parse the JSON to find alive agents
echo "Parsing agent data to find alive agents..."
while IFS= read -r id; do
    if [ "$id" != "null" ] && [ -n "$id" ]; then
        if [ "$VERBOSE" = true ]; then
            echo "Checking status for agent: $id"
        fi
        ALIVE_STATUS=$(echo "$ALL_AGENTS" | jq -r ".\"$id\".alive" 2>/dev/null)
        if [ "$ALIVE_STATUS" = "true" ]; then
            ALIVE_AGENT_IDS+=("$id")
            if [ "$VERBOSE" = true ]; then
                echo "Agent $id is alive"
            fi
        else
            if [ "$VERBOSE" = true ]; then
                echo "Agent $id is not alive"
            fi
        fi
    fi
done < <(echo "$ALL_AGENTS" | jq -r 'keys[]' 2>/dev/null)

# Check if we have at least 2 alive agents
echo "Found ${#ALIVE_AGENT_IDS[@]} alive agents"
if [ ${#ALIVE_AGENT_IDS[@]} -lt 2 ]; then
    echo -e "${RED}Need at least 2 alive agents for testing, found ${#ALIVE_AGENT_IDS[@]}${NC}"
    echo "All agents status:"
    echo "$ALL_AGENTS" | jq '.[] | {agent_id: .agent_id, alive: .alive, last_seen: .last_seen}'
    exit 1
fi

AGENT_1_ID="${ALIVE_AGENT_IDS[0]}"
AGENT_2_ID="${ALIVE_AGENT_IDS[1]}"

echo "Using alive Agent 1 ID: $AGENT_1_ID"
echo "Using alive Agent 2 ID: $AGENT_2_ID"
echo ""

# Test 2: Durability Test - Server Restart
print_header "TEST 2: DURABILITY - SERVER RESTART"
echo "Testing system resilience to server restarts..."

# Submit a task before restart
echo "Submitting test task to Agent 1 ($AGENT_1_ID)..."
if [ "$VERBOSE" = true ]; then
    echo "Executing: curl -s -X POST $BASE_URL/agent/$AGENT_1_ID/ping_module -H \"Content-Type: application/json\" -d '{\"host\": \"1.1.1.1\", \"count\": 2}'"
fi
RESPONSE=$(curl -s -X POST $BASE_URL/agent/$AGENT_1_ID/ping_module \
    -H "Content-Type: application/json" \
    -d '{"host": "1.1.1.1", "count": 2}')
    
echo "Raw response: $RESPONSE"
if [ "$VERBOSE" = true ]; then
    echo "Parsing response to extract request ID"
fi
REQUEST_ID=$(echo "$RESPONSE" | jq -r '.id' 2>/dev/null || echo "null")

if [ "$REQUEST_ID" = "null" ] || [ "$REQUEST_ID" = "" ]; then
    echo -e "${RED}Failed to submit test task${NC}"
    echo "Response was: $RESPONSE"
    # Try alternate parsing
    if [ "$VERBOSE" = true ]; then
        echo "Trying alternate parsing method for request ID"
    fi
    REQUEST_ID=$(echo "$RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    if [ -z "$REQUEST_ID" ]; then
        exit 1
    else
        echo "Parsed ID: $REQUEST_ID"
    fi
fi

echo "Task submitted with ID: $REQUEST_ID"

# Wait for task completion and verify initial storage
echo "Waiting for task to complete and verifying initial storage..."
if [ "$VERBOSE" = true ]; then
    echo "Sleeping for 8 seconds to allow task completion"
fi
sleep 8

echo "Checking initial result storage..."
if [ "$VERBOSE" = true ]; then
    echo "Fetching result from: $BASE_URL/agents/$AGENT_1_ID/results/$REQUEST_ID"
fi
INITIAL_RESULT=$(curl -s $BASE_URL/agents/$AGENT_1_ID/results/$REQUEST_ID 2>/dev/null)
if [ "$VERBOSE" = true ]; then
    echo "Initial result response: $INITIAL_RESULT"
fi
if echo "$INITIAL_RESULT" | jq -e .id >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Task result initially stored successfully${NC}"
    ADDRESS=$(echo "$INITIAL_RESULT" | jq -r '.address')
    RECEIVED=$(echo "$INITIAL_RESULT" | jq -r '.packets_received')
    SENT=$(echo "$INITIAL_RESULT" | jq -r '.packets_sent')
    echo "  Result details: $ADDRESS - $RECEIVED/$SENT packets received"
else
    echo -e "${YELLOW}⚠ Warning: Initial result not immediately available${NC}"
    echo "  Response: $INITIAL_RESULT"
fi

# Restart server
echo "Restarting server to test durability..."
stop_service "Server" "server"
if [ "$VERBOSE" = true ]; then
    echo "Sleeping for 3 seconds after stopping server"
fi
sleep 3
start_service "Server" "server"
wait_for_system
if [ "$VERBOSE" = true ]; then
    echo "Sleeping for 5 seconds after system stabilization"
fi
sleep 5

# Check if task result is still available
echo "Checking if task result persists after server restart..."
if [ "$VERBOSE" = true ]; then
    echo "Fetching result from: $BASE_URL/agents/$AGENT_1_ID/results/$REQUEST_ID"
fi
RETRIEVED_RESULT=$(curl -s $BASE_URL/agents/$AGENT_1_ID/results/$REQUEST_ID 2>/dev/null)
if [ "$VERBOSE" = true ]; then
    echo "Post-restart result response: $RETRIEVED_RESULT"
fi
if echo "$RETRIEVED_RESULT" | jq -e .id >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Task result successfully retrieved after server restart${NC}"
    ADDRESS=$(echo "$RETRIEVED_RESULT" | jq -r '.address')
    RECEIVED=$(echo "$RETRIEVED_RESULT" | jq -r '.packets_received')
    SENT=$(echo "$RETRIEVED_RESULT" | jq -r '.packets_sent')
    echo "  Retrieved details: $ADDRESS - $RECEIVED/$SENT packets received"
    print_result "PASS" "Task result persisted through server restart"
else
    echo -e "${RED}✗ Task result lost during server restart${NC}"
    echo "Debug info:"
    echo "  Request ID: $REQUEST_ID"
    echo "  Agent ID: $AGENT_1_ID"
    echo "  Initial result: $(echo "$INITIAL_RESULT" | jq -r '.id' 2>/dev/null || echo 'None')"
    echo "  Post-restart response: $RETRIEVED_RESULT"
    print_result "FAIL" "Task result lost during server restart"
fi

echo ""

# Test 3: Idempotency Test
print_header "TEST 3: IDEMPOTENCY TEST"
echo "Testing idempotent execution of the same request..."

# Submit the same task twice with untracked flag
echo "Submitting identical tasks with untracked flag..."

echo "Submitting first task..."
if [ "$VERBOSE" = true ]; then
    echo "Executing: curl -s -X POST \"$BASE_URL/agent/$AGENT_1_ID/ping_module?untracked=true\" -H \"Content-Type: application/json\" -d '{\"host\": \"8.8.4.4\", \"count\": 1}'"
fi
RESPONSE1=$(curl -s -X POST "$BASE_URL/agent/$AGENT_1_ID/ping_module?untracked=true" \
    -H "Content-Type: application/json" \
    -d '{"host": "8.8.4.4", "count": 1}' 2>/dev/null)
if [ "$VERBOSE" = true ]; then
    echo "First response: $RESPONSE1"
fi

echo "Submitting second identical task..."
if [ "$VERBOSE" = true ]; then
    echo "Executing: curl -s -X POST \"$BASE_URL/agent/$AGENT_1_ID/ping_module?untracked=true\" -H \"Content-Type: application/json\" -d '{\"host\": \"8.8.4.4\", \"count\": 1}'"
fi
RESPONSE2=$(curl -s -X POST "$BASE_URL/agent/$AGENT_1_ID/ping_module?untracked=true" \
    -H "Content-Type: application/json" \
    -d '{"host": "8.8.4.4", "count": 1}' 2>/dev/null)
if [ "$VERBOSE" = true ]; then
    echo "Second response: $RESPONSE2"
fi

echo "Comparing responses..."
if [ "$RESPONSE1" = "$RESPONSE2" ]; then
    print_result "PASS" "Idempotent requests produce consistent responses"
else
    print_result "FAIL" "Idempotent requests produce inconsistent responses"
fi

echo ""

# Test 4: Consistency Test - Multiple Agents
print_header "TEST 4: CONSISTENCY - MULTIPLE AGENTS"
echo "Testing consistency across multiple agents..."

# Submit tasks to both agents
echo "Submitting tasks to both agents simultaneously..."

echo "Submitting task to Agent 1 ($AGENT_1_ID)..."
if [ "$VERBOSE" = true ]; then
    echo "Executing: curl -s -X POST $BASE_URL/agent/$AGENT_1_ID/ping_module -H \"Content-Type: application/json\" -d '{\"host\": \"1.0.0.1\", \"count\": 1}'"
fi
TASK1_RESPONSE=$(curl -s -X POST $BASE_URL/agent/$AGENT_1_ID/ping_module \
    -H "Content-Type: application/json" \
    -d '{"host": "1.0.0.1", "count": 1}' 2>/dev/null)
if [ "$VERBOSE" = true ]; then
    echo "Agent 1 response: $TASK1_RESPONSE"
fi
    
echo "Submitting task to Agent 2 ($AGENT_2_ID)..."
if [ "$VERBOSE" = true ]; then
    echo "Executing: curl -s -X POST $BASE_URL/agent/$AGENT_2_ID/ping_module -H \"Content-Type: application/json\" -d '{\"host\": \"1.0.0.1\", \"count\": 1}'"
fi
TASK2_RESPONSE=$(curl -s -X POST $BASE_URL/agent/$AGENT_2_ID/ping_module \
    -H "Content-Type: application/json" \
    -d '{"host": "1.0.0.1", "count": 1}' 2>/dev/null)
if [ "$VERBOSE" = true ]; then
    echo "Agent 2 response: $TASK2_RESPONSE"
fi

TASK1_ID=$(echo $TASK1_RESPONSE | jq -r '.id')
TASK2_ID=$(echo $TASK2_RESPONSE | jq -r '.id')

echo "Task 1 ID: $TASK1_ID (Agent 1)"
echo "Task 2 ID: $TASK2_ID (Agent 2)"

# Wait for completion
echo "Waiting for tasks to complete..."
if [ "$VERBOSE" = true ]; then
    echo "Sleeping for 5 seconds to allow task completion"
fi
sleep 5

# Check results from both agents
echo "Checking results from both agents..."

echo "Fetching result for Task 1 from Agent 1..."
if [ "$VERBOSE" = true ]; then
    echo "Executing: curl -s $BASE_URL/agents/$AGENT_1_ID/results/$TASK1_ID"
fi
RESULT1=$(curl -s $BASE_URL/agents/$AGENT_1_ID/results/$TASK1_ID 2>/dev/null)
if [ "$VERBOSE" = true ]; then
    echo "Result 1: $RESULT1"
fi

echo "Fetching result for Task 2 from Agent 2..."
if [ "$VERBOSE" = true ]; then
    echo "Executing: curl -s $BASE_URL/agents/$AGENT_2_ID/results/$TASK2_ID"
fi
RESULT2=$(curl -s $BASE_URL/agents/$AGENT_2_ID/results/$TASK2_ID 2>/dev/null)
if [ "$VERBOSE" = true ]; then
    echo "Result 2: $RESULT2"
fi

if echo "$RESULT1" | jq -e .id >/dev/null 2>&1 && echo "$RESULT2" | jq -e .id >/dev/null 2>&1; then
    print_result "PASS" "Both agents processed tasks successfully"
else
    print_result "FAIL" "One or both agents failed to process tasks"
fi

echo ""

# Test 5: DBOS Resilience Test
print_header "TEST 5: DBOS RESILIENCE TEST"
echo "Testing system behavior during DBOS service interruption..."

# Submit a task
echo "Submitting task before DBOS restart..."
if [ "$VERBOSE" = true ]; then
    echo "Executing: curl -s -X POST $BASE_URL/agent/$AGENT_1_ID/ping_module -H \"Content-Type: application/json\" -d '{\"host\": \"9.9.9.9\", \"count\": 1}'"
fi
RESPONSE=$(curl -s -X POST $BASE_URL/agent/$AGENT_1_ID/ping_module \
    -H "Content-Type: application/json" \
    -d '{"host": "9.9.9.9", "count": 1}' 2>/dev/null)
if [ "$VERBOSE" = true ]; then
    echo "Task submission response: $RESPONSE"
fi
    
REQUEST_ID=$(echo $RESPONSE | jq -r '.id')
echo "Task submitted with ID: $REQUEST_ID"

# Wait for task completion
echo "Waiting for task to complete..."
if [ "$VERBOSE" = true ]; then
    echo "Sleeping for 5 seconds to allow task completion"
fi
sleep 5

# Verify initial storage
echo "Verifying initial result storage..."
if [ "$VERBOSE" = true ]; then
    echo "Fetching initial result from: $BASE_URL/agents/$AGENT_1_ID/results/$REQUEST_ID"
fi
INITIAL_RESULT=$(curl -s $BASE_URL/agents/$AGENT_1_ID/results/$REQUEST_ID 2>/dev/null)
if [ "$VERBOSE" = true ]; then
    echo "Initial result: $INITIAL_RESULT"
fi
if echo "$INITIAL_RESULT" | jq -e .id >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Task result initially stored successfully${NC}"
else
    echo -e "${YELLOW}⚠ Warning: Initial result not immediately available${NC}"
fi

# Restart DBOS service
echo "Restarting DBOS service..."
stop_service "DBOS" "dbos"
if [ "$VERBOSE" = true ]; then
    echo "Sleeping for 3 seconds after stopping DBOS"
fi
sleep 3
start_service "DBOS" "dbos"
wait_for_system

# Check if system recovers and result is still available
echo "Checking system recovery and result persistence after DBOS restart..."
if [ "$VERBOSE" = true ]; then
    echo "Executing health check: curl -s $BASE_URL/"
fi
HEALTH_CHECK=$(curl -s $BASE_URL/ 2>/dev/null)
if [ "$VERBOSE" = true ]; then
    echo "Health check response: $HEALTH_CHECK"
fi
if echo "$HEALTH_CHECK" | jq -e .status >/dev/null 2>&1; then
    echo -e "${GREEN}✓ System API is responsive${NC}"
    
    # Check if result is still available
    echo "Checking if task result is still accessible..."
    if [ "$VERBOSE" = true ]; then
        echo "Fetching result from: $BASE_URL/agents/$AGENT_1_ID/results/$REQUEST_ID"
    fi
    RETRIEVED_RESULT=$(curl -s $BASE_URL/agents/$AGENT_1_ID/results/$REQUEST_ID 2>/dev/null)
    if [ "$VERBOSE" = true ]; then
        echo "Post-restart result: $RETRIEVED_RESULT"
    fi
    if echo "$RETRIEVED_RESULT" | jq -e .id >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Task result still accessible after DBOS restart${NC}"
        print_result "PASS" "System recovered and data persisted after DBOS restart"
    else
        echo -e "${YELLOW}⚠ System recovered but result not accessible${NC}"
        echo "  Initial result: $(echo "$INITIAL_RESULT" | jq -r '.id' 2>/dev/null || echo 'None')"
        echo "  Post-restart result: $RETRIEVED_RESULT"
        print_result "PARTIAL" "System recovered but data access issue"
    fi
else
    echo -e "${RED}✗ System failed to recover after DBOS restart${NC}"
    print_result "FAIL" "System failed to recover after DBOS restart"
fi

echo ""

# Test 6: Agent Failure Recovery
print_header "TEST 6: AGENT FAILURE RECOVERY"
echo "Testing agent recovery capabilities..."

# Stop one agent
echo "Stopping Agent 1..."
stop_service "Agent 1" "agent_1"
if [ "$VERBOSE" = true ]; then
    echo "Sleeping for 3 seconds after stopping agent"
fi
sleep 3

# Try to submit task to stopped agent
echo "Attempting to submit task to stopped agent..."
if [ "$VERBOSE" = true ]; then
    echo "Executing: curl -s -w \"%{http_code}\" -X POST $BASE_URL/agent/$AGENT_1_ID/ping_module -H \"Content-Type: application/json\" -d '{\"host\": \"8.8.8.8\", \"count\": 1}'"
fi
ERROR_RESPONSE=$(curl -s -w "%{http_code}" -X POST $BASE_URL/agent/$AGENT_1_ID/ping_module \
    -H "Content-Type: application/json" \
    -d '{"host": "8.8.8.8", "count": 1}' 2>/dev/null)
if [ "$VERBOSE" = true ]; then
    echo "Response from stopped agent: $ERROR_RESPONSE"
fi

# Restart agent
echo "Restarting Agent 1..."
start_service "Agent 1" "agent_1"
wait_for_system

# Verify agent is back online
echo "Verifying agent is back online..."
# Wait a moment for the agent to register as alive
if [ "$VERBOSE" = true ]; then
    echo "Sleeping for 5 seconds to allow agent registration"
fi
sleep 5
if [ "$VERBOSE" = true ]; then
    echo "Fetching agent status from: $BASE_URL/agents/$AGENT_1_ID"
fi
AGENT_STATUS=$(curl -s $BASE_URL/agents/$AGENT_1_ID 2>/dev/null)
if [ "$VERBOSE" = true ]; then
    echo "Agent status response: $AGENT_STATUS"
fi
if echo "$AGENT_STATUS" | jq -e .alive >/dev/null 2>&1; then
    ALIVE=$(echo "$AGENT_STATUS" | jq -r '.alive')
    if [ "$ALIVE" = "true" ]; then
        print_result "PASS" "Agent successfully recovered and is alive"
    else
        print_result "FAIL" "Agent recovered but is not marked as alive"
        echo "Agent status: $AGENT_STATUS"
    fi
else
    print_result "FAIL" "Could not verify agent status after recovery"
    echo "Agent status response: $AGENT_STATUS"
fi

echo ""

# Final Report
print_header "CHAOS ENGINEERING TEST SUMMARY"
echo "All chaos engineering tests completed."
echo ""
echo "Tests performed:"
echo "  1. System Health Check - Verified all services are running"
echo "  2. Durability Test - Checked persistence through server restart"
echo "  3. Idempotency Test - Ensured consistent responses for identical requests"
echo "  4. Consistency Test - Validated multi-agent processing"
echo "  5. DBOS Resilience - Tested recovery from DBOS service interruption"
echo "  6. Agent Recovery - Verified agent failure and recovery process"
echo ""
echo "These tests validate the system's ability to maintain:"
echo "  • Durability: Data persistence through service restarts"
echo "  • Idempotency: Consistent behavior for repeated operations"
echo "  • Consistency: Reliable processing across multiple agents"
echo "  • Resilience: Recovery from service interruptions"
echo ""
if [ "$VERBOSE" = true ]; then
    echo "Verbosity was enabled for this test run. All major steps were logged."
    echo ""
fi

echo -e "${BLUE}=== Test Suite Completed ===${NC}"