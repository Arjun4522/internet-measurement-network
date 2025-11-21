package store

import (
	"context"
	"encoding/json"

	"github.com/internet-measurement-network/dbos/internal/models"
	"github.com/internet-measurement-network/dbos/pkg/redis"
)

// ResultStore manages measurement result persistence
type ResultStore struct {
	redis *redis.Client
}

// NewResultStore creates a new result store
func NewResultStore(redis *redis.Client) *ResultStore {
	return &ResultStore{
		redis: redis,
	}
}

// StoreResult stores a measurement result in the database
func (s *ResultStore) StoreResult(ctx context.Context, result *models.MeasurementResult) error {
	return s.redis.StoreResult(ctx, result.AgentID, result.ID, result)
}

// GetResult retrieves a measurement result from the database
func (s *ResultStore) GetResult(ctx context.Context, agentID, requestID string) (*models.MeasurementResult, error) {
	data, err := s.redis.GetResult(ctx, agentID, requestID)
	if err != nil {
		return nil, err
	}

	var result models.MeasurementResult
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, err
	}

	return &result, nil
}

// ListResults retrieves all results for an agent from the database
func (s *ResultStore) ListResults(ctx context.Context, agentID string) ([]*models.MeasurementResult, error) {
	resultsData, err := s.redis.GetResultsByAgent(ctx, agentID)
	if err != nil {
		return nil, err
	}

	results := make([]*models.MeasurementResult, 0, len(resultsData))
	for _, data := range resultsData {
		var result models.MeasurementResult
		if err := json.Unmarshal(data, &result); err != nil {
			continue
		}
		results = append(results, &result)
	}

	return results, nil
}
