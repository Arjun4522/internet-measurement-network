package redis

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/go-redis/redis/v8"
)

// Client wraps the Redis client with convenience methods
type Client struct {
	client *redis.Client
}

// NewClient creates a new Redis client
func NewClient(addr string) *Client {
	rdb := redis.NewClient(&redis.Options{
		Addr: addr,
	})

	return &Client{
		client: rdb,
	}
}

// Close closes the Redis connection
func (c *Client) Close() error {
	return c.client.Close()
}

// Ping checks if the Redis connection is alive
func (c *Client) Ping(ctx context.Context) error {
	return c.client.Ping(ctx).Err()
}

// SetAgent stores an agent in Redis
func (c *Client) SetAgent(ctx context.Context, agentID string, agent interface{}) error {
	key := fmt.Sprintf("agent:%s", agentID)
	data, err := json.Marshal(agent)
	if err != nil {
		return err
	}

	return c.client.Set(ctx, key, data, 0).Err()
}

// GetAgent retrieves an agent from Redis
func (c *Client) GetAgent(ctx context.Context, agentID string) ([]byte, error) {
	key := fmt.Sprintf("agent:%s", agentID)
	return c.client.Get(ctx, key).Bytes()
}

// GetAllAgents retrieves all agents from Redis
func (c *Client) GetAllAgents(ctx context.Context) (map[string][]byte, error) {
	keys, err := c.client.Keys(ctx, "agent:*").Result()
	if err != nil {
		return nil, err
	}

	agents := make(map[string][]byte)
	for _, key := range keys {
		data, err := c.client.Get(ctx, key).Bytes()
		if err != nil {
			continue
		}
		agents[key] = data
	}

	return agents, nil
}

// SetModuleState stores a module state in Redis with versioning
func (c *Client) SetModuleState(ctx context.Context, requestID string, state interface{}) error {
	key := fmt.Sprintf("module_state:%s", requestID)
	data, err := json.Marshal(state)
	if err != nil {
		return err
	}

	// Also store in a sorted set for efficient querying by agent and module
	stateMap, ok := state.(map[string]interface{})
	if ok {
		if agentID, ok := stateMap["agent_id"].(string); ok {
			if moduleName, ok := stateMap["module_name"].(string); ok {
				score := float64(time.Now().Unix())
				setKey := fmt.Sprintf("module_states:%s:%s", agentID, moduleName)
				c.client.ZAdd(ctx, setKey, &redis.Z{
					Score:  score,
					Member: key,
				})
			}
		}
	}

	return c.client.Set(ctx, key, data, 0).Err()
}

// SetModuleStateWithVersion stores a module state in Redis with optimistic concurrency control
func (c *Client) SetModuleStateWithVersion(ctx context.Context, requestID string, state interface{}, expectedVersion int64) error {
	// First, get the current state to check version
	currentKey := fmt.Sprintf("module_state:%s", requestID)
	currentData, err := c.client.Get(ctx, currentKey).Bytes()
	if err != nil && err != redis.Nil {
		return err
	}

	// If there's existing data, unmarshal it to check version
	if err != redis.Nil {
		var currentState map[string]interface{}
		if unmarshalErr := json.Unmarshal(currentData, &currentState); unmarshalErr == nil {
			if currentVersion, ok := currentState["version"].(float64); ok {
				if int64(currentVersion) != expectedVersion {
					return fmt.Errorf("version conflict: expected %d, got %d", expectedVersion, int64(currentVersion))
				}
			}
		}
	}

	// Proceed with storing the new state
	key := fmt.Sprintf("module_state:%s", requestID)
	data, err := json.Marshal(state)
	if err != nil {
		return err
	}

	// Also store in a sorted set for efficient querying by agent and module
	stateMap, ok := state.(map[string]interface{})
	if ok {
		if agentID, ok := stateMap["agent_id"].(string); ok {
			if moduleName, ok := stateMap["module_name"].(string); ok {
				score := float64(time.Now().Unix())
				setKey := fmt.Sprintf("module_states:%s:%s", agentID, moduleName)
				c.client.ZAdd(ctx, setKey, &redis.Z{
					Score:  score,
					Member: key,
				})
			}
		}
	}

	return c.client.Set(ctx, key, data, 0).Err()
}

// GetModuleState retrieves a module state from Redis
func (c *Client) GetModuleState(ctx context.Context, requestID string) ([]byte, error) {
	key := fmt.Sprintf("module_state:%s", requestID)
	return c.client.Get(ctx, key).Bytes()
}

// GetModuleStatesByAgent retrieves all module states for an agent from Redis
func (c *Client) GetModuleStatesByAgent(ctx context.Context, agentID, moduleName string) (map[string][]byte, error) {
	setKey := fmt.Sprintf("module_states:%s:%s", agentID, moduleName)
	keys, err := c.client.ZRange(ctx, setKey, 0, -1).Result()
	if err != nil {
		return nil, err
	}

	states := make(map[string][]byte)
	for _, key := range keys {
		data, err := c.client.Get(ctx, key).Bytes()
		if err != nil {
			continue
		}
		states[key] = data
	}

	return states, nil
}

// StoreResult stores a measurement result in Redis with idempotency protection
func (c *Client) StoreResult(ctx context.Context, agentID, requestID string, result interface{}) error {
	// Check if this request ID has already been processed (idempotency)
	idempotencyKey := fmt.Sprintf("processed:%s", requestID)
	exists, err := c.client.Exists(ctx, idempotencyKey).Result()
	if err != nil {
		return err
	}

	// If already processed, return success without storing again
	if exists > 0 {
		return nil
	}

	key := fmt.Sprintf("result:%s:%s", agentID, requestID)
	data, err := json.Marshal(result)
	if err != nil {
		return err
	}

	// Also store in a sorted set for efficient querying by agent
	score := float64(time.Now().Unix())
	setKey := fmt.Sprintf("results:%s", agentID)
	err = c.client.ZAdd(ctx, setKey, &redis.Z{
		Score:  score,
		Member: key,
	}).Err()
	if err != nil {
		return err
	}

	// Store the result
	err = c.client.Set(ctx, key, data, 0).Err()
	if err != nil {
		return err
	}

	// Mark this request ID as processed for idempotency (expires after 24 hours)
	return c.client.Set(ctx, idempotencyKey, "1", 24*time.Hour).Err()
}

// GetResult retrieves a measurement result from Redis
func (c *Client) GetResult(ctx context.Context, agentID, requestID string) ([]byte, error) {
	key := fmt.Sprintf("result:%s:%s", agentID, requestID)
	return c.client.Get(ctx, key).Bytes()
}

// GetResultsByAgent retrieves all results for an agent from Redis
func (c *Client) GetResultsByAgent(ctx context.Context, agentID string) (map[string][]byte, error) {
	setKey := fmt.Sprintf("results:%s", agentID)
	keys, err := c.client.ZRange(ctx, setKey, 0, -1).Result()
	if err != nil {
		return nil, err
	}

	results := make(map[string][]byte)
	for _, key := range keys {
		data, err := c.client.Get(ctx, key).Bytes()
		if err != nil {
			continue
		}
		results[key] = data
	}

	return results, nil
}

// ScheduleTask schedules a task in Redis with visibility timeout support
func (c *Client) ScheduleTask(ctx context.Context, taskID string, task interface{}, scheduledAt time.Time) error {
	key := fmt.Sprintf("task:%s", taskID)
	data, err := json.Marshal(task)
	if err != nil {
		return err
	}

	// Store the task
	err = c.client.Set(ctx, key, data, 0).Err()
	if err != nil {
		return err
	}

	// Add to pending tasks sorted set for efficient querying of due tasks
	score := float64(scheduledAt.Unix())
	return c.client.ZAdd(ctx, "tasks:pending", &redis.Z{
		Score:  score,
		Member: key,
	}).Err()
}

// GetTask retrieves a task from Redis
func (c *Client) GetTask(ctx context.Context, taskID string) ([]byte, error) {
	key := fmt.Sprintf("task:%s", taskID)
	return c.client.Get(ctx, key).Bytes()
}

// GetDueTasks retrieves all due tasks from Redis and moves them to inflight with visibility timeout
func (c *Client) GetDueTasks(ctx context.Context, timestamp time.Time, visibilityTimeout time.Duration) (map[string][]byte, error) {
	// Get tasks that are due
	score := float64(timestamp.Unix())
	keys, err := c.client.ZRangeByScore(ctx, "tasks:pending", &redis.ZRangeBy{
		Min: "0",
		Max: fmt.Sprintf("%f", score),
	}).Result()
	if err != nil {
		return nil, err
	}

	tasks := make(map[string][]byte)
	visibilityTime := time.Now().Add(visibilityTimeout)

	for _, key := range keys {
		// Move task from pending to inflight
		taskKey := key
		if len(key) > 5 {
			taskKey = key[5:] // Remove "task:" prefix
		}

		// Get the task data
		data, err := c.client.Get(ctx, taskKey).Bytes()
		if err != nil {
			continue
		}

		// Remove from pending set
		c.client.ZRem(ctx, "tasks:pending", key)

		// Add to inflight set with visibility timeout
		inflightScore := float64(visibilityTime.Unix())
		c.client.ZAdd(ctx, "tasks:inflight", &redis.Z{
			Score:  inflightScore,
			Member: key,
		})

		tasks[taskKey] = data
	}

	return tasks, nil
}

// AckTask acknowledges completion of a task and removes it from inflight
func (c *Client) AckTask(ctx context.Context, taskID string) error {
	key := fmt.Sprintf("task:%s", taskID)

	// Remove from inflight set
	c.client.ZRem(ctx, "tasks:inflight", key)

	// Delete the task entirely (since it's completed)
	return c.client.Del(ctx, key).Err()
}

// NackTask negatively acknowledges a task, moving it back to pending with retry handling
func (c *Client) NackTask(ctx context.Context, taskID string, retryDelay time.Duration) error {
	key := fmt.Sprintf("task:%s", taskID)

	// Remove from inflight set
	c.client.ZRem(ctx, "tasks:inflight", key)

	// Move back to pending with retry delay
	retryTime := time.Now().Add(retryDelay)
	score := float64(retryTime.Unix())
	return c.client.ZAdd(ctx, "tasks:pending", &redis.Z{
		Score:  score,
		Member: key,
	}).Err()
}

// RequeueExpiredTasks moves expired inflight tasks back to pending
func (c *Client) RequeueExpiredTasks(ctx context.Context, timestamp time.Time) error {
	// Get expired inflight tasks
	score := float64(timestamp.Unix())
	keys, err := c.client.ZRangeByScore(ctx, "tasks:inflight", &redis.ZRangeBy{
		Min: "0",
		Max: fmt.Sprintf("%f", score),
	}).Result()
	if err != nil {
		return err
	}

	// Move expired tasks back to pending
	for _, key := range keys {
		// Remove from inflight
		c.client.ZRem(ctx, "tasks:inflight", key)

		// Add back to pending with a small delay to prevent immediate reprocessing
		retryTime := time.Now().Add(5 * time.Second)
		score := float64(retryTime.Unix())
		c.client.ZAdd(ctx, "tasks:pending", &redis.Z{
			Score:  score,
			Member: key,
		})
	}

	return nil
}

// LogEvent logs an event to a Redis list for durable event logging
func (c *Client) LogEvent(ctx context.Context, eventType, message string, metadata map[string]interface{}) error {
	event := map[string]interface{}{
		"type":      eventType,
		"message":   message,
		"metadata":  metadata,
		"timestamp": time.Now().Unix(),
	}

	data, err := json.Marshal(event)
	if err != nil {
		return err
	}

	// Push to a Redis list for durable event logging
	return c.client.LPush(ctx, "events:log", data).Err()
}

// GetEvents retrieves recent events from the event log
func (c *Client) GetEvents(ctx context.Context, limit int64) ([][]byte, error) {
	strings, err := c.client.LRange(ctx, "events:log", 0, limit-1).Result()
	if err != nil {
		return nil, err
	}

	// Convert []string to [][]byte
	events := make([][]byte, len(strings))
	for i, s := range strings {
		events[i] = []byte(s)
	}

	return events, nil
}
