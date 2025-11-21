# Internet-Measurement-Network

## 🏗️ Architecture

### Overview

The Internet Measurement Network (IMN) is a distributed system for performing network measurements using autonomous agents. The system uses NATS as a messaging backbone for communication between components, with OpenTelemetry for observability data collection and OpenSearch for data storage and visualization.

The architecture consists of several key components:

1. **Agents**: Autonomous measurement nodes that perform network tests
2. **Server**: Central coordination service that manages agents
3. **NATS**: Message broker for communication between components
4. **OpenTelemetry Collector**: Aggregates and processes observability data
5. **Data Prepper**: Transforms and routes telemetry data to OpenSearch
6. **OpenSearch**: Storage and search engine for telemetry data
7. **OpenSearch Dashboards**: Visualization interface for telemetry data

### Component Details

#### Agents (`src/aiori_agent/`)
Autonomous measurement nodes that can dynamically load modules to perform various network tests. Key features include:
- Dynamic module loading with hot-reloading capabilities
- NATS integration for communication
- OpenTelemetry instrumentation for observability
- Crash recovery and error handling

Each agent has:
- A unique ID for identification
- Multiple modules that can be loaded/unloaded dynamically
- Input/output/error subjects for communication
- Heartbeat mechanism for health monitoring

#### Server (`server/`)
Central coordination service that:
- Maintains a registry of active agents
- Receives heartbeats from agents
- Provides REST API for querying agent status
- Routes measurement requests to appropriate agents
- Validates measurement requests against module schemas
- Captures and stores module execution results
- Provides REST API for retrieving detailed module results

#### NATS (`docker-compose.yml`)
Message broker that serves as the communication backbone:
- Provides pub/sub messaging for all components
- Handles agent-to-server and server-to-agent communication
- Monitors agent health through heartbeat messages
- Enables scalable, decoupled architecture

#### OpenTelemetry Collector (`otlp/otel-collector-config.yaml`)
Aggregates and processes observability data:
- Receives traces, logs, and metrics from agents and server
- Processes and batches telemetry data
- Routes data to appropriate backends
- Provides debugging output for development

#### Data Prepper (`docker/pipelines.yaml`)
Transforms and routes telemetry data:
- Receives OTLP data from OpenTelemetry Collector
- Processes traces, logs, and metrics separately
- Stores data in appropriate OpenSearch indices
- Generates service maps from trace data

#### OpenSearch (`docker-compose.yml`)
Storage and search engine for telemetry data:
- Stores traces in multiple formats for different use cases
- Stores logs with daily indexing
- Stores metrics with daily indexing
- Provides search and aggregation capabilities

#### OpenSearch Dashboards (`docker-compose.yml`)
Visualization interface:
- Provides GUI for viewing telemetry data
- Enables creation of custom dashboards
- Allows exploration of stored data

## 📊 Data Flow

1. **Agent Registration**:
   - Agents start and send heartbeat messages to `agent.heartbeat_module` subject
   - Server receives heartbeats and maintains agent registry
   - Agents are marked alive/dead based on heartbeat timing

2. **Measurement Request**:
   - Client sends request to server API endpoint `/agent/{agent_id}/{module_name}`
   - Server validates request against module schema
   - Server publishes request to appropriate NATS subject
   - Agent receives request on its input subject

3. **Measurement Execution**:
   - Agent executes measurement using loaded module
   - Module performs network test (ping, etc.)
   - Results are processed and formatted

4. **Result Reporting**:
   - Agent publishes results to output subject
   - Server captures and stores results in memory
   - Errors are published to error subject
   - OpenTelemetry data is sent to collector

5. **Data Processing**:
   - OpenTelemetry Collector receives observability data
   - Data is processed and batched
   - Data is forwarded to Data Prepper

6. **Data Storage**:
   - Data Prepper transforms data for storage
   - Data is stored in appropriate OpenSearch indices
   - Service maps are generated from trace data

7. **Data Visualization**:
   - OpenSearch Dashboards accesses stored data
   - Users create visualizations and dashboards
   - Metrics, logs, and traces are viewable

## 🔍 Trace Organization in OpenSearch

Currently, traces are organized by agent-specific subjects rather than by module names:

- **Heartbeat traces**: Use consistent subject `agent.heartbeat_module` across all agents
- **Module traces**: Use agent-specific subjects like `agent.{agent_id}.in` and `agent.{agent_id}.out`

This means:
- Heartbeat traces are easily searchable by module name
- Module traces are only searchable by agent-specific subject names
- Service maps show communication patterns but are organized by agent IDs rather than module types

## 🐳 Docker Services

| Service | Image | Ports | Purpose |
|---------|-------|-------|---------|
| `nats` | `nats:latest` | 4222, 8222 | Core messaging bus |
| `otel-collector` | `otel/opentelemetry-collector-contrib:0.92.0` | 5081, 4317, 4318, 8888 | Telemetry collection and processing |
| `opensearch` | `opensearchproject/opensearch:2.11.0` | 9200, 9600 | Data storage and search |
| `opensearch-dashboards` | `opensearchproject/opensearch-dashboards:2.11.0` | 5601 | Data visualization |
| `data-prepper` | `opensearchproject/data-prepper:2.12.0` | 21891, 21892, 21893, 4900 | Data transformation and routing |
| `server` | Custom build | 8000 | Agent coordination and API |
| `agent_1` | Custom build | 9101 | Measurement agent 1 |
| `agent_2` | Custom build | 9102 | Measurement agent 2 |

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.12+ (for local development)

### Running the Full Stack

1. **Start the complete system:**
   ```bash
   docker-compose up
   ```

2. **Access the services:**
   - **NATS Server:** `localhost:4222` (client connections)
   - **NATS Monitoring:** `localhost:8222` (metrics)
   - **NATS UI Dashboard:** `localhost:9222` (web interface)
   - **Agent 1 API:** `localhost:9101` (metrics/control)
   - **Agent 2 API:** `localhost:9102` (metrics/control)

### Running Agents Locally (Development)

1. **Install dependencies:**
   ```bash
   pip install -r agent/requirements.txt
   ```

2. **Ensure NATS server is running:**
   ```bash
   nats-server -n newton -m 8222 -DVV
   ```

3. **Start an agent:**
   ```bash
   python -m agent start
   ```

## 🧪 Comprehensive Testing Guide

### Prerequisites
Before testing, ensure all services are running:
```bash
# Start the complete system
docker-compose up -d

# Wait for services to initialize (30-60 seconds)
sleep 30

# Verify services are running
docker-compose ps
```

### 1. Verify System Health

#### Check Server Status
```bash
# Check if server is responsive
curl -s localhost:8000/ | jq .

# Expected response:
# {
#   "status": "ok",
#   "total_agents": 2,
#   "alive_agents": 2
# }
```

#### List Available Agents
```bash
# Get list of alive agents and their IDs
curl -s localhost:8000/agents/alive | jq 'keys[]'

# Example output:
# "a4cd3d41-d26d-40fb-874d-347561fe8ef3"
# "e36bfca1-6607-414b-b52e-1c3b231bd71c"
```

### 2. Module Testing Procedures

#### Ping Module (Network Connectivity Testing)
```bash
# Trigger ping module
AGENT_ID="a4cd3d41-d26d-40fb-874d-347561fe8ef3"
curl -X POST "http://localhost:8000/agent/$AGENT_ID/ping_module" \
-H "Content-Type: application/json" \
-d '{"host": "8.8.8.8", "count": 4}'

# Check result and state
REQUEST_ID=$(curl -s -X POST "http://localhost:8000/agent/$AGENT_ID/ping_module" \
-H "Content-Type: application/json" \
-d '{"host": "8.8.8.8", "count": 4}' | jq -r '.id')

# Retrieve detailed results
curl -s "http://localhost:8000/agents/$AGENT_ID/results/$REQUEST_ID" | jq .

# Monitor execution state
curl -s "http://localhost:8000/modules/states/$REQUEST_ID" | jq .

# Expected result format:
# {
#   "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
#   "address": "8.8.8.8",
#   "rtts": [12.34, 11.56, 13.78, 12.91],
#   "packets_received": 4,
#   "packets_sent": 4
# }
```

#### Echo Module (Message Testing)
```bash
# Trigger echo module
AGENT_ID="a4cd3d41-d26d-40fb-874d-347561fe8ef3"
curl -X POST "http://localhost:8000/agent/$AGENT_ID/echo_module" \
-H "Content-Type: application/json" \
-d '{"message": "Hello World Test"}'

# Check result and state
REQUEST_ID=$(curl -s -X POST "http://localhost:8000/agent/$AGENT_ID/echo_module" \
-H "Content-Type: application/json" \
-d '{"message": "Hello World Test"}' | jq -r '.id')

# Retrieve detailed results
curl -s "http://localhost:8000/agents/$AGENT_ID/results/$REQUEST_ID" | jq .

# Monitor execution state
curl -s "http://localhost:8000/modules/states/$REQUEST_ID" | jq .

# Expected result format:
# {
#   "message": "Hello World Test",
#   "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
#   "processed_at": 1234567890.123,
#   "from_module": "working_module"
# }
```

#### Faulty Module (Error Handling Testing)
```bash
# Normal operation test
AGENT_ID="a4cd3d41-d26d-40fb-874d-347561fe8ef3"
curl -X POST "http://localhost:8000/agent/$AGENT_ID/faulty_module" \
-H "Content-Type: application/json" \
-d '{"message": "Normal Test"}'

# Check successful execution
REQUEST_ID=$(curl -s -X POST "http://localhost:8000/agent/$AGENT_ID/faulty_module" \
-H "Content-Type: application/json" \
-d '{"message": "Normal Test"}' | jq -r '.id')

curl -s "http://localhost:8000/agents/$AGENT_ID/results/$REQUEST_ID" | jq .
curl -s "http://localhost:8000/modules/states/$REQUEST_ID" | jq .

# Delay simulation test
REQUEST_ID_DELAY=$(curl -s -X POST "http://localhost:8000/agent/$AGENT_ID/faulty_module" \
-H "Content-Type: application/json" \
-d '{"message": "Delay Test", "delay": 3}' | jq -r '.id')

# Check state during processing
curl -s "http://localhost:8000/modules/states/$REQUEST_ID_DELAY" | jq .

# Error simulation test
REQUEST_ID_ERROR=$(curl -s -X POST "http://localhost:8000/agent/$AGENT_ID/faulty_module" \
-H "Content-Type: application/json" \
-d '{"message": "Error Test", "crash": true}' | jq -r '.id')

# Check error state
curl -s "http://localhost:8000/modules/states/$REQUEST_ID_ERROR" | jq .

# Expected error state:
# {
#   "agent_id": "a4cd3d41-d26d-40fb-874d-347561fe8ef3",
#   "module_name": "faulty_module",
#   "state": "error",
#   "timestamp": "2023-01-01T12:00:00Z",
#   "error_message": "Intentional crash triggered.",
#   "details": {
#     "action": "request_failed"
#   }
# }
```

### 3. Advanced Testing Scenarios

#### Bulk Testing Script
```bash
#!/bin/bash
# bulk_test.sh - Test multiple modules sequentially

AGENT_ID="a4cd3d41-d26d-40fb-874d-347561fe8ef3"

echo "=== Bulk Module Testing ==="

# Test 1: Ping Module
echo "Testing Ping Module..."
PING_ID=$(curl -s -X POST "http://localhost:8000/agent/$AGENT_ID/ping_module" \
-H "Content-Type: application/json" \
-d '{"host": "1.1.1.1", "count": 3}' | jq -r '.id')
sleep 2
curl -s "http://localhost:8000/modules/states/$PING_ID" | jq '.state'

# Test 2: Echo Module
echo "Testing Echo Module..."
ECHO_ID=$(curl -s -X POST "http://localhost:8000/agent/$AGENT_ID/echo_module" \
-H "Content-Type: application/json" \
-d '{"message": "Bulk Test"}' | jq -r '.id')
sleep 1
curl -s "http://localhost:8000/modules/states/$ECHO_ID" | jq '.state'

# Test 3: Faulty Module
echo "Testing Faulty Module..."
FAULTY_ID=$(curl -s -X POST "http://localhost:8000/agent/$AGENT_ID/faulty_module" \
-H "Content-Type: application/json" \
-d '{"message": "Bulk Test"}' | jq -r '.id')
sleep 1
curl -s "http://localhost:8000/modules/states/$FAULTY_ID" | jq '.state'

echo "=== Test Results ==="
echo "Ping: $(curl -s "http://localhost:8000/modules/states/$PING_ID" | jq -r '.state')"
echo "Echo: $(curl -s "http://localhost:8000/modules/states/$ECHO_ID" | jq -r '.state')"
echo "Faulty: $(curl -s "http://localhost:8000/modules/states/$FAULTY_ID" | jq -r '.state')"
```

#### Concurrent Testing
```bash
# Test multiple modules simultaneously
AGENT_ID="a4cd3d41-d26d-40fb-874d-347561fe8ef3"

# Start all tests concurrently
curl -X POST "http://localhost:8000/agent/$AGENT_ID/ping_module" \
-H "Content-Type: application/json" \
-d '{"host": "8.8.8.8", "count": 2}' &

curl -X POST "http://localhost:8000/agent/$AGENT_ID/echo_module" \
-H "Content-Type: application/json" \
-d '{"message": "Concurrent Test"}' &

curl -X POST "http://localhost:8000/agent/$AGENT_ID/faulty_module" \
-H "Content-Type: application/json" \
-d '{"message": "Concurrent Test"}' &

wait  # Wait for all background jobs to complete
```

## 📥 Retrieving Module Results

The server now automatically captures and stores detailed results from module executions. Instead of only receiving a generic success message, you can now retrieve the actual metrics and data from each module execution.

### New API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /agents/{agent_id}/results` | GET | Get all results for a specific agent |
| `GET /agents/{agent_id}/results/{request_id}` | GET | Get specific result by request ID |
| `DELETE /agents/{agent_id}/results/{request_id}` | DELETE | Delete a specific result |

### Example Usage

#### Ping Module Results
When you trigger a ping command:
```bash
# Trigger ping and save the request ID
RESPONSE=$(curl -s -X POST "http://localhost:8000/agent/{agent_id}/ping_module" \
-H "Content-Type: application/json" \
-d '{"host": "8.8.8.8", "count": 4}')

REQUEST_ID=$(echo $RESPONSE | jq -r '.id')
```

You can then retrieve the detailed results:
```bash
# Get the specific result
curl -s "http://localhost:8000/agents/{agent_id}/results/$REQUEST_ID" | jq .

# Example response:
{
  "id": "06cd58b9-41bb-4fe2-a280-9d25f6c81a5f",
  "address": "8.8.8.8",
  "rtts": [43.98, 41.23, 42.67, 44.12],
  "packets_received": 4,
  "packets_sent": 4
}
```

#### Result Storage
- Results are stored in-memory on the server
- Each result is keyed by agent ID and request ID
- Results are automatically captured when agents publish to their output topics
- Results persist until manually deleted or the server restarts

## 📊 Retrieving Module States

The server tracks the execution state of each module request by request ID. You can monitor the progress and status of your requests using the state endpoints.

### State API Endpoint

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /modules/states/{request_id}` | GET | Get module state by request ID |

### State Values
- `started` - Module has been initialized
- `running` - Module is actively processing the request
- `completed` - Module has successfully finished processing
- `error` - Module encountered an error during processing
- `failed` - Module failed critically

### Example Usage

#### Track Echo Module State
```bash
# Trigger echo module with a specific request ID
curl -X POST "http://localhost:8000/agent/{agent_id}/echo_module" \
-H "Content-Type: application/json" \
-d '{"message": "test message", "id": "echo-test-123"}'

# Check the state of the request
curl -s "http://localhost:8000/modules/states/echo-test-123" | jq .
```

Example state response:
```json
{
  "agent_id": "agent-123",
  "module_name": "echo_module",
  "state": "completed",
  "timestamp": "2023-01-01T12:00:00Z",
  "details": {
    "action": "request_completed"
  }
}
```

#### 2. Trigger Ping Module
```bash
# Trigger ping module on a specific agent
curl -X POST "http://localhost:8000/agent/{agent_id}/ping_module" \
-H "Content-Type: application/json" \
-d '{"host": "8.8.8.8", "count": 4}'
```

#### 3. Trigger Echo Module
```bash
# Trigger echo module on a specific agent
curl -X POST "http://localhost:8000/agent/{agent_id}/echo_module" \
-H "Content-Type: application/json" \
-d '{"message": "test message"}'
```

#### 4. View Traces in OpenSearch
```bash
# View recent traces (organized by agent-specific subjects)
curl -s -X POST "localhost:9200/otel-v1-apm-span-*/_search" \
-H "Content-Type: application/json" \
-d '{"size": 10, "sort": [{"startTime": {"order": "desc"}}]}' \
| jq '.hits.hits[]._source | {name, serviceName, traceId, traceGroup, startTime}'

# Search for specific agent traces
curl -s -X POST "localhost:9200/otel-v1-apm-span-*/_search" \
-H "Content-Type: application/json" \
-d '{"size": 10, "query": {"wildcard": {"name": "*{agent_id}*"}}}' \
| jq '.hits.hits[]._source | {name, serviceName, traceId, traceGroup, startTime}'

# View service maps
curl -s localhost:9200/otel-v1-apm-service-map/_search?pretty
```

## 📥 Retrieving Module Results

The server now automatically captures and stores detailed results from module executions. Instead of only receiving a generic success message, you can now retrieve the actual metrics and data from each module execution.

### New API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /agents/{agent_id}/results` | GET | Get all results for a specific agent |
| `GET /agents/{agent_id}/results/{request_id}` | GET | Get specific result by request ID |
| `DELETE /agents/{agent_id}/results/{request_id}` | DELETE | Delete a specific result |

### Example Usage

#### Ping Module Results
When you trigger a ping command:
```bash
# Trigger ping and save the request ID
RESPONSE=$(curl -s -X POST "http://localhost:8000/agent/{agent_id}/ping_module" \
-H "Content-Type: application/json" \
-d '{"host": "8.8.8.8", "count": 4}')

REQUEST_ID=$(echo $RESPONSE | jq -r '.id')
```

You can then retrieve the detailed results:
```bash
# Get the specific result
curl -s "http://localhost:8000/agents/{agent_id}/results/$REQUEST_ID" | jq .

# Example response:
{
  "id": "06cd58b9-41bb-4fe2-a280-9d25f6c81a5f",
  "address": "8.8.8.8",
  "rtts": [43.98, 41.23, 42.67, 44.12],
  "packets_received": 4,
  "packets_sent": 4
}
```

#### Result Storage
- Results are stored in-memory on the server
- Each result is keyed by agent ID and request ID
- Results are automatically captured when agents publish to their output topics
- Results persist until manually deleted or the server restarts

The new `ping_module.py` provides advanced network measurement capabilities:

### Basic Usage

Send a JSON message to the agent's input subject:
```json
{
  "target": "google.com",
  "count": 4,
  "port": 80,
  "request_id": "test-123"
}
```

### Subject Structure
- **Input:** `agent.{agent_id}.in` (e.g., `agent.aiori_1.in`)
- **Output:** `agent.{agent_id}.out`
- **Error:** `agent.{agent_id}.error`

### Example Response
```json
{
  "protocol": "ICMP",
  "address": "google.com",
  "is_alive": true,
  "port": 80,
  "timestamp": 1725749200.123456,
  "rtt_min": 12.34,
  "rtt_avg": 15.67,
  "rtt_max": 23.45,
  "packets_sent": 4,
  "packets_received": 4,
  "packet_loss": 0.0,
  "jitter": 2.1,
  "request_id": "test-123"
}
```

## 📡 NATS Subjects

| Subject Pattern | Purpose | Descrption |
|----------------|---------|-----------|
| `agent.{id}.in` | Agent command input | Request comes in here |
| `agent.{id}.out` | Agent response output | Response comes out from here |
| `agent.{id}.error` | Error messages | Error comes out from here |
| `heartbeat.{id}` | System health status | Heartbeat |

## 🔧 Areas for Improvement

### Enhanced Result Accessibility
The system now provides direct access to detailed module execution results through REST API endpoints, addressing the previous limitation where users only received generic success messages. This enhancement enables:

1. **Real-time result retrieval**: Access detailed metrics without relying solely on OpenSearch
2. **Programmatic result consumption**: Build applications that can programmatically retrieve and process measurement results
3. **Immediate feedback**: Get instant access to results without waiting for data to be processed and stored in OpenSearch

### Trace Context Propagation
Currently, only heartbeat traces are well-organized in OpenSearch. To improve trace visibility for all modules:

1. **Implement consistent trace context propagation**:
   - Modify the NATS client to automatically inject/extract trace context in message headers
   - Ensure trace context flows through the entire request-response cycle

2. **Enhance module-level tracing**:
   - Add module-specific spans for operations (e.g., "ping_execution", "echo_processing")
   - Include module metadata in trace attributes

3. **Improve trace grouping**:
   - Organize traces by module type rather than agent-specific subjects
   - Create meaningful trace group names like "ping_module_execution" or "echo_module_response"

### Better Service Maps
To create more meaningful service maps:

1. **Add module-level service identification**:
   - Include module names in service metadata
   - Create service relationships based on module interactions

2. **Enhance trace attributes**:
   - Add module-specific attributes to traces
   - Include request/response metadata in trace attributes

### Searchable Traces
To make traces more discoverable:

1. **Standardize trace naming**:
   - Use consistent naming conventions across all modules
   - Include module names in span names

2. **Add searchable tags**:
   - Include module type, operation type, and other metadata as indexed attributes

## Run

```sh
$ python3 -m nats_observe
$ python3 -m fastapi run server/main.py
$ python3 -m aiori_agent  --nats_url nats://192.168.19.169:4222 --agent_id f7c34015-2b5c-4b95-b1bf-5e5391241dac --modules_path /internet-measurement-network/modules/
```

## 📋 Key Findings

During investigation, it was discovered that:

1. **All modules ARE being traced** - Both heartbeat and other modules (ping, echo) generate traces
2. **Traces are organized differently** - Heartbeat traces use consistent subjects, while module traces use agent-specific subjects
3. **Service maps ARE generated** - Communication patterns between server and agents are captured
4. **Trace context flows correctly** - Requests from server to agents maintain trace context

The main limitation is organizational - traces are searchable but not intuitively organized by module type, making it difficult to find specific module executions without knowing the agent-specific subject names.

## 🚀 Next Steps

To improve the observability experience:

1. **Refactor trace naming** - Modify the system to organize traces by module type rather than agent IDs
2. **Enhance trace attributes** - Add more metadata to make traces more informative
3. **Improve service map generation** - Create more meaningful service relationships based on module interactions
4. **Add module-specific dashboards** - Create OpenSearch Dashboards visualizations for each module type