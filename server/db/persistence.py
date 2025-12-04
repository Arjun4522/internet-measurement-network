"""
Database persistence layer for AgentCache and WorkflowState
"""
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

# Handle relative imports
try:
    from models import AgentInfo
except ImportError:
    try:
        # Try alternative import path
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from models import AgentInfo
    except ImportError:
        # Create a dummy AgentInfo for type hints if import fails
        from typing import NamedTuple
        class AgentInfo(NamedTuple):
            agent_id: str
            alive: bool
            hostname: str
            last_seen: datetime
            config: Dict[str, Any]
            first_seen: datetime
            total_heartbeats: int

class PersistenceManager:
    """Manages persistence of agent and workflow state data"""
    
    def __init__(self, db_url: str = ""):
        self.db_url = db_url or os.environ.get("DBOS_SYSTEM_DATABASE_URL", "postgresql://imn_user:imn_password@postgres:5432/imn_db")
        self.init_tables()
    
    def get_connection(self):
        """Get database connection"""
        return psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
    
    def init_tables(self):
        """Initialize database tables for custom persistence"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Create agents table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS persistent_agents (
                    agent_id VARCHAR(255) PRIMARY KEY,
                    alive BOOLEAN NOT NULL,
                    hostname VARCHAR(255) NOT NULL,
                    last_seen TIMESTAMP NOT NULL,
                    config JSONB NOT NULL,
                    first_seen TIMESTAMP NOT NULL,
                    total_heartbeats INTEGER NOT NULL
                )
            ''')
            
            # Create workflows table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS persistent_workflows (
                    workflow_id VARCHAR(255) PRIMARY KEY,
                    agent_id VARCHAR(255) NOT NULL,
                    module_name VARCHAR(255) NOT NULL,
                    request JSONB NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
            ''')
            
            # Create workflow state history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS persistent_workflow_states (
                    id SERIAL PRIMARY KEY,
                    workflow_id VARCHAR(255) NOT NULL,
                    state VARCHAR(50) NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    metadata JSONB,
                    FOREIGN KEY (workflow_id) REFERENCES persistent_workflows (workflow_id)
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_persistent_agents_alive 
                ON persistent_agents (alive)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_persistent_workflows_agent 
                ON persistent_workflows (agent_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_persistent_workflow_states_workflow 
                ON persistent_workflow_states (workflow_id)
            ''')
            
            conn.commit()
        except Exception as e:
            # Log the error but don't fail - tables might already exist
            print(f"Warning: Error initializing tables: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def save_agent(self, agent: AgentInfo):
        """Save agent to database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO persistent_agents 
            (agent_id, alive, hostname, last_seen, config, first_seen, total_heartbeats)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (agent_id) 
            DO UPDATE SET 
                alive = EXCLUDED.alive,
                hostname = EXCLUDED.hostname,
                last_seen = EXCLUDED.last_seen,
                config = EXCLUDED.config,
                total_heartbeats = EXCLUDED.total_heartbeats
        ''', (
            agent.agent_id,
            agent.alive,
            agent.hostname,
            agent.last_seen,
            json.dumps(agent.config),
            agent.first_seen,
            agent.total_heartbeats
        ))
        
        conn.commit()
        conn.close()
    
    def load_agents(self) -> Dict[str, AgentInfo]:
        """Load all agents from database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM persistent_agents')
        rows = cursor.fetchall()
        
        agents = {}
        for row in rows:
            agent_id, alive, hostname, last_seen, config, first_seen, total_heartbeats = row
            
            agent = AgentInfo(
                agent_id=agent_id,
                alive=bool(alive),
                hostname=hostname,
                last_seen=datetime.fromisoformat(last_seen),
                config=json.loads(config) if config else {},
                first_seen=datetime.fromisoformat(first_seen),
                total_heartbeats=total_heartbeats
            )
            agents[agent_id] = agent
        
        conn.close()
        return agents
    
    def delete_agent(self, agent_id: str):
        """Delete agent from database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM persistent_agents WHERE agent_id = %s', (agent_id,))
        
        conn.commit()
        conn.close()
    
    def save_workflow(self, workflow_id: str, workflow_data: Dict[str, Any]):
        """Save workflow to database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO persistent_workflows 
            (workflow_id, agent_id, module_name, request, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (workflow_id) 
            DO UPDATE SET 
                agent_id = EXCLUDED.agent_id,
                module_name = EXCLUDED.module_name,
                request = EXCLUDED.request,
                created_at = EXCLUDED.created_at
        ''', (
            workflow_id,
            workflow_data.get("agent_id", ""),
            workflow_data.get("module_name", ""),
            json.dumps(workflow_data.get("request", {})),
            workflow_data.get("created_at", "")
        ))
        
        conn.commit()
        conn.close()
    
    def save_workflow_state(self, workflow_id: str, state: str, timestamp: str, metadata: Optional[Dict[str, Any]] = None):
        """Save workflow state transition to database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO persistent_workflow_states 
            (workflow_id, state, timestamp, metadata)
            VALUES (%s, %s, %s, %s)
        ''', (
            workflow_id,
            state,
            timestamp,
            json.dumps(metadata) if metadata else '{}'
        ))
        
        conn.commit()
        conn.close()
    
    def load_workflows(self) -> Dict[str, Dict[str, Any]]:
        """Load all workflows from database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM persistent_workflows')
        rows = cursor.fetchall()
        
        workflows = {}
        for row in rows:
            workflow_id, agent_id, module_name, request, created_at = row
            
            workflows[workflow_id] = {
                "agent_id": agent_id,
                "module_name": module_name,
                "request": json.loads(request) if request else {},
                "created_at": created_at
            }
        
        conn.close()
        return workflows
    
    def load_workflow_states(self) -> Dict[str, List[Dict]]:
        """Load all workflow states from database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT workflow_id, state, timestamp, metadata FROM persistent_workflow_states ORDER BY timestamp')
        rows = cursor.fetchall()
        
        states = {}
        for row in rows:
            workflow_id, state, timestamp, metadata = row
            
            if workflow_id not in states:
                states[workflow_id] = []
            
            state_entry = {
                "state": state,
                "timestamp": timestamp
            }
            
            if metadata:
                state_entry.update(json.loads(metadata))
            
            states[workflow_id].append(state_entry)
        
        conn.close()
        return states
    
    def delete_workflow(self, workflow_id: str):
        """Delete workflow from database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Delete states first (foreign key constraint)
        cursor.execute('DELETE FROM persistent_workflow_states WHERE workflow_id = %s', (workflow_id,))
        
        # Delete workflow
        cursor.execute('DELETE FROM persistent_workflows WHERE workflow_id = %s', (workflow_id,))
        
        conn.commit()
        conn.close()