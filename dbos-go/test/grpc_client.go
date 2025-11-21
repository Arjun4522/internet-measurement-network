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
	}

	// Test storing a measurement result
	resultData := `{"target":"8.8.8.8","latency_ms":25,"timestamp":"2023-01-01T00:00:00Z"}`
	result := &api.MeasurementResult{
		Id:         "result-123",
		AgentId:    "test-agent-1",
		ModuleName: "ping_module",
		Data:       []byte(resultData),
		Timestamp:  time.Now().Unix(),
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
