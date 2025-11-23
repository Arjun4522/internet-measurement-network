package store

import (
	"context"
	"encoding/json"
	"time"

	"github.com/internet-measurement-network/dbos/internal/models"
	"github.com/internet-measurement-network/dbos/pkg/redis"
)

// TaskStore manages task persistence
type TaskStore struct {
	redis *redis.Client
}

// NewTaskStore creates a new task store
func NewTaskStore(redis *redis.Client) *TaskStore {
	return &TaskStore{
		redis: redis,
	}
}

// ScheduleTask schedules a task in the database
func (s *TaskStore) ScheduleTask(ctx context.Context, task *models.Task) error {
	return s.redis.ScheduleTask(ctx, task.ID, task, task.ScheduledAt)
}

// GetTask retrieves a task from the database
func (s *TaskStore) GetTask(ctx context.Context, taskID string) (*models.Task, error) {
	data, err := s.redis.GetTask(ctx, taskID)
	if err != nil {
		return nil, err
	}

	var task models.Task
	if err := json.Unmarshal(data, &task); err != nil {
		return nil, err
	}

	return &task, nil
}

// ListDueTasks retrieves all due tasks from the database with visibility timeout
func (s *TaskStore) ListDueTasks(ctx context.Context, timestamp time.Time) ([]*models.Task, error) {
	tasksData, err := s.redis.GetDueTasks(ctx, timestamp, 5*time.Minute) // 5-minute visibility timeout
	if err != nil {
		return nil, err
	}

	tasks := make([]*models.Task, 0, len(tasksData))
	for _, data := range tasksData {
		var task models.Task
		if err := json.Unmarshal(data, &task); err != nil {
			continue
		}
		tasks = append(tasks, &task)
	}

	return tasks, nil
}

// AckTask acknowledges completion of a task
func (s *TaskStore) AckTask(ctx context.Context, taskID string) error {
	return s.redis.AckTask(ctx, taskID)
}

// NackTask negatively acknowledges a task, moving it back to pending
func (s *TaskStore) NackTask(ctx context.Context, taskID string, retryDelay time.Duration) error {
	return s.redis.NackTask(ctx, taskID, retryDelay)
}

// RequeueExpiredTasks moves expired inflight tasks back to pending
func (s *TaskStore) RequeueExpiredTasks(ctx context.Context, timestamp time.Time) error {
	return s.redis.RequeueExpiredTasks(ctx, timestamp)
}
