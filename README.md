# Internet Measurement Network (IMN)

## 🌐 Overview

The Internet Measurement Network (IMN) is a distributed system for performing network measurements using autonomous agents. The system uses NATS as a messaging backbone for communication between components, enabling scalable and resilient network monitoring.

## 🏗️ Architecture

### Core Components

1. **Agents**: Autonomous measurement nodes that perform network tests
2. **Server**: Central coordination service that manages agents
3. **NATS**: Message broker for communication between components

### Component Details

#### Agents (`src/aiori_agent/`)
Autonomous measurement nodes that can dynamically load modules to perform various network tests. Key features include:
- Dynamic module loading with hot-reloading capabilities
- NATS integration for communication
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

#### NATS (`docker-compose-core.yml`)
Message broker that serves as the communication backbone:
- Provides pub/sub messaging for all components
- Handles agent-to-server and server-to-agent communication
- Monitors agent health through heartbeat messages
- Enables scalable, decoupled architecture

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
   - Module performs network test (ping, echo, etc.)
   - Results are processed and formatted

4. **Result Reporting**:
   - Agent publishes results to output subject
   - Server captures and stores results in memory/database
   - Errors are published to error subject

## 🐳 Deployment Options

### Core Pipeline (Minimal Setup)
Deploy only the essential components: 2 agents, NATS, and server without observability.

```bash
docker-compose -f docker-compose-core.yml up
```

### Full Stack (With Observability)
Deploy all components including OpenTelemetry, OpenSearch, and Dashboards.

```bash
docker-compose up
```

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose

### Running the Core Pipeline

1. **Start the core system**:
   ```bash
   docker-compose -f docker-compose-core.yml up
   ```

2. **Access the services**:
   - **NATS Server:** `localhost:4222` (client connections)
   - **NATS Monitoring:** `localhost:8222` (metrics)
   - **Server API:** `localhost:8000` (agent coordination and API)
   - **Agent 1 API:** `localhost:9101` (metrics/control)
   - **Agent 2 API:** `localhost:9202` (metrics/control)

## 🧪 API Usage

### Get Alive Agents
```bash
# Get list of alive agents and their IDs
curl -s localhost:8000/agents/alive | jq
```

### Trigger Ping Module
```bash
# Get an agent ID first
AGENT_ID=$(curl -s localhost:8000/agents/alive | jq -r 'keys[0]')

# Trigger ping module on an agent
curl -X POST "http://localhost:8000/agent/$AGENT_ID/ping_module" \
-H "Content-Type: application/json" \
-d '{"host": "8.8.8.8", "count": 4}'
```

### Trigger Echo Module
```bash
# Get an agent ID first
AGENT_ID=$(curl -s localhost:8000/agents/alive | jq -r 'keys[0]')

# Trigger echo module on an agent
curl -X POST "http://localhost:8000/agent/$AGENT_ID/working_module" \
-H "Content-Type: application/json" \
-d '{"message": "test message"}'
```

### Retrieve Module Results

The server automatically captures and stores detailed results from module executions.

#### Get All Results for an Agent
```bash
# Get an agent ID first
AGENT_ID=$(curl -s localhost:8000/agents/alive | jq -r 'keys[0]')

# Get all results for the agent
curl -s "http://localhost:8000/agents/$AGENT_ID/results" | jq
```

#### Get Specific Result by Request ID
```bash
# First, trigger a ping with a specific request ID
RESPONSE=$(curl -s -X POST "http://localhost:8000/agent/$AGENT_ID/ping_module" \
-H "Content-Type: application/json" \
-d '{"host": "8.8.8.8", "count": 4, "id": "my-ping-request"}')

# Get the specific result
curl -s "http://localhost:8000/agents/$AGENT_ID/results/my-ping-request" | jq
```

### Monitor Module States

The server tracks the execution state of each module request by request ID.

#### Get Module State by Request ID
```bash
# Trigger a module with a specific request ID
curl -X POST "http://localhost:8000/agent/$AGENT_ID/working_module" \
-H "Content-Type: application/json" \
-d '{"message": "test message", "id": "echo-test-123"}'

# Check the state of the request
curl -s "http://localhost:8000/modules/states/echo-test-123" | jq
```

## 📦 Available Modules

### Ping Module
Performs ICMP ping or TCP ping to measure network latency and packet loss.

**Request Schema**:
```json
{
  "host": "8.8.8.8",
  "count": 4,
  "port": 80
}
```

**Response Format**:
```json
{
  "id": "request-id",
  "address": "8.8.8.8",
  "rtts": [43.98, 41.23, 42.67, 44.12],
  "packets_received": 4,
  "packets_sent": 4
}
```

### Echo Module
Echoes back the received message with additional metadata.

**Request Schema**:
```json
{
  "message": "test message"
}
```

**Response Format**:
```json
{
  "id": "request-id",
  "message": "test message",
  "processed_at": 1234567890.123,
  "from_module": "working_module"
}
```

## 🛠️ Development

### Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd internet-measurement-network
   ```

2. **Install dependencies**:
   ```bash
   pip install -r server/requirements.txt
   pip install -r src/aiori_agent/requirements.txt
   ```

3. **Start NATS server**:
   ```bash
   docker-compose -f docker-compose-core.yml up nats
   ```

4. **Start the server**:
   ```bash
   cd server
   fastapi run main.py
   ```

5. **Start agents**:
   ```bash
   # In a new terminal
   python -m aiori_agent
   
   # In another terminal
   AGENT_NAME=aiori_2 python -m aiori_agent
   ```

## 📡 NATS Subjects

| Subject Pattern | Purpose | Description |
|----------------|---------|-------------|
| `agent.heartbeat_module` | Heartbeat messages | All agents send heartbeats here |
| `agent.{id}.in` | Agent command input | Request comes in here |
| `agent.{id}.out` | Agent response output | Response comes out from here |
| `agent.{id}.error` | Error messages | Error comes out from here |
| `agent.module.state` | Module state updates | Module state changes are published here |

## 📋 Key Features

1. **Dynamic Module Loading**: Agents can load/unload modules at runtime without restart
2. **Hot Reloading**: Modules are automatically reloaded when files change
3. **Crash Recovery**: Automatic restart of failed modules with state preservation
4. **Real-time Results**: Immediate access to measurement results via REST API
5. **Module State Tracking**: Monitor the execution state of all module requests
6. **Scalable Architecture**: Decoupled components communicating via NATS messaging
7. **Extensible Design**: Easy to add new measurement modules

## 🚀 Next Steps

1. Add more measurement modules (traceroute, DNS lookup, HTTP latency, etc.)
2. Implement result persistence with a proper database
3. Add authentication and authorization for API access
4. Create a web dashboard for monitoring and control
5. Implement alerting based on measurement thresholds