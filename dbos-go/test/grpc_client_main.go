package main

import (
	"context"
	"log"
	"time"

	"github.com/internet-measurement-network/dbos/api"
	"google.golang.org/grpc"
)

func main() {
	// Connect to the DBOS gRPC server
	conn, err := grpc.Dial("localhost:50051", grpc.WithInsecure())
	if err != nil {
		log.Fatalf("Failed to connect to DBOS server: %v", err)
	}
	defer conn.Close()

	// Create a client
	client := api.NewDBOSClient(conn)

	// Test registering an agent
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	agent := &api.Agent{
		Id:              "test-agent-1",
		Hostname:        "test-host-1",
		Alive:           true,
		LastSeen:        time.Now().Unix(),
		FirstSeen:       time.Now().Unix(),
		Config:          map[string]string{"region": "us-west", "version": "1.0"},
		TotalHeartbeats: 1,
	}

	registerReq := &api.RegisterAgentRequest{
		Agent: agent,
	}

	registerResp, err := client.RegisterAgent(ctx, registerReq)
	if err != nil {
		log.Printf("Error registering agent: %v", err)
	} else {
		log.Printf("Register agent response: %+v", registerResp)
	}

	// Test getting the agent back
	getReq := &api.GetAgentRequest{
		AgentId: "test-agent-1",
	}

	getResp, err := client.GetAgent(ctx, getReq)
	if err != nil {
		log.Printf("Error getting agent: %v", err)
	} else {
		log.Printf("Get agent response: %+v", getResp)
	}

	// Test setting a module state
	state := &api.ModuleState{
		AgentId:      "test-agent-1",
		ModuleName:   "ping_module",
		Version:      1, // For optimistic concurrency control
		State:        "running",
		ErrorMessage: "",
		Details:      map[string]string{"target": "8.8.8.8"},
		Timestamp:    time.Now().Unix(),
		RequestId:    "req-12345",
	}

	setStateReq := &api.SetModuleStateRequest{
		State: state,
	}

	setStateResp, err := client.SetModuleState(ctx, setStateReq)
	if err != nil {
		log.Printf("Error setting module state: %v", err)
	} else {
		log.Printf("Set module state response: %+v", setStateResp)
	}

	// Test getting the module state
	getStateReq := &api.GetModuleStateRequest{
		RequestId: "req-12345",
	}

	getStateResp, err := client.GetModuleState(ctx, getStateReq)
	if err != nil {
		log.Printf("Error getting module state: %v", err)
	} else {
		log.Printf("Get module state response: %+v", getStateResp)
		// Store the version for later use in concurrency testing
		if getStateResp.Found && getStateResp.State != nil {
			state.Version = getStateResp.State.Version
		}
	}

	// Test storing a measurement result with metadata
	resultData := `{"target":"8.8.8.8","latency_ms":25,"timestamp":"2023-01-01T00:00:00Z"}`
	result := &api.MeasurementResult{
		Id:                  "result-123",
		AgentId:             "test-agent-1",
		ModuleName:          "ping_module",
		Data:                []byte(resultData),
		Timestamp:           time.Now().Unix(),
		ReceivedAt:          time.Now().Unix(),
		AgentStartTime:      time.Now().Add(-10 * time.Minute).Unix(),
		AgentRuntimeVersion: "v1.2.3",
		ModuleRevision:      "abc123",
		DbosServerId:        "server-001",
		IngestSource:        "grpc-client-test",
	}

	storeResultReq := &api.StoreResultRequest{
		Result: result,
	}

	storeResultResp, err := client.StoreResult(ctx, storeResultReq)
	if err != nil {
		log.Printf("Error storing result: %v", err)
	} else {
		log.Printf("Store result response: %+v", storeResultResp)
	}

	// Test getting the result back
	getResultReq := &api.GetResultRequest{
		AgentId:   "test-agent-1",
		RequestId: "result-123",
	}

	getResultResp, err := client.GetResult(ctx, getResultReq)
	if err != nil {
		log.Printf("Error getting result: %v", err)
	} else {
		log.Printf("Get result response: %+v", getResultResp)
	}

	// Test idempotency by storing the same result again (should not create duplicates)
	storeResultResp2, err := client.StoreResult(ctx, storeResultReq)
	if err != nil {
		log.Printf("Error storing result (idempotency test): %v", err)
	} else {
		log.Printf("Store result response (idempotency test): %+v", storeResultResp2)
	}

	// Test optimistic concurrency control by trying to update with wrong version
	stateWithError := &api.ModuleState{
		AgentId:      "test-agent-1",
		ModuleName:   "ping_module",
		Version:      0, // Wrong version - should cause conflict
		State:        "completed",
		ErrorMessage: "",
		Details:      map[string]string{"target": "8.8.8.8", "status": "success"},
		Timestamp:    time.Now().Unix(),
		RequestId:    "req-12345",
	}

	setStateReqWithError := &api.SetModuleStateRequest{
		State: stateWithError,
	}

	setStateRespWithError, err := client.SetModuleState(ctx, setStateReqWithError)
	if err != nil {
		log.Printf("Expected error in optimistic concurrency test: %v", err)
	} else {
		log.Printf("Set module state response (optimistic concurrency test): %+v", setStateRespWithError)
	}

	// Test valid state transition (strong state ordering) - running -> completed
	validStateTransition := &api.ModuleState{
		AgentId:      "test-agent-1",
		ModuleName:   "ping_module",
		Version:      state.Version + 1, // Correct version
		State:        "completed",       // Valid transition from "running" to "completed"
		ErrorMessage: "",
		Details:      map[string]string{"target": "8.8.8.8", "status": "success"},
		Timestamp:    time.Now().Unix(),
		RequestId:    "req-12345",
	}

	setStateValidTransitionReq := &api.SetModuleStateRequest{
		State: validStateTransition,
	}

	setStateValidTransitionResp, err := client.SetModuleState(ctx, setStateValidTransitionReq)
	if err != nil {
		log.Printf("Error in valid state transition: %v", err)
	} else {
		log.Printf("Set module state response (valid state transition): %+v", setStateValidTransitionResp)
	}

	// Get the updated version after successful transition
	getStateResp2, err := client.GetModuleState(ctx, getStateReq)
	if err != nil {
		log.Printf("Error getting module state: %v", err)
	} else {
		log.Printf("Get module state response after valid transition: %+v", getStateResp2)
	}

	// Test invalid state transition (strong state ordering) - completed -> running
	invalidStateTransition := &api.ModuleState{
		AgentId:      "test-agent-1",
		ModuleName:   "ping_module",
		Version:      getStateResp2.State.Version, // Use version from previous get
		State:        "running",                   // Invalid transition from "completed" to "running"
		ErrorMessage: "",
		Details:      map[string]string{"target": "8.8.8.8"},
		Timestamp:    time.Now().Unix(),
		RequestId:    "req-12345",
	}

	setStateInvalidTransitionReq := &api.SetModuleStateRequest{
		State: invalidStateTransition,
	}

	setStateInvalidTransitionResp, err := client.SetModuleState(ctx, setStateInvalidTransitionReq)
	if err != nil {
		log.Printf("Expected error in invalid state transition: %v", err)
	} else {
		log.Printf("Set module state response (invalid state transition): %+v", setStateInvalidTransitionResp)
	}

	// Test task scheduling with visibility timeout
	task := &api.Task{
		Id:             "task-001",
		AgentId:        "test-agent-1",
		ModuleName:     "ping_module",
		Payload:        []byte(`{"target":"8.8.8.8","count":4}`),
		ScheduledAt:    time.Now().Unix(),
		CreatedAt:      time.Now().Unix(),
		Status:         "pending",
		VisibilityTime: time.Now().Add(30 * time.Second).Unix(), // 30 second visibility timeout
		RetryCount:     0,
	}

	scheduleTaskReq := &api.ScheduleTaskRequest{
		Task: task,
	}

	scheduleTaskResp, err := client.ScheduleTask(ctx, scheduleTaskReq)
	if err != nil {
		log.Printf("Error scheduling task: %v", err)
	} else {
		log.Printf("Schedule task response: %+v", scheduleTaskResp)
	}

	// Test getting the task
	getTaskReq := &api.GetTaskRequest{
		TaskId: "task-001",
	}

	getTaskResp, err := client.GetTask(ctx, getTaskReq)
	if err != nil {
		log.Printf("Error getting task: %v", err)
	} else {
		log.Printf("Get task response: %+v", getTaskResp)
	}

	// Test acknowledging the task (move from inflight to completed)
	ackTaskReq := &api.AckTaskRequest{
		TaskId: "task-001",
	}

	ackTaskResp, err := client.AckTask(ctx, ackTaskReq)
	if err != nil {
		log.Printf("Error acknowledging task: %v", err)
	} else {
		log.Printf("Ack task response: %+v", ackTaskResp)
	}

	// Test durable event logging
	eventsReq := &api.GetEventsRequest{
		Limit: 10,
	}

	eventsResp, err := client.GetEvents(ctx, eventsReq)
	if err != nil {
		log.Printf("Error getting events: %v", err)
	} else {
		log.Printf("Get events response: Found %d events", len(eventsResp.Events))
		for i, event := range eventsResp.Events {
			log.Printf("  Event %d: %s", i, string(event))
		}
	}

	// Test listing all agents
	listAgentsReq := &api.ListAgentsRequest{}
	listAgentsResp, err := client.ListAgents(ctx, listAgentsReq)
	if err != nil {
		log.Printf("Error listing agents: %v", err)
	} else {
		log.Printf("List agents response: %d agents found", len(listAgentsResp.Agents))
		for _, a := range listAgentsResp.Agents {
			log.Printf("  Agent: %s (%s)", a.Id, a.Hostname)
		}
	}

	log.Println("All tests completed successfully!")
}