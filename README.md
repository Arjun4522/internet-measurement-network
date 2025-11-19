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

## 🧪 Testing Commands

### Check OpenSearch Indices
```bash
# Check what indices were created in OpenSearch
curl -s "http://localhost:9200/_cat/indices?v" | grep -E "ss4o|otel|traces|logs|metrics"

# Check document counts in the trace indices
curl -s "http://localhost:9200/otel-spans-*/_count"
curl -s "http://localhost:9200/otel-v1-apm-span*/_count"

# Check if logs and metrics indices exist
curl -s "http://localhost:9200/ss4o_logs-*/_count"
curl -s "http://localhost:9200/ss4o_metrics-*/_count"
```

### Check Data Prepper Logs
```bash
# Check for received data in Data Prepper logs
docker logs internet-measurement-network-data-prepper-1 | grep -i "received\|processing\|records\|events" | tail -n 20
```

## 🎯 Using the New Ping Module

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

## Run

```sh
$ python3 -m nats_observe
$ python3 -m fastapi run server/main.py
$ python3 -m aiori_agent  --nats_url nats://192.168.19.169:4222 --agent_id f7c34015-2b5c-4b95-b1bf-5e5391241dac --modules_path /internet-measurement-network/modules/
```