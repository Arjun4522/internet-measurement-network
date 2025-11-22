package store

import (
	"context"
	"encoding/json"

	"github.com/internet-measurement-network/dbos/internal/models"
	"github.com/internet-measurement-network/dbos/pkg/redis"
)

// AgentStore manages agent persistence
type AgentStore struct {
	redis *redis.Client
}

// NewAgentStore creates a new agent store
func NewAgentStore(redis *redis.Client) *AgentStore {
	return &AgentStore{
		redis: redis,
	}
}

// RegisterAgent stores an agent in the database
func (s *AgentStore) RegisterAgent(ctx context.Context, agent *models.Agent) error {
	return s.redis.SetAgent(ctx, agent.ID, agent)
}

// GetAgent retrieves an agent from the database
func (s *AgentStore) GetAgent(ctx context.Context, agentID string) (*models.Agent, error) {
	data, err := s.redis.GetAgent(ctx, agentID)
	if err != nil {
		return nil, err
	}

	var agent models.Agent
	if err := json.Unmarshal(data, &agent); err != nil {
		return nil, err
	}

	return &agent, nil
}

// ListAgents retrieves all agents from the database
func (s *AgentStore) ListAgents(ctx context.Context) ([]*models.Agent, error) {
	agentsData, err := s.redis.GetAllAgents(ctx)
	if err != nil {
		return nil, err
	}

	agents := make([]*models.Agent, 0, len(agentsData))
	for _, data := range agentsData {
		var agent models.Agent
		if err := json.Unmarshal(data, &agent); err != nil {
			continue
		}
		agents = append(agents, &agent)
	}

	return agents, nil
}
