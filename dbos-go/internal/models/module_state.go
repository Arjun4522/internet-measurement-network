package models

import (
	"time"
)

// ModuleState represents the state of a module execution
type ModuleState struct {
	AgentID      string            `json:"agent_id"`
	ModuleName   string            `json:"module_name"`
	State        string            `json:"state"`
	ErrorMessage string            `json:"error_message"`
	Details      map[string]string `json:"details"`
	Timestamp    time.Time         `json:"timestamp"`
	RequestID    string            `json:"request_id"`
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
	}
}

// ModuleStateEnum defines the possible states for a module
type ModuleStateEnum string

const (
	ModuleStateStarted   ModuleStateEnum = "started"
	ModuleStateRunning   ModuleStateEnum = "running"
	ModuleStateCompleted ModuleStateEnum = "completed"
	ModuleStateError     ModuleStateEnum = "error"
	ModuleStateFailed    ModuleStateEnum = "failed"
)
