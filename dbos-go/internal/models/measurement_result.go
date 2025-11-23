package models

import (
	"time"
)

// MeasurementResult represents a network measurement result with metadata
type MeasurementResult struct {
	ID                  string    `json:"id"`
	AgentID             string    `json:"agent_id"`
	ModuleName          string    `json:"module_name"`
	Data                []byte    `json:"data"` // JSON-encoded result data
	Timestamp           time.Time `json:"timestamp"`
	ReceivedAt          time.Time `json:"received_at"`           // When the result was received
	AgentStartTime      time.Time `json:"agent_start_time"`      // When the agent started
	AgentRuntimeVersion string    `json:"agent_runtime_version"` // Agent runtime version
	ModuleRevision      string    `json:"module_revision"`       // Module revision
	DBOSServerID        string    `json:"dbos_server_id"`        // DBOS server ID
	IngestSource        string    `json:"ingest_source"`         // Source of the ingestion
}

// NewMeasurementResult creates a new measurement result instance
func NewMeasurementResult(id, agentID, moduleName string, data []byte) *MeasurementResult {
	return &MeasurementResult{
		ID:                  id,
		AgentID:             agentID,
		ModuleName:          moduleName,
		Data:                data,
		Timestamp:           time.Now(),
		ReceivedAt:          time.Now(),
		AgentStartTime:      time.Time{},
		AgentRuntimeVersion: "",
		ModuleRevision:      "",
		DBOSServerID:        "",
		IngestSource:        "",
	}
}
