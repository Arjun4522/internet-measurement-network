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
- UpdateAgentStatus
- ListAgents

### Module State Management
- SetModuleState
- GetModuleState
- UpdateModuleState
- ListModuleStates

### Measurement Results
- StoreResult
- GetResult
- ListResults
- DeleteResult

### Task Scheduling
- ScheduleTask
- GetTask
- UpdateTaskStatus
- ListDueTasks

## Setup

1. Install Go dependencies:
   ```bash
   cd dbos-go
   go mod tidy
   ```

2. Generate protobuf code for Go:
   ```bash
   cd dbos-go
   protoc --go_out=. --go-grpc_out=. api/dbos.proto
   ```

3. Install Redis (using Docker):
   ```bash
   docker run -d --name redis-dbos -p 6379:6379 redis:latest
   ```

4. Start the DBOS server:
   ```bash
   cd dbos-go
   go run cmd/main.go
   ```

## Testing

To test the DBOS service with a standalone gRPC client:

1. In another terminal, run the test client:
   ```bash
   cd dbos-go
   go run test/grpc_client.go
   ```

2. Clean up:
   ```bash
   pkill -f "dbos-go/cmd/main.go"
   docker stop redis-dbos && docker rm redis-dbos
   ```

## Future Integration with IMN Python Server

TODO:
1. Replace in-memory agent cache with DBOS gRPC client calls
2. Replace in-memory results cache with persistent storage via DBOS
3. Replace in-memory module state tracking with DBOS state management
4. Add DBOS client initialization in server startup
5. Update API endpoints to use DBOS for agent management
6. Update NATS handlers to store state changes in DBOS
7. Add error handling and fallback mechanisms for DBOS connectivity
8. Add configuration options for DBOS service address
9. Implement connection pooling for gRPC client
10. Add metrics and monitoring for DBOS integration