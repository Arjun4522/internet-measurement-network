package models

import (
	"time"
)

// MeasurementResult represents a network measurement result
type MeasurementResult struct {
	ID         string    `json:"id"`
	AgentID    string    `json:"agent_id"`
	ModuleName string    `json:"module_name"`
	Data       []byte    `json:"data"` // JSON-encoded result data
	Timestamp  time.Time `json:"timestamp"`
}

// NewMeasurementResult creates a new measurement result instance
func NewMeasurementResult(id, agentID, moduleName string, data []byte) *MeasurementResult {
	return &MeasurementResult{
		ID:         id,
		AgentID:    agentID,
		ModuleName: moduleName,
		Data:       data,
		Timestamp:  time.Now(),
	}
}
