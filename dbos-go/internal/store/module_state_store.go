package store

import (
	"context"
	"encoding/json"
	"fmt"

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

// SetModuleState stores a module state in the database with validation
func (s *ModuleStateStore) SetModuleState(ctx context.Context, state *models.ModuleState) error {
	// Validate state transition if this is an update
	if state.RequestID != "" {
		currentState, err := s.GetModuleState(ctx, state.RequestID)
		if err == nil {
			// Validate the state transition
			if !models.IsValidTransition(models.ModuleStateEnum(currentState.State), models.ModuleStateEnum(state.State)) {
				return fmt.Errorf("invalid state transition from %s to %s", currentState.State, state.State)
			}

			// Increment version for updates
			state.Version = currentState.Version + 1
		} else {
			// This is a new state, set initial version
			state.Version = 1
		}
	} else {
		// This is a new state, set initial version
		state.Version = 1
	}

	return s.redis.SetModuleState(ctx, state.RequestID, state)
}

// SetModuleStateWithVersion stores a module state in the database with version checking
func (s *ModuleStateStore) SetModuleStateWithVersion(ctx context.Context, state *models.ModuleState, expectedVersion int64) error {
	// Validate state transition if this is an update
	if state.RequestID != "" {
		currentState, err := s.GetModuleState(ctx, state.RequestID)
		if err == nil {
			// Validate the state transition
			if !models.IsValidTransition(models.ModuleStateEnum(currentState.State), models.ModuleStateEnum(state.State)) {
				return fmt.Errorf("invalid state transition from %s to %s", currentState.State, state.State)
			}
		}
	}

	return s.redis.SetModuleStateWithVersion(ctx, state.RequestID, state, expectedVersion)
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
