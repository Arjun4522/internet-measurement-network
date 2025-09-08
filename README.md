# Internet-Measurement-Network

## 🏗️ Architecture

```
aiori-imn/
├── agent/                 # Core agent module
│   ├── __main__.py       # Agent entry point
│   ├── agent.py          # Main agent class & NATS management
│   ├── cli.py            # Typer-based CLI commands
│   ├── config.py         # Configuration settings
│   ├── module_manager.py # Dynamic module loading
│   └── base.py           # BaseWorker class
├── modules/              # Measurement modules
│   ├── echo_module.py    # Basic echo functionality
│   ├── faulty_module.py  # Error simulation module
│   ├── heartbeat_module.py # System health monitoring
│   └── ping_module.py    # NEW: Advanced ping with fallback
├── docker/               # Docker configuration
│   └── Dockerfile.agent  # Agent container definition
├── docker-compose.yml    # Full stack deployment
└── requirements.txt      # Python dependencies
```

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

## 🐳 Docker Services

| Service | Image | Ports | Purpose |
|---------|-------|-------|---------|
| `nats` | `nats:latest` | 4222, 8222 | Core messaging bus |
| `nats-ui` | `mdawar/nats-dashboard` | 9222 | Web dashboard |
| `nui` | `ghcr.io/nats-nui/nui` | 31312 | Native UI |
| `agent_1` | Custom build | 9101 | Measurement agent 1 |
| `agent_2` | Custom build | 9102 | Measurement agent 2 |
