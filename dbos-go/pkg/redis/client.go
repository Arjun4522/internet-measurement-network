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

// SetModuleState stores a module state in Redis
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

// StoreResult stores a measurement result in Redis
func (c *Client) StoreResult(ctx context.Context, agentID, requestID string, result interface{}) error {
	key := fmt.Sprintf("result:%s:%s", agentID, requestID)
	data, err := json.Marshal(result)
	if err != nil {
		return err
	}

	// Also store in a sorted set for efficient querying by agent
	score := float64(time.Now().Unix())
	setKey := fmt.Sprintf("results:%s", agentID)
	c.client.ZAdd(ctx, setKey, &redis.Z{
		Score:  score,
		Member: key,
	})

	return c.client.Set(ctx, key, data, 0).Err()
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

// ScheduleTask schedules a task in Redis
func (c *Client) ScheduleTask(ctx context.Context, taskID string, task interface{}, scheduledAt time.Time) error {
	key := fmt.Sprintf("task:%s", taskID)
	data, err := json.Marshal(task)
	if err != nil {
		return err
	}

	// Store in a sorted set for efficient querying of due tasks
	score := float64(scheduledAt.Unix())
	c.client.ZAdd(ctx, "tasks:scheduled", &redis.Z{
		Score:  score,
		Member: key,
	})

	return c.client.Set(ctx, key, data, 0).Err()
}

// GetTask retrieves a task from Redis
func (c *Client) GetTask(ctx context.Context, taskID string) ([]byte, error) {
	key := fmt.Sprintf("task:%s", taskID)
	return c.client.Get(ctx, key).Bytes()
}

// GetDueTasks retrieves all due tasks from Redis
func (c *Client) GetDueTasks(ctx context.Context, timestamp time.Time) (map[string][]byte, error) {
	score := float64(timestamp.Unix())
	keys, err := c.client.ZRangeByScore(ctx, "tasks:scheduled", &redis.ZRangeBy{
		Min: "0",
		Max: fmt.Sprintf("%f", score),
	}).Result()
	if err != nil {
		return nil, err
	}

	tasks := make(map[string][]byte)
	for _, key := range keys {
		// Remove the prefix to get the actual key
		actualKey := key
		if len(key) > 5 {
			actualKey = key[5:] // Remove "task:" prefix
		}

		data, err := c.client.Get(ctx, actualKey).Bytes()
		if err != nil {
			continue
		}
		tasks[actualKey] = data
	}

	return tasks, nil
}
