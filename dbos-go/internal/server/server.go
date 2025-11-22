package server

import (
	"context"
	"log"
	"net"
	"time"

	"github.com/internet-measurement-network/dbos/api"
	"github.com/internet-measurement-network/dbos/internal/models"
	"github.com/internet-measurement-network/dbos/internal/store"
	"github.com/internet-measurement-network/dbos/pkg/redis"
	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.17.0"
	"google.golang.org/grpc"
)

// Server implements the DBOS gRPC service
type Server struct {
	api.UnimplementedDBOSServer
	agentStore       *store.AgentStore
	moduleStateStore *store.ModuleStateStore
	resultStore      *store.ResultStore
	taskStore        *store.TaskStore
}

// NewServer creates a new DBOS server with OpenTelemetry instrumentation
func NewServer(redisAddr string) *Server {
	// Initialize OpenTelemetry
	initTracer()

	// Create Redis client
	redisClient := redis.NewClient(redisAddr)

	// Create stores
	agentStore := store.NewAgentStore(redisClient)
	moduleStateStore := store.NewModuleStateStore(redisClient)
	resultStore := store.NewResultStore(redisClient)
	taskStore := store.NewTaskStore(redisClient)

	return &Server{
		agentStore:       agentStore,
		moduleStateStore: moduleStateStore,
		resultStore:      resultStore,
		taskStore:        taskStore,
	}
}

// initTracer initializes the OpenTelemetry tracer
func initTracer() {
	ctx := context.Background()

	// Create the OTLP exporter
	exporter, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithEndpoint("otel-collector:4317"),
		otlptracegrpc.WithInsecure(),
	)
	if err != nil {
		log.Printf("Warning: Failed to create OTLP exporter: %v", err)
		return
	}

	// Create resource with service name
	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceName("dbos"),
		),
	)
	if err != nil {
		log.Printf("Warning: Failed to create resource: %v", err)
		return
	}

	// Create trace provider
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
	)

	// Set global tracer provider
	otel.SetTracerProvider(tp)

	// Set propagator
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(propagation.TraceContext{}, propagation.Baggage{}))

	log.Println("OpenTelemetry tracer initialized")
}

// Start starts the gRPC server with OpenTelemetry instrumentation
func (s *Server) Start(port string) error {
	lis, err := net.Listen("tcp", ":"+port)
	if err != nil {
		return err
	}

	// Create gRPC server with OpenTelemetry interceptor
	grpcServer := grpc.NewServer(
		grpc.UnaryInterceptor(otelgrpc.UnaryServerInterceptor()),
		grpc.StreamInterceptor(otelgrpc.StreamServerInterceptor()),
	)

	api.RegisterDBOSServer(grpcServer, s)

	return grpcServer.Serve(lis)
}

// RegisterAgent registers a new agent
func (s *Server) RegisterAgent(ctx context.Context, req *api.RegisterAgentRequest) (*api.RegisterAgentResponse, error) {
	agent := &models.Agent{
		ID:              req.Agent.Id,
		Hostname:        req.Agent.Hostname,
		Alive:           req.Agent.Alive,
		LastSeen:        time.Unix(req.Agent.LastSeen, 0),
		FirstSeen:       time.Unix(req.Agent.FirstSeen, 0),
		Config:          req.Agent.Config,
		TotalHeartbeats: req.Agent.TotalHeartbeats,
	}

	err := s.agentStore.RegisterAgent(ctx, agent)
	if err != nil {
		return &api.RegisterAgentResponse{
			Success: false,
			Error:   err.Error(),
		}, nil
	}

	return &api.RegisterAgentResponse{
		Success: true,
	}, nil
}

// GetAgent retrieves an agent by ID
func (s *Server) GetAgent(ctx context.Context, req *api.GetAgentRequest) (*api.GetAgentResponse, error) {
	agent, err := s.agentStore.GetAgent(ctx, req.AgentId)
	if err != nil {
		return &api.GetAgentResponse{
			Found: false,
			Error: err.Error(),
		}, nil
	}

	return &api.GetAgentResponse{
		Found: true,
		Agent: &api.Agent{
			Id:              agent.ID,
			Hostname:        agent.Hostname,
			Alive:           agent.Alive,
			LastSeen:        agent.LastSeen.Unix(),
			FirstSeen:       agent.FirstSeen.Unix(),
			Config:          agent.Config,
			TotalHeartbeats: agent.TotalHeartbeats,
		},
	}, nil
}

// ListAgents retrieves all agents
func (s *Server) ListAgents(ctx context.Context, req *api.ListAgentsRequest) (*api.ListAgentsResponse, error) {
	agents, err := s.agentStore.ListAgents(ctx)
	if err != nil {
		return &api.ListAgentsResponse{
			Error: err.Error(),
		}, nil
	}

	apiAgents := make([]*api.Agent, len(agents))
	for i, agent := range agents {
		apiAgents[i] = &api.Agent{
			Id:              agent.ID,
			Hostname:        agent.Hostname,
			Alive:           agent.Alive,
			LastSeen:        agent.LastSeen.Unix(),
			FirstSeen:       agent.FirstSeen.Unix(),
			Config:          agent.Config,
			TotalHeartbeats: agent.TotalHeartbeats,
		}
	}

	return &api.ListAgentsResponse{
		Agents: apiAgents,
	}, nil
}

// SetModuleState sets a module state
func (s *Server) SetModuleState(ctx context.Context, req *api.SetModuleStateRequest) (*api.SetModuleStateResponse, error) {
	state := &models.ModuleState{
		AgentID:      req.State.AgentId,
		ModuleName:   req.State.ModuleName,
		State:        req.State.State,
		ErrorMessage: req.State.ErrorMessage,
		Details:      req.State.Details,
		Timestamp:    time.Unix(req.State.Timestamp, 0),
		RequestID:    req.State.RequestId,
	}

	err := s.moduleStateStore.SetModuleState(ctx, state)
	if err != nil {
		return &api.SetModuleStateResponse{
			Success: false,
			Error:   err.Error(),
		}, nil
	}

	return &api.SetModuleStateResponse{
		Success: true,
	}, nil
}

// GetModuleState retrieves a module state by request ID
func (s *Server) GetModuleState(ctx context.Context, req *api.GetModuleStateRequest) (*api.GetModuleStateResponse, error) {
	state, err := s.moduleStateStore.GetModuleState(ctx, req.RequestId)
	if err != nil {
		return &api.GetModuleStateResponse{
			Found: false,
			Error: err.Error(),
		}, nil
	}

	return &api.GetModuleStateResponse{
		Found: true,
		State: &api.ModuleState{
			AgentId:      state.AgentID,
			ModuleName:   state.ModuleName,
			State:        state.State,
			ErrorMessage: state.ErrorMessage,
			Details:      state.Details,
			Timestamp:    state.Timestamp.Unix(),
			RequestId:    state.RequestID,
		},
	}, nil
}

// ListModuleStates retrieves all module states for an agent and module
func (s *Server) ListModuleStates(ctx context.Context, req *api.ListModuleStatesRequest) (*api.ListModuleStatesResponse, error) {
	states, err := s.moduleStateStore.ListModuleStates(ctx, req.AgentId, req.ModuleName)
	if err != nil {
		return &api.ListModuleStatesResponse{
			Error: err.Error(),
		}, nil
	}

	apiStates := make([]*api.ModuleState, len(states))
	for i, state := range states {
		apiStates[i] = &api.ModuleState{
			AgentId:      state.AgentID,
			ModuleName:   state.ModuleName,
			State:        state.State,
			ErrorMessage: state.ErrorMessage,
			Details:      state.Details,
			Timestamp:    state.Timestamp.Unix(),
			RequestId:    state.RequestID,
		}
	}

	return &api.ListModuleStatesResponse{
		States: apiStates,
	}, nil
}

// StoreResult stores a measurement result
func (s *Server) StoreResult(ctx context.Context, req *api.StoreResultRequest) (*api.StoreResultResponse, error) {
	result := &models.MeasurementResult{
		ID:         req.Result.Id,
		AgentID:    req.Result.AgentId,
		ModuleName: req.Result.ModuleName,
		Data:       req.Result.Data,
		Timestamp:  time.Unix(req.Result.Timestamp, 0),
	}

	err := s.resultStore.StoreResult(ctx, result)
	if err != nil {
		return &api.StoreResultResponse{
			Success: false,
			Error:   err.Error(),
		}, nil
	}

	return &api.StoreResultResponse{
		Success: true,
	}, nil
}

// GetResult retrieves a measurement result by agent ID and request ID
func (s *Server) GetResult(ctx context.Context, req *api.GetResultRequest) (*api.GetResultResponse, error) {
	result, err := s.resultStore.GetResult(ctx, req.AgentId, req.RequestId)
	if err != nil {
		return &api.GetResultResponse{
			Found: false,
			Error: err.Error(),
		}, nil
	}

	return &api.GetResultResponse{
		Found: true,
		Result: &api.MeasurementResult{
			Id:         result.ID,
			AgentId:    result.AgentID,
			ModuleName: result.ModuleName,
			Data:       result.Data,
			Timestamp:  result.Timestamp.Unix(),
		},
	}, nil
}

// ListResults retrieves all results for an agent
func (s *Server) ListResults(ctx context.Context, req *api.ListResultsRequest) (*api.ListResultsResponse, error) {
	results, err := s.resultStore.ListResults(ctx, req.AgentId)
	if err != nil {
		return &api.ListResultsResponse{
			Error: err.Error(),
		}, nil
	}

	apiResults := make([]*api.MeasurementResult, len(results))
	for i, result := range results {
		apiResults[i] = &api.MeasurementResult{
			Id:         result.ID,
			AgentId:    result.AgentID,
			ModuleName: result.ModuleName,
			Data:       result.Data,
			Timestamp:  result.Timestamp.Unix(),
		}
	}

	return &api.ListResultsResponse{
		Results: apiResults,
	}, nil
}

// ScheduleTask schedules a task
func (s *Server) ScheduleTask(ctx context.Context, req *api.ScheduleTaskRequest) (*api.ScheduleTaskResponse, error) {
	task := &models.Task{
		ID:          req.Task.Id,
		AgentID:     req.Task.AgentId,
		ModuleName:  req.Task.ModuleName,
		Payload:     req.Task.Payload,
		ScheduledAt: time.Unix(req.Task.ScheduledAt, 0),
		CreatedAt:   time.Unix(req.Task.CreatedAt, 0),
		Status:      req.Task.Status,
	}

	err := s.taskStore.ScheduleTask(ctx, task)
	if err != nil {
		return &api.ScheduleTaskResponse{
			Success: false,
			Error:   err.Error(),
		}, nil
	}

	return &api.ScheduleTaskResponse{
		Success: true,
	}, nil
}

// GetTask retrieves a task by ID
func (s *Server) GetTask(ctx context.Context, req *api.GetTaskRequest) (*api.GetTaskResponse, error) {
	task, err := s.taskStore.GetTask(ctx, req.TaskId)
	if err != nil {
		return &api.GetTaskResponse{
			Found: false,
			Error: err.Error(),
		}, nil
	}

	return &api.GetTaskResponse{
		Found: true,
		Task: &api.Task{
			Id:          task.ID,
			AgentId:     task.AgentID,
			ModuleName:  task.ModuleName,
			Payload:     task.Payload,
			ScheduledAt: task.ScheduledAt.Unix(),
			CreatedAt:   task.CreatedAt.Unix(),
			Status:      task.Status,
		},
	}, nil
}

// ListDueTasks retrieves all due tasks
func (s *Server) ListDueTasks(ctx context.Context, req *api.ListDueTasksRequest) (*api.ListDueTasksResponse, error) {
	tasks, err := s.taskStore.ListDueTasks(ctx, time.Unix(req.Timestamp, 0))
	if err != nil {
		return &api.ListDueTasksResponse{
			Error: err.Error(),
		}, nil
	}

	apiTasks := make([]*api.Task, len(tasks))
	for i, task := range tasks {
		apiTasks[i] = &api.Task{
			Id:          task.ID,
			AgentId:     task.AgentID,
			ModuleName:  task.ModuleName,
			Payload:     task.Payload,
			ScheduledAt: task.ScheduledAt.Unix(),
			CreatedAt:   task.CreatedAt.Unix(),
			Status:      task.Status,
		}
	}

	return &api.ListDueTasksResponse{
		Tasks: apiTasks,
	}, nil
}
