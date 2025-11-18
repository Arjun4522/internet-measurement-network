# Internet Measurement Network (IMN)

A distributed network measurement and monitoring system built on NATS messaging with OpenTelemetry observability.

## 🏗️ Architecture Overview

The IMN follows a microservices architecture with decoupled components communicating through NATS messaging:

```
aiori-imn/
├── agent/                 # Core agent module
│   ├── __main__.py       # Agent entry point
│   ├── agent.py          # Main agent class & NATS management
│   ├── cli.py            # Typer-based CLI commands
│   ├── config.py         # Configuration settings
│   ├── module_manager.py # Dynamic module loading
│   └── base.py           # BaseWorker class
├── modules/              # Pluggable measurement modules
│   ├── echo_module.py    # Basic echo functionality
│   ├── faulty_module.py  # Error simulation module
│   ├── heartbeat_module.py # System health monitoring
│   └── ping_module.py    # Network latency measurement
├── docker/               # Docker configuration
│   └── Dockerfile.agent  # Agent container definition
├── docker-compose.yml    # Full stack deployment
└── requirements.txt      # Python dependencies
```

## 🧩 Component Design

### 1. **NATS Message Broker**
- Central communication hub using publish/subscribe pattern
- Enables decoupled, asynchronous communication between agents
- Ports: 4222 (client connections), 8222 (monitoring)

### 2. **Measurement Agents**
- Independent worker processes performing network measurements
- Dynamically load modules for different measurement types
- Communicate exclusively through NATS subjects
- Export telemetry data via OpenTelemetry

### 3. **Pluggable Modules**
- **heartbeat_module**: System health monitoring with 2-second intervals
- **ping_module**: ICMP-based network latency measurement
- **echo_module**: Basic message echoing for testing
- **faulty_module**: Simulates errors for testing error handling
- **tcping_module**: TCP port connectivity testing

### 4. **Observability Stack**
- **OpenTelemetry Collector**: Receives and processes telemetry data
- **Debug Exporter**: Displays telemetry data for monitoring
- **NATS UI Dashboard**: Web interface for NATS message traffic
- **NUI Dashboard**: Advanced NATS monitoring and visualization

## 🔀 Data Flow

1. **Agent Initialization**:
   - Agents connect to NATS and broadcast heartbeats
   - Modules dynamically loaded and registered
   - Telemetry exporters initialized

2. **Measurement Workflow**:
   - External systems send JSON commands via NATS subjects
   - Agents process requests and send results back via NATS
   - Telemetry data exported to OpenTelemetry collector

3. **Communication Patterns**:
   - **Control**: `agent.{id}.in` (send commands)
   - **Responses**: `agent.{id}.out` (receive results)
   - **Errors**: `agent.{id}.error` (error handling)
   - **Health**: `heartbeat.{id}` (system monitoring)

## 🔄 Workflow

### Agent Lifecycle:
1. Start NATS connection
2. Load measurement modules dynamically
3. Register module schemas and subjects
4. Begin periodic heartbeat broadcasts
5. Listen for incoming measurement requests
6. Process requests and send responses
7. Export telemetry data continuously

### Measurement Process:
1. Command sent to `agent.{uuid}.in` subject
2. Agent receives and validates request
3. Module performs measurement operation
4. Results published to `agent.{uuid}.out` subject
5. Errors published to `agent.{uuid}.error` subject
6. Telemetry data exported via OpenTelemetry

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
   - **NUI Dashboard:** `localhost:31312` (advanced monitoring)
   - **Agent 1 API:** `localhost:9101` (metrics/control)
   - **Agent 2 API:** `localhost:9102` (metrics/control)
   - **OTLP Collector:** `localhost:5081` (telemetry endpoint)

## 🎯 Using the Ping Module

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

| Subject Pattern | Purpose | Description |
|----------------|---------|-------------|
| `agent.{id}.in` | Agent command input | Request comes in here |
| `agent.{id}.out` | Agent response output | Response comes out from here |
| `agent.{id}.error` | Error messages | Error comes out from here |
| `heartbeat.{id}` | System health status | Heartbeat |

## 🐳 Docker Services

| Service | Image | Ports | Purpose |
|---------|-------|-------|---------|
| `nats` | `nats:latest` | 4222, 8222 | Core messaging bus |
| `nats-ui` | `mdawar/nats-dashboard` | 9222 | Web dashboard |
| `nui` | `ghcr.io/nats-nui/nui` | 31312 | Native UI |
| `otel-collector` | `otel/opentelemetry-collector` | 5081, 4317, 4318 | Telemetry collection |
| `agent_1` | Custom build | 9101 | Measurement agent 1 |
| `agent_2` | Custom build | 9102 | Measurement agent 2 |

## 🛠️ Fixes Applied

### 1. **TCPing Module Dependency Issue**
**Problem**: Missing `six` Python package caused tcping module to fail
**Fix**: Added `RUN pip install --no-cache-dir six` to Dockerfile.agent
**Result**: TCPing module now loads and functions correctly

### 2. **OpenTelemetry Connection Issues**
**Problem**: Agents couldn't connect to OTLP collector due to:
- Wrong endpoint configuration (`localhost` instead of service name)
- Protocol mismatch (gRPC vs HTTP)
- Missing environment variables

**Fixes Applied**:
- Added `OTLP_TRACE_ENDPOINT` and `OTLP_LOGS_ENDPOINT` environment variables
- Configured OTLP collector to accept gRPC on port 5081
- Updated docker-compose.yml with correct port mappings
- Used service name `otel-collector` instead of `localhost`

**Result**: Telemetry data now flows successfully from agents to collector

### 3. **Network Configuration**
**Problem**: Docker networking prevented inter-container communication
**Fix**: Used Docker Compose service names for inter-container communication
**Result**: Agents can now communicate with OTLP collector via `otel-collector:5081`

## 🧪 Testing Endpoints

### Web UI Endpoints:
- **NUI Dashboard**: `http://localhost:31312`
- **NATS UI Dashboard**: `http://localhost:9222`
- **NATS Monitoring**: `http://localhost:8222`

### Agent API Endpoints:
- **Agent 1 Metrics**: `http://localhost:9101/metrics`
- **Agent 2 Metrics**: `http://localhost:9102/metrics`

### NATS Server Endpoints:
- **NATS Client Connection**: `nats://localhost:4222`

## 📊 Monitoring Telemetry

The system exports rich telemetry data including:
- **Traces**: Operation spans with timing information
- **Logs**: Structured log messages with metadata
- **Metrics**: System performance and health metrics
- **Events**: Detailed event information with attributes

All telemetry data flows through the OpenTelemetry collector and is currently displayed via the debug exporter.

## 🛡️ Security Considerations

- All containers run in an isolated Docker network
- Services use explicit port mappings for controlled access
- NATS authentication can be configured for production use
- Telemetry data is only exported internally within the Docker network

## 🚀 Future Enhancements

- Add authentication and authorization for NATS connections
- Implement persistent storage for measurement results
- Add alerting mechanisms for anomaly detection
- Extend module library with additional measurement types
- Add support for distributed tracing across multiple agents
- Implement data visualization dashboards