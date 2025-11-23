package models

import (
	"time"
)

// ModuleState represents the state of a module execution with versioning
type ModuleState struct {
	AgentID      string            `json:"agent_id"`
	ModuleName   string            `json:"module_name"`
	State        string            `json:"state"`
	ErrorMessage string            `json:"error_message"`
	Details      map[string]string `json:"details"`
	Timestamp    time.Time         `json:"timestamp"`
	RequestID    string            `json:"request_id"`
	Version      int64             `json:"version"` // For optimistic concurrency control
}

// NewModuleState creates a new module state instance
func NewModuleState(agentID, moduleName, state, requestID string) *ModuleState {
	return &ModuleState{
		AgentID:    agentID,
		ModuleName: moduleName,
		State:      state,
		Details:    make(map[string]string),
		Timestamp:  time.Now(),
		RequestID:  requestID,
		Version:    1, // Start with version 1
	}
}

// ModuleStateEnum defines the possible states for a module
type ModuleStateEnum string

const (
	ModuleStateCreated   ModuleStateEnum = "created"
	ModuleStateStarted   ModuleStateEnum = "started"
	ModuleStateRunning   ModuleStateEnum = "running"
	ModuleStateCompleted ModuleStateEnum = "completed"
	ModuleStateError     ModuleStateEnum = "error"
	ModuleStateFailed    ModuleStateEnum = "failed"
)

// Valid state transitions
var validTransitions = map[ModuleStateEnum][]ModuleStateEnum{
	ModuleStateCreated:   {ModuleStateStarted},
	ModuleStateStarted:   {ModuleStateRunning, ModuleStateError, ModuleStateFailed},
	ModuleStateRunning:   {ModuleStateCompleted, ModuleStateError, ModuleStateFailed},
	ModuleStateCompleted: {}, // Terminal state
	ModuleStateError:     {}, // Terminal state
	ModuleStateFailed:    {}, // Terminal state
}

// IsValidTransition checks if a state transition is valid
func IsValidTransition(from, to ModuleStateEnum) bool {
	// Allow transitioning from empty state (initial)
	if from == "" {
		return true
	}

	// Check if the transition is valid
	validNextStates, exists := validTransitions[from]
	if !exists {
		return false
	}

	// If no valid next states, this is a terminal state
	if len(validNextStates) == 0 {
		return false
	}

	// Check if the target state is in the valid next states
	for _, validState := range validNextStates {
		if validState == to {
			return true
		}
	}

	return false
}
