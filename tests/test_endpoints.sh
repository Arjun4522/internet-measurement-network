#!/bin/bash

# Test all endpoints script
echo "=== Testing Internet Measurement Network Endpoints ==="

# Function to test HTTP endpoints
test_http() {
    local url=$1
    local name=$2
    echo "Testing $name ($url)..."
    if curl -s --connect-timeout 5 --max-time 10 "$url" > /dev/null; then
        echo "✅ $name: SUCCESS"
    else
        echo "❌ $name: FAILED"
    fi
    echo ""
}

# Function to test NATS monitoring endpoints
test_nats_monitoring() {
    local endpoint=$1
    local name=$2
    echo "Testing NATS $name endpoint..."
    if curl -s --connect-timeout 5 --max-time 10 "http://localhost:8222$endpoint" > /dev/null; then
        echo "✅ NATS $name: SUCCESS"
    else
        echo "❌ NATS $name: FAILED"
    fi
    echo ""
}

echo "1. Testing Web UI Endpoints:"
echo "=========================="
test_http "http://localhost:31312" "NUI Dashboard"
test_http "http://localhost:9222" "NATS UI Dashboard"

echo "2. Testing Agent API Endpoints:"
echo "============================="
test_http "http://localhost:9101/metrics" "Agent 1 Metrics"
test_http "http://localhost:9102/metrics" "Agent 2 Metrics"

echo "3. Testing NATS Monitoring Endpoints:"
echo "===================================="
test_nats_monitoring "/" "Root"
test_nats_monitoring "/varz" "Variables"
test_nats_monitoring "/connz" "Connections"
test_nats_monitoring "/routez" "Routes"
test_nats_monitoring "/subsz" "Subscriptions"

echo "4. Testing NATS Connectivity:"
echo "============================"
if command -v nats &> /dev/null; then
    echo "Testing NATS connection..."
    if nats server info --server localhost:4222 > /dev/null 2>&1; then
        echo "✅ NATS Client Connection: SUCCESS"
    else
        echo "❌ NATS Client Connection: FAILED"
    fi
else
    echo "⚠️  NATS CLI client not found. Install with: 'go install github.com/nats-io/natscli/nats@latest'"
fi

echo ""
echo "=== Testing Complete ==="