# DBOS - Distributed Business Operating System

A high-performance Go-based service for managing runtime state, measurement results, and control-plane coordination for the Internet Measurement Network system.

## Architecture Overview

The DBOS service is designed as a separate microservice that communicates with the Python server via gRPC. It handles:

1. **Runtime State Management** - Agents, requests, module states
2. **Network Measurement Results Storage** - Persistent storage of measurement data
3. **Control-Plane Coordination** - Scheduling, task management, and coordination
4. **Integration with Redis** - For fast, reliable persistence

## Key Components

- **gRPC Server** - Exposes APIs for Python server to interact with
- **State Manager** - Handles agent and module state transitions
- **Result Store** - Manages storage and retrieval of measurement results
- **Scheduler** - Handles task scheduling and coordination
- **Redis Client** - Connects to Redis for persistent storage

## Communication Flow

```
Python Server ←→ gRPC ←→ DBOS Service ←→ Redis
```

## API Endpoints

### Agent Management
- RegisterAgent
- GetAgent
- ListAgents

### Module State Management
- SetModuleState
- GetModuleState
- ListModuleStates

### Measurement Results
- StoreResult
- GetResult
- ListResults

### Task Scheduling
- ScheduleTask
- GetTask
- ListDueTasks

## Setup

1. Install Go dependencies:
   ```bash
   cd dbos-go
   go mod tidy
   ```

2. Install Redis (using Docker):
   ```bash
   docker run -d --name redis-dbos -p 6379:6379 redis:latest
   ```

3. Start the DBOS server:
   ```bash
   cd dbos-go
   REDIS_ADDR=localhost:6379 PORT=50051 go run cmd/main.go
   ```

The DBOS service will start on port 50051 and connect to Redis at localhost:6379.

## Environment Variables

- `REDIS_ADDR` - Redis address (default: "localhost:6379")
- `PORT` - Server port (default: "50051")

## Testing

To test the DBOS service with a standalone gRPC client:

1. In another terminal, run the test client:
   ```bash
   cd dbos-go
   go run test/grpc_client.go
   ```

This will run a series of tests including:
- Registering a test agent
- Getting agent information
- Setting and getting module states
- Storing and retrieving measurement results
- Listing all agents

2. Clean up:
   ```bash
   pkill -f "dbos-go/cmd/main.go"
   docker stop redis-dbos && docker rm redis-dbos
   ```

## Integration with IMN Python Server

The DBOS service is now integrated with the IMN Python server. To enable DBOS integration:

1. Set environment variables in the Python server:
   ```bash
   export USE_DBOS=true
   export DBOS_ADDRESS=localhost:50051
   ```

2. Install Python gRPC dependencies:
   ```bash
   pip install grpcio grpcio-tools
   ```

3. Generate Python gRPC client code:
   ```bash
   python -m grpc_tools.protoc -I./dbos-go/api --python_out=./server --grpc_python_out=./server ./dbos-go/api/dbos.proto
   ```

4. Start the Python server:
   ```bash
   cd server
   python -m fastapi run main.py
   ```

When enabled, the Python server will:
- Register agents with DBOS on heartbeat
- Store module states in DBOS
- Store measurement results in DBOS
- Retrieve data from DBOS when available, with in-memory cache as fallback