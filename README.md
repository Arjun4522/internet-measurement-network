# Internet Measurement Network (IMN)

A distributed system for performing network measurements using autonomous agents with real-time observability and persistent storage.

## 🏗️ Architecture Overview

The Internet Measurement Network is a distributed system designed for large-scale network measurements. It utilizes a microservices architecture with autonomous agents that can dynamically load modules to perform various network tests.

### Core Components

1. **Agents** - Autonomous measurement nodes that perform network tests
2. **Server** - Central coordination service that manages agents and routes requests
3. **DBOS** - Distributed Business Operating System for persistent storage and state management
4. **NATS** - High-performance message broker for inter-component communication
5. **OpenTelemetry Collector** - Aggregates and processes observability data
6. **Data Prepper** - Transforms and routes telemetry data to OpenSearch
7. **OpenSearch** - Storage and search engine for telemetry data
8. **OpenSearch Dashboards** - Visualization interface for telemetry data

### Key Features

- **Distributed Measurements** - Deploy agents anywhere to collect network data
- **Dynamic Modules** - Hot-reloadable modules for different measurement types
- **Real-time Observability** - Comprehensive tracing, logging, and metrics
- **Persistent Storage** - DBOS service for reliable data storage
- **Scalable Architecture** - Horizontally scalable components
- **Resilient Design** - Built-in fault tolerance and recovery mechanisms

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development)

### Running the Full Stack

```bash
# Start the complete system
docker-compose up -d

# Wait for services to initialize (30-60 seconds)
sleep 30

# Verify services are running
docker-compose ps
```

### Accessing Services

Once running, the following services will be available:

| Service | URL | Description |
|---------|-----|-------------|
| Server API | http://localhost:8000 | Main API for agent management |
| Agent 1 | http://localhost:9101 | Measurement agent with metrics |
| Agent 2 | http://localhost:9102 | Measurement agent with metrics |
| NATS | nats://localhost:4222 | Core messaging system |
| OpenSearch | http://localhost:9200 | Data storage and search |
| OpenSearch Dashboards | http://localhost:5601 | Data visualization |
| DBOS | grpc://localhost:50051 | Persistent storage service |

## 📊 System Components

### Agents (`src/aiori_agent/`)

Autonomous measurement nodes with dynamic module loading capabilities:

- **Hot Module Reloading** - Load/unload modules without restarting
- **Multiple Measurement Types** - Ping, TCP ping, echo, and custom modules
- **Health Monitoring** - Continuous heartbeat reporting
- **Error Recovery** - Automatic restart on module failures
- **Observability** - Built-in OpenTelemetry instrumentation

### Server (`server/`)

Central coordination service that manages the entire network:

- **Agent Registry** - Tracks all connected agents and their status
- **Request Routing** - Routes measurement requests to appropriate agents
- **Schema Validation** - Validates requests against module specifications
- **Result Management** - Stores and retrieves measurement results
- **RESTful API** - Clean interface for external integrations

### DBOS (Distributed Business Operating System)

Go-based microservice for persistent storage and state management:

- **Agent State Management** - Tracks agent lifecycle and status
- **Measurement Results** - Persistent storage of all measurement data
- **Module State Tracking** - Monitors execution state of all modules
- **Task Scheduling** - Manages scheduled and recurring measurements
- **High Performance** - Built with Go and Redis for fast operations

### Observability Stack

Comprehensive monitoring and visualization capabilities:

- **OpenTelemetry Collection** - Automatic tracing, logging, and metrics
- **Data Transformation** - Data Prepper processes telemetry for storage
- **Centralized Storage** - OpenSearch indexes all observability data
- **Rich Visualizations** - Dashboards for real-time system monitoring

## 🛠️ Core Modules

### Ping Module

Performs ICMP ping measurements with detailed statistics:

```bash
# Trigger a ping measurement
curl -X POST "http://localhost:8000/agent/{agent_id}/ping_module" \
  -H "Content-Type: application/json" \
  -d '{"host": "8.8.8.8", "count": 4}'
```

Returns detailed RTT statistics, packet loss, and jitter measurements.

### TCPing Module

Measures TCP connectivity and latency to specific ports:

```bash
# Test TCP connectivity
curl -X POST "http://localhost:8000/agent/{agent_id}/tcping" \
  -H "Content-Type: application/json" \
  -d '{"host": "google.com", "port": 443, "count": 5}'
```

Provides connection time, response time, and availability metrics.

### Echo Module

Simple message echoing for testing basic agent functionality:

```bash
# Test agent connectivity
curl -X POST "http://localhost:8000/agent/{agent_id}/echo_module" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello IMN!"}'
```

### Heartbeat Module

Continuous health monitoring with system metrics:

- CPU and memory utilization
- Network interface statistics
- Disk usage information
- System load averages

### Faulty Module

Testing module for simulating various error conditions:

```bash
# Simulate processing delay
curl -X POST "http://localhost:8000/agent/{agent_id}/faulty_module" \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "delay": 5}'

# Simulate crash
curl -X POST "http://localhost:8000/agent/{agent_id}/faulty_module" \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "crash": true}'
```

## 📈 API Usage

### Agent Management

```bash
# List all agents
curl http://localhost:8000/agents | jq

# Get specific agent details
curl http://localhost:8000/agents/{agent_id} | jq

# List only alive agents
curl http://localhost:8000/agents/alive | jq
```

### Triggering Measurements

```bash
# Ping measurement
curl -X POST "http://localhost:8000/agent/{agent_id}/ping_module" \
  -H "Content-Type: application/json" \
  -d '{"host": "1.1.1.1", "count": 10}'

# TCP connectivity test
curl -X POST "http://localhost:8000/agent/{agent_id}/tcping" \
  -H "Content-Type: application/json" \
  -d '{"host": "github.com", "port": 443}'
```

### Retrieving Results

```bash
# Get all results for an agent
curl http://localhost:8000/agents/{agent_id}/results | jq

# Get specific result by ID
curl http://localhost:8000/agents/{agent_id}/results/{request_id} | jq

# Monitor execution state
curl http://localhost:8000/modules/states/{request_id} | jq
```

## 🧪 Testing

The system includes comprehensive testing capabilities:

```bash
# Run end-to-end tests
./tests/test_endpoints.sh

# Run chaos engineering tests
./tests/chaos_test.sh

# Generate sample traces for testing
./tests/generate_traces.sh
```

### Test Coverage

- **System Health Checks** - Verify all services are operational
- **Durability Testing** - Validate persistence through service restarts
- **Idempotency Testing** - Ensure consistent responses for repeated requests
- **Consistency Testing** - Validate multi-agent processing
- **Resilience Testing** - Test recovery from service interruptions
- **Agent Recovery** - Verify agent failure and recovery processes

## 🔍 Observability

### Tracing

All module executions are automatically traced with OpenTelemetry:

- Request flow from server to agent and back
- Detailed timing information for each operation
- Error tracing with contextual information
- Service maps showing system interactions

### Metrics

Comprehensive metrics collection:

- Agent health and performance metrics
- Module execution statistics
- System resource utilization
- Network measurement results

### Logging

Structured logging throughout the system:

- Debug information for troubleshooting
- Error and warning notifications
- Audit trails for all operations
- Performance profiling data

## 🔄 Data Flow

1. **Agent Registration** - Agents send heartbeats to register with the server
2. **Request Submission** - Clients send measurement requests to the server API
3. **Request Validation** - Server validates requests against module schemas
4. **Message Routing** - Server publishes requests to appropriate NATS subjects
5. **Measurement Execution** - Agents execute measurements using loaded modules
6. **Result Reporting** - Agents publish results to output subjects
7. **Result Storage** - Server captures and stores results via DBOS
8. **Observability Collection** - OpenTelemetry data is sent to the collector
9. **Data Processing** - Data Prepper transforms data for storage
10. **Data Storage** - Processed data is stored in OpenSearch
11. **Visualization** - Users access data through OpenSearch Dashboards

## 📦 Development

### Local Agent Development

```bash
# Install dependencies
pip install -e .

# Start an agent locally
python -m aiori_agent --nats_url nats://localhost:4222
```

### Server Development

```bash
# Install server dependencies
pip install -r server/requirements.txt

# Start the server
fastapi run server/main.py
```

### DBOS Development

```bash
# Navigate to DBOS directory
cd dbos-go

# Install dependencies
go mod tidy

# Start DBOS service
go run cmd/main.go
```

## 🎯 Future Enhancements

### Short-term Goals

1. **Enhanced Module System** - Support for more complex measurement modules
2. **Advanced Scheduling** - Cron-like scheduling and conditional execution
3. **Improved Security** - Authentication, authorization, and encryption
4. **Custom Dashboards** - Module-specific visualization templates

### Long-term Vision

1. **Global Deployment** - Coordinated worldwide measurement network
2. **AI-Powered Analytics** - Anomaly detection and predictive analysis
3. **Federated Architecture** - Multi-tenant deployment capabilities
4. **Edge Computing** - Integration with edge computing platforms

## 📚 Documentation

Additional documentation is available in the following locations:

- [API Documentation](http://localhost:8000/docs) - Interactive API documentation
- [Architecture Diagrams](docs/architecture/) - Detailed system diagrams
- [Module Development Guide](docs/modules/) - Creating custom measurement modules
- [Deployment Guide](docs/deployment/) - Production deployment strategies

## 🤝 Contributing

We welcome contributions from the community! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to get involved.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.