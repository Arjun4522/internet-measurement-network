# Internet Measurement Network (IMN)

A distributed system for performing network measurements using autonomous agents with real-time coordination and monitoring capabilities.

## 🏗️ Architecture Overview

The Internet Measurement Network is a microservices-based system that enables distributed network measurement tasks through autonomous agents. The architecture leverages NATS for messaging, OpenTelemetry for observability, and follows a modular design for extensibility.

### Core Components

#### 1. Agents (`src/aiori_agent/`)
Autonomous measurement nodes that dynamically load modules to perform various network tests:
- Dynamic module loading with hot-reloading capabilities
- NATS integration for communication
- OpenTelemetry instrumentation for observability
- Crash recovery and error handling mechanisms
- Heartbeat mechanism for health monitoring

#### 2. Server (`server/`)
Central coordination service built with FastAPI that:
- Maintains registry of active agents
- Processes agent heartbeats
- Provides REST API for querying agent status
- Routes measurement requests to appropriate agents
- Validates measurement requests against module schemas
- Tracks workflow execution states

#### 3. NATS Messaging System
Message broker serving as the communication backbone:
- Pub/sub messaging for all components
- Agent-to-server and server-to-agent communication
- Health monitoring through heartbeat messages
- Scalable, decoupled architecture

#### 4. OpenTelemetry Collector
Aggregates and processes observability data:
- Receives traces, logs, and metrics from agents and server
- Processes and batches telemetry data
- Routes data to appropriate backends

#### 5. Data Storage & Visualization
- **OpenSearch**: Storage engine for telemetry data with daily indexing
- **OpenSearch Dashboards**: Visualization interface for telemetry data

## 🔄 Data Flow

1. **Agent Registration**:
   - Agents send heartbeats to `agent.heartbeat_module` subject
   - Server maintains agent registry and health status

2. **Measurement Request**:
   - Client sends request to server API endpoint `/agent/{agent_id}/{module_name}`
   - Server validates request against module schema
   - Server publishes request to appropriate NATS subject

3. **Measurement Execution**:
   - Agent receives request on its input subject
   - Agent executes measurement using loaded module
   - Module performs network test (ping, echo, etc.)

4. **Result Reporting**:
   - Agent publishes results to output subject
   - Agent reports state transitions to `agent.module.state`
   - Server captures workflow results and states

5. **Observability Pipeline**:
   - OpenTelemetry data is collected and processed
   - Data is transformed by Data Prepper
   - Data is stored in OpenSearch indices
   - Service maps are generated from trace data

## 🐳 Deployment

### Prerequisites
- Docker and Docker Compose
- Python 3.10+ (for local development)

### Quick Start

1. **Start the complete system**:
   ```bash
   docker-compose up --build
   ```

2. **Access services**:
   - **Server API**: `localhost:8000`
   - **NATS Server**: `localhost:4222`
   - **OpenSearch**: `localhost:9200`
   - **OpenSearch Dashboards**: `localhost:5601`

### Individual Component Startup

#### Server
```bash
python3 -m fastapi run server/main.py
```

#### Agent
```bash
python3 -m aiori_agent --nats_url nats://localhost:4222 \
  --agent_id $(uuidgen) \
  --modules_path ./modules/
```

## 🛠️ API Usage

### Health & Discovery
```bash
# Check system health
curl http://localhost:8000/

# List all agents
curl http://localhost:8000/agents

# List alive agents
curl http://localhost:8000/agents/alive

# Get specific agent info
curl http://localhost:8000/agents/{agent_id}
```

### Module Execution
```bash
# Execute echo module
curl -X POST http://localhost:8000/agent/{agent_id}/echo_module \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, World!"}'

# Execute ping module
curl -X POST http://localhost:8000/agent/{agent_id}/ping_module \
  -H "Content-Type: application/json" \
  -d '{"host": "8.8.8.8", "count": 4}'

# Execute faulty module (testing errors)
curl -X POST http://localhost:8000/agent/{agent_id}/faulty_module \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "crash": true}'

# Async execution
curl -X POST http://localhost:8000/agent/{agent_id}/echo_module/async \
  -H "Content-Type: application/json" \
  -d '{"message": "async test"}'
```

### Workflow Management
```bash
# List all workflows
curl http://localhost:8000/workflows

# List workflows by status
curl http://localhost:8000/workflows?status=COMPLETED
curl http://localhost:8000/workflows?status=FAILED

# Get workflow details
curl http://localhost:8000/workflows/{workflow_id}

# Cancel workflow
curl -X POST http://localhost:8000/workflows/{workflow_id}/cancel
```

### Debug Endpoints
```bash
# System state overview
curl http://localhost:8000/debug/state
```

## 📊 Module Specifications

### Echo Module
Simple module that echoes back received messages with processing timestamp.

**Schema**:
```json
{
  "message": "string"
}
```

**Subjects**:
- Input: `agent.{agent_id}.working_module.in`
- Output: `agent.{agent_id}.working_module.out`
- Error: `agent.{agent_id}.working_module.error`

### Ping Module
Performs ICMP ping or TCP ping to target hosts.

**Schema**:
```json
{
  "host": "IP/Hostname",
  "count": 3,
  "port": 80
}
```

**Subjects**:
- Input: `agent.{agent_id}.in`
- Output: `agent.{agent_id}.out`
- Error: `agent.{agent_id}.error`

### Faulty Module
Test module for simulating errors and delays.

**Schema**:
```json
{
  "message": "string",
  "delay": null,
  "crash": false
}
```

**Subjects**:
- Input: `agent.{agent_id}.faulty_module.in`
- Output: `agent.{agent_id}.faulty_module.out`
- Error: `agent.{agent_id}.faulty_module.error`

## 🧪 Testing

### Automated Testing
```bash
# Run comprehensive endpoint tests
./tests/test_endpoints.sh

# Run specific tests
curl -X POST http://localhost:8000/agent/{agent_id}/echo_module \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}'
```

### Manual Verification
1. Start the system with `docker-compose up`
2. Get an active agent ID:
   ```bash
   curl -s http://localhost:8000/agents/alive | jq 'keys[0]'
   ```
3. Test module execution with the retrieved agent ID
4. Monitor workflow states and results

## 📈 Observability

### Trace Organization
- **Heartbeat traces**: Consistent subject `agent.heartbeat_module`
- **Module traces**: Agent-specific subjects for granular tracking
- **Service maps**: Generated from trace data showing communication patterns

### Monitoring Endpoints
- **NATS Monitoring**: `localhost:8222`
- **OpenTelemetry Collector**: `localhost:8888/metrics`
- **Agent Metrics**: Individual ports per agent

## 🚀 Development

### Project Structure
```
├── docker/              # Docker configurations
├── modules/             # Agent modules (ping, echo, faulty)
├── otlp/                # OpenTelemetry collector config
├── server/              # FastAPI server implementation
├── src/aiori_agent/     # Agent core implementation
├── tests/               # Test scripts
└── docker-compose.yml   # System orchestration
```

### Adding New Modules
1. Create new module in `modules/` directory
2. Extend `BaseWorker` class
3. Implement required methods (`setup`, `run`, `handle`)
4. Define input schema using Pydantic
5. Set appropriate subject names

### Extending Server Functionality
1. Add new endpoints in `server/main.py`
2. Follow existing patterns for validation and error handling
3. Maintain consistent workflow state management

## 🔧 Configuration

### Environment Variables
```bash
# NATS configuration
NATS_URL=nats://localhost:4222

# OpenTelemetry endpoints
OTLP_TRACE_ENDPOINT=otel-collector:4317
OTLP_METRICS_ENDPOINT=otel-collector:4317
OTLP_LOGS_ENDPOINT=otel-collector:4317

# Database
DBOS_SYSTEM_DATABASE_URL=sqlite:///db/data.db
```

### Module Subject Patterns
Each module defines its own subject naming pattern:
- Echo Module: `agent.{agent_id}.working_module.{in|out|error}`
- Faulty Module: `agent.{agent_id}.faulty_module.{in|out|error}`
- Ping Module: `agent.{agent_id}.{in|out|error}`

## 📊 Key Features

1. **Distributed Architecture**: Scalable agent-based measurement system
2. **Real-time Coordination**: Instantaneous command and control
3. **Workflow Tracking**: Detailed state management for all operations
4. **Extensible Design**: Easy addition of new measurement modules
5. **Comprehensive Observability**: Full tracing, logging, and metrics
6. **Error Handling**: Robust error detection and reporting
7. **Hot Reloading**: Dynamic module updates without restarts

## 📋 Future Enhancements

1. **Advanced Analytics**: ML-based anomaly detection
2. **Dashboard Integration**: Custom visualization for measurement data
3. **Security Enhancements**: Authentication and encryption
4. **Persistence Layer**: Long-term storage for historical data
5. **Multi-region Support**: Geographically distributed agents