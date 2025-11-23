package models

import (
	"time"
)

// Task represents a scheduled task with visibility timeout support
type Task struct {
	ID             string    `json:"id"`
	AgentID        string    `json:"agent_id"`
	ModuleName     string    `json:"module_name"`
	Payload        []byte    `json:"payload"` // JSON-encoded task payload
	ScheduledAt    time.Time `json:"scheduled_at"`
	CreatedAt      time.Time `json:"created_at"`
	Status         string    `json:"status"`
	VisibilityTime time.Time `json:"visibility_time"` // For visibility timeout
	RetryCount     int       `json:"retry_count"`     // For retry handling
}

// NewTask creates a new task instance
func NewTask(id, agentID, moduleName string, payload []byte, scheduledAt time.Time) *Task {
	return &Task{
		ID:             id,
		AgentID:        agentID,
		ModuleName:     moduleName,
		Payload:        payload,
		ScheduledAt:    scheduledAt,
		CreatedAt:      time.Now(),
		Status:         "pending",
		VisibilityTime: time.Time{}, // Zero time means not in flight
		RetryCount:     0,
	}
}

// TaskStatusEnum defines the possible statuses for a task
type TaskStatusEnum string

const (
	TaskStatusPending   TaskStatusEnum = "pending"
	TaskStatusRunning   TaskStatusEnum = "running"
	TaskStatusCompleted TaskStatusEnum = "completed"
	TaskStatusFailed    TaskStatusEnum = "failed"
)
