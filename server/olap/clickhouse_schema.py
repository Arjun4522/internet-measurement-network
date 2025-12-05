"""
ClickHouse database schema for storing measurement results and analytics
"""
from datetime import datetime
from typing import Dict, Any, Optional, List

# ClickHouse table schemas - Each statement must be executed separately
CREATE_TABLE_STATEMENTS = [
    # Measurements table
    """CREATE TABLE IF NOT EXISTS measurements (
        workflow_id String,
        agent_id String,
        module_name String,
        created_at DateTime64(3, 'UTC'),
        completed_at DateTime64(3, 'UTC'),
        measurement_data String,
        agent_hostname String,
        agent_name String,
        agent_pid UInt32,
        system_machine String,
        system_node_name String,
        system_platform String,
        system_processor String,
        system_release String,
        system_version String,
        network_interfaces String,
        user_name String,
        user_uid UInt32,
        user_gid UInt32,
        user_home_dir String,
        user_shell String,
        request_data String,
        success Boolean,
        INDEX idx_workflow_id workflow_id TYPE bloom_filter GRANULARITY 1,
        INDEX idx_agent_id agent_id TYPE bloom_filter GRANULARITY 1,
        INDEX idx_module_name module_name TYPE bloom_filter GRANULARITY 1,
        INDEX idx_created_at created_at TYPE minmax GRANULARITY 1
    ) ENGINE = MergeTree()
    ORDER BY (created_at, agent_id, module_name)
    PARTITION BY toYYYYMM(created_at)""",
    
    # Agent heartbeats table
    """CREATE TABLE IF NOT EXISTS agent_heartbeats (
        agent_id String,
        agent_name String,
        hostname String,
        timestamp DateTime64(3, 'UTC'),
        alive Boolean,
        total_heartbeats UInt32,
        load_avg_1m Float32,
        load_avg_5m Float32,
        load_avg_15m Float32,
        config String,
        INDEX idx_agent_id agent_id TYPE bloom_filter GRANULARITY 1,
        INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 1
    ) ENGINE = MergeTree()
    ORDER BY (timestamp, agent_id)
    PARTITION BY toYYYYMM(timestamp)""",
    
    # Module states table
    """CREATE TABLE IF NOT EXISTS module_states (
        workflow_id String,
        agent_id String,
        module_name String,
        state String,
        timestamp DateTime64(3, 'UTC'),
        error_message Nullable(String),
        details String,
        INDEX idx_workflow_id workflow_id TYPE bloom_filter GRANULARITY 1,
        INDEX idx_agent_id agent_id TYPE bloom_filter GRANULARITY 1,
        INDEX idx_module_name module_name TYPE bloom_filter GRANULARITY 1,
        INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 1
    ) ENGINE = MergeTree()
    ORDER BY (timestamp, agent_id, module_name)
    PARTITION BY toYYYYMM(timestamp)""",
    
    # Daily statistics table
    """CREATE TABLE IF NOT EXISTS daily_stats (
        date Date,
        agent_id String,
        module_name String,
        total_executions UInt32,
        successful_executions UInt32,
        failed_executions UInt32,
        avg_execution_time Float32,
        INDEX idx_date date TYPE minmax GRANULARITY 1,
        INDEX idx_agent_id agent_id TYPE bloom_filter GRANULARITY 1
    ) ENGINE = MergeTree()
    ORDER BY (date, agent_id, module_name)"""
]

# Table descriptions for documentation
TABLE_DESCRIPTIONS = {
    "measurements": """
    Main fact table storing all measurement results with comprehensive metadata.
    Includes denormalized agent information for efficient querying.
    """,
    
    "agent_heartbeats": """
    Historical table storing agent heartbeat information for monitoring and analytics.
    """,
    
    "module_states": """
    Table tracking all module state transitions for workflow monitoring.
    """,
    
    "daily_stats": """
    Aggregated daily statistics for quick dashboard queries.
    """
}

# Sample data structures for reference
SAMPLE_DATA_STRUCTURES = {
    "measurement_result": {
        "workflow_id": "uuid-string",
        "agent_id": "uuid-string",
        "module_name": "ping_module",
        "created_at": "2023-01-01 12:00:00.000",
        "completed_at": "2023-01-01 12:00:01.234",
        "measurement_data": '{"address": "8.8.8.8", "rtts": [12.3, 15.1, 11.8], "packets_sent": 3, "packets_received": 3}',
        "agent_hostname": "agent-host-1",
        "agent_name": "aiori_1",
        "agent_pid": 12345,
        "system_machine": "x86_64",
        "system_node_name": "agent-host-1",
        "system_platform": "Linux-5.4.0",
        "system_processor": "x86_64",
        "system_release": "5.4.0-42-generic",
        "system_version": "#46-Ubuntu SMP",
        "network_interfaces": '{"eth0": {"ipv4": ["192.168.1.10"], "ipv6": [], "mac": ["aa:bb:cc:dd:ee:ff"]}}',
        "user_name": "agent-user",
        "user_uid": 1000,
        "user_gid": 1000,
        "user_home_dir": "/home/agent-user",
        "user_shell": "/bin/bash",
        "request_data": '{"host": "8.8.8.8", "count": 3}',
        "success": True
    },
    
    "agent_heartbeat": {
        "agent_id": "uuid-string",
        "agent_name": "aiori_1",
        "hostname": "agent-host-1",
        "timestamp": "2023-01-01 12:00:00.000",
        "alive": True,
        "total_heartbeats": 42,
        "load_avg_1m": 0.15,
        "load_avg_5m": 0.12,
        "load_avg_15m": 0.08,
        "config": '{"modules": ["ping_module", "echo_module"], "interval": 5}'
    },
    
    "module_state": {
        "workflow_id": "uuid-string",
        "agent_id": "uuid-string",
        "module_name": "ping_module",
        "state": "COMPLETED",
        "timestamp": "2023-01-01 12:00:00.000",
        "error_message": None,
        "details": '{"action": "request_completed"}'
    }
}