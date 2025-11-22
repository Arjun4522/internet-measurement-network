package models

import (
	"time"
)

// Agent represents a measurement agent in the system
type Agent struct {
	ID              string            `json:"id"`
	Hostname        string            `json:"hostname"`
	Alive           bool              `json:"alive"`
	LastSeen        time.Time         `json:"last_seen"`
	FirstSeen       time.Time         `json:"first_seen"`
	Config          map[string]string `json:"config"`
	TotalHeartbeats int32             `json:"total_heartbeats"`
}

// NewAgent creates a new agent instance
func NewAgent(id, hostname string) *Agent {
	return &Agent{
		ID:        id,
		Hostname:  hostname,
		Alive:     true,
		LastSeen:  time.Now(),
		FirstSeen: time.Now(),
		Config:    make(map[string]string),
	}
}
