package store

import (
	"context"
	"encoding/json"

	"github.com/internet-measurement-network/dbos/internal/models"
	"github.com/internet-measurement-network/dbos/pkg/redis"
)

// ModuleStateStore manages module state persistence
type ModuleStateStore struct {
	redis *redis.Client
}

// NewModuleStateStore creates a new module state store
func NewModuleStateStore(redis *redis.Client) *ModuleStateStore {
	return &ModuleStateStore{
		redis: redis,
	}
}

// SetModuleState stores a module state in the database
func (s *ModuleStateStore) SetModuleState(ctx context.Context, state *models.ModuleState) error {
	return s.redis.SetModuleState(ctx, state.RequestID, state)
}

// GetModuleState retrieves a module state from the database
func (s *ModuleStateStore) GetModuleState(ctx context.Context, requestID string) (*models.ModuleState, error) {
	data, err := s.redis.GetModuleState(ctx, requestID)
	if err != nil {
		return nil, err
	}

	var state models.ModuleState
	if err := json.Unmarshal(data, &state); err != nil {
		return nil, err
	}

	return &state, nil
}

// ListModuleStates retrieves all module states for an agent and module from the database
func (s *ModuleStateStore) ListModuleStates(ctx context.Context, agentID, moduleName string) ([]*models.ModuleState, error) {
	statesData, err := s.redis.GetModuleStatesByAgent(ctx, agentID, moduleName)
	if err != nil {
		return nil, err
	}

	states := make([]*models.ModuleState, 0, len(statesData))
	for _, data := range statesData {
		var state models.ModuleState
		if err := json.Unmarshal(data, &state); err != nil {
			continue
		}
		states = append(states, &state)
	}

	return states, nil
}
