import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Query, HTTPException
from dbos import DBOS, DBOSConfig, Queue
from nats_observe.config import NATSotelSettings
from nats_observe.client import Client as NATSotel
from nats.aio.msg import Msg
from openapi_schema_validator import validate
from jsonschema.exceptions import ValidationError

from models import AgentInfo, ModuleStateEnum
from db.persistence import PersistenceManager

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Centralized configuration"""
    NATS_URL = [os.environ.get("NATS_URL", "nats://localhost:4222")]
    HEARTBEAT_SUBJECT = "agent.heartbeat_module"
    HEARTBEAT_INTERVAL = 5
    HEARTBEAT_TIMEOUT = HEARTBEAT_INTERVAL * 2
    
    # OpenTelemetry endpoints
    OTLP_TRACE_ENDPOINT = os.environ.get("OTLP_TRACE_ENDPOINT", "otel-collector:4317")
    OTLP_METRICS_ENDPOINT = os.environ.get("OTLP_METRICS_ENDPOINT", "otel-collector:4317")
    OTLP_LOGS_ENDPOINT = os.environ.get("OTLP_LOGS_ENDPOINT", "otel-collector:4317")
    
    # Database
    DBOS_SYSTEM_DATABASE_URL = os.environ.get("DBOS_SYSTEM_DATABASE_URL", "sqlite:///db/data.db")

config = Config()

# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class WorkflowState:
    """Manages workflow state tracking with only 3 states: RUNNING, COMPLETED, FAILED"""
    def __init__(self):
        # workflow_id -> workflow metadata
        self.workflows: Dict[str, Dict[str, Any]] = {}
        # workflow_id -> list of state transitions
        self.state_history: Dict[str, list] = {}
        # workflow_id -> agent_id mapping for health checking
        self.workflow_agents: Dict[str, str] = {}
        # Add persistence
        self.persistence = PersistenceManager() if PersistenceManager else None
        self._load_persistent_workflows()
    
    def _load_persistent_workflows(self):
        """Load workflows from persistent storage on startup"""
        if self.persistence:
            try:
                persistent_workflows = self.persistence.load_workflows()
                self.workflows.update(persistent_workflows)
                
                persistent_states = self.persistence.load_workflow_states()
                self.state_history.update(persistent_states)
                
                print(f"[WorkflowState] Loaded {len(persistent_workflows)} workflows from persistent storage")
            except Exception as e:
                print(f"[WorkflowState] Warning: Could not load persistent workflows: {e}")
    
    def sync_with_database(self):
        """Sync in-memory cache with database"""
        if self.persistence:
            try:
                # Load fresh data from database
                fresh_workflows = self.persistence.load_workflows()
                fresh_states = self.persistence.load_workflow_states()
                
                # Update in-memory cache with any new/updated entries
                updated_count = 0
                for wf_id, wf_data in fresh_workflows.items():
                    if wf_id not in self.workflows:
                        self.workflows[wf_id] = wf_data
                        updated_count += 1
                    elif self.workflows[wf_id] != wf_data:
                        self.workflows[wf_id] = wf_data
                        updated_count += 1
                
                # Update state history
                for wf_id, states in fresh_states.items():
                    if wf_id not in self.state_history:
                        self.state_history[wf_id] = states
                        updated_count += 1
                    elif self.state_history[wf_id] != states:
                        self.state_history[wf_id] = states
                        updated_count += 1
                
                if updated_count > 0:
                    print(f"[WorkflowState] Synced {updated_count} updates from database")
                    
            except Exception as e:
                print(f"[WorkflowState] Warning: Could not sync with database: {e}")
    
    def create_workflow(self, workflow_id: str, agent_id: str, module_name: str, 
                       request: Dict[str, Any]) -> None:
        """Initialize a new workflow with RUNNING state"""
        workflow_data = {
            "agent_id": agent_id,
            "module_name": module_name,
            "request": request,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        self.workflows[workflow_id] = workflow_data
        self.workflow_agents[workflow_id] = agent_id  # Track which agent handles this workflow
        
        self.state_history[workflow_id] = [{
            "state": "RUNNING",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
        
        print(f"[Workflow] Created {workflow_id}: RUNNING")
        
        # Persist workflow data
        if hasattr(self, 'persistence') and self.persistence:
            try:
                self.persistence.save_workflow(workflow_id, workflow_data)
                self.persistence.save_workflow_state(
                    workflow_id, 
                    "RUNNING", 
                    datetime.now(timezone.utc).isoformat()
                )
            except Exception as e:
                print(f"[WorkflowState] Warning: Could not persist workflow {workflow_id}: {e}")
    
    def set_state(self, workflow_id: str, state: str, **metadata) -> None:
        """Set workflow state - only RUNNING, COMPLETED, or FAILED allowed"""
        if state not in ["RUNNING", "COMPLETED", "FAILED"]:
            raise ValueError(f"Invalid state: {state}. Must be RUNNING, COMPLETED, or FAILED")
        
        if workflow_id not in self.state_history:
            self.state_history[workflow_id] = []
        
        timestamp = datetime.now(timezone.utc).isoformat()
        state_entry = {
            "state": state,
            "timestamp": timestamp,
            **metadata
        }
        self.state_history[workflow_id].append(state_entry)
        print(f"[Workflow] {workflow_id}: {state}")
        
        # If workflow is completing/failing, remove from agent tracking
        if state in ["COMPLETED", "FAILED"] and workflow_id in self.workflow_agents:
            del self.workflow_agents[workflow_id]
        
        # Persist state transition
        if hasattr(self, 'persistence') and self.persistence:
            try:
                self.persistence.save_workflow_state(workflow_id, state, timestamp, metadata)
            except Exception as e:
                print(f"[WorkflowState] Warning: Could not persist state for {workflow_id}: {e}")
    
    def check_stale_workflows(self, agent_cache) -> None:
        """Check for workflows assigned to dead agents and mark them as failed"""
        try:
            # Get current running workflows
            running_workflows = []
            for workflow_id, states in self.state_history.items():
                if states and states[-1]["state"] == "RUNNING":
                    running_workflows.append(workflow_id)
            
            # Check if agents for these workflows are still alive
            for workflow_id in running_workflows:
                if workflow_id in self.workflow_agents:
                    agent_id = self.workflow_agents[workflow_id]
                    agent = agent_cache.get(agent_id)
                    
                    # If agent doesn't exist or is dead, mark workflow as failed
                    if not agent or not agent.alive:
                        print(f"[Workflow] Marking {workflow_id} as FAILED due to dead agent {agent_id}")
                        self.set_state(
                            workflow_id, 
                            "FAILED", 
                            reason="Agent died or disconnected",
                            agent_id=agent_id
                        )
        except Exception as e:
            print(f"[WorkflowState] Error checking stale workflows: {e}")
    
    def get_current_state(self, workflow_id: str) -> Optional[str]:
        """Get current state of a workflow"""
        history = self.state_history.get(workflow_id, [])
        return history[-1]["state"] if history else None

class AgentCache:
    """Manages agent lifecycle and metadata"""
    def __init__(self):
        self.agents: Dict[str, AgentInfo] = {}
        self.persistence = PersistenceManager() if PersistenceManager else None
        self._load_persistent_agents()
    
    def _load_persistent_agents(self):
        """Load agents from persistent storage on startup"""
        if self.persistence:
            try:
                persistent_agents = self.persistence.load_agents()
                for agent_id, agent in persistent_agents.items():
                    self.agents[agent_id] = agent
                print(f"[AgentCache] Loaded {len(persistent_agents)} agents from persistent storage")
            except Exception as e:
                print(f"[AgentCache] Warning: Could not load persistent agents: {e}")
    
    def sync_with_database(self):
        """Sync in-memory cache with database"""
        if self.persistence:
            try:
                # Load fresh data from database
                fresh_agents = self.persistence.load_agents()
                
                # Update in-memory cache with any new/updated entries
                updated_count = 0
                for agent_id, agent in fresh_agents.items():
                    if agent_id not in self.agents:
                        self.agents[agent_id] = agent
                        updated_count += 1
                    elif self.agents[agent_id] != agent:
                        self.agents[agent_id] = agent
                        updated_count += 1
                
                if updated_count > 0:
                    print(f"[AgentCache] Synced {updated_count} agent updates from database")
                    
            except Exception as e:
                print(f"[AgentCache] Warning: Could not sync with database: {e}")
    
    def update_heartbeat(self, agent_id: str, hostname: str, config: Dict[str, Any]) -> AgentInfo:
        """Update or create agent from heartbeat"""
        now = datetime.now(timezone.utc)
        
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            agent.last_seen = now
            agent.alive = True
            agent.config = config
            agent.total_heartbeats += 1
            print(f"[AgentCache] Updated: {agent_id}")
        else:
            agent = AgentInfo(
                agent_id=agent_id,
                alive=True,
                hostname=hostname,
                last_seen=now,
                config=config,
                first_seen=now,
                total_heartbeats=1
            )
            self.agents[agent_id] = agent
            print(f"[AgentCache] Registered: {agent_id}")
        
        # Persist agent data
        if hasattr(self, 'persistence') and self.persistence:
            try:
                self.persistence.save_agent(agent)
            except Exception as e:
                print(f"[AgentCache] Warning: Could not persist agent {agent_id}: {e}")
        
        return agent
    
    def mark_dead_agents(self, timeout_seconds: int) -> None:
        """Mark agents as dead if they haven't sent heartbeat"""
        now = datetime.now(timezone.utc)
        for agent_id, agent in self.agents.items():
            # Ensure last_seen is timezone-aware for comparison
            last_seen = agent.last_seen
            if last_seen.tzinfo is None:
                # If naive datetime, assume it's UTC
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            
            if agent.alive and (now - last_seen) > timedelta(seconds=timeout_seconds):
                agent.alive = False
                print(f"[AgentCache] Marked dead: {agent_id}")
    
    def get(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent by ID"""
        return self.agents.get(agent_id)
    
    def get_alive(self) -> Dict[str, AgentInfo]:
        """Get all alive agents"""
        return {aid: agent for aid, agent in self.agents.items() if agent.alive}
    
    def get_dead(self) -> Dict[str, AgentInfo]:
        """Get all dead agents"""
        return {aid: agent for aid, agent in self.agents.items() if not agent.alive}

# Global state instances
workflow_state = WorkflowState()
agent_cache = AgentCache()

# ============================================================================
# DBOS INITIALIZATION
# ============================================================================

dbos_config: DBOSConfig = {
    "name": "agent-server",
    "system_database_url": config.DBOS_SYSTEM_DATABASE_URL,
}
DBOS(config=dbos_config)

# ============================================================================
# NATS CLIENT
# ============================================================================

nats_settings = NATSotelSettings(
    service_name="server",
    servers=config.NATS_URL,
    otlp_trace_endpoint=config.OTLP_TRACE_ENDPOINT,
    otlp_logs_endpoint=config.OTLP_LOGS_ENDPOINT
)
nats_client: NATSotel = NATSotel(nats_settings)

# ============================================================================
# DBOS WORKFLOW STEPS
# ============================================================================

@DBOS.step()
async def validate_agent(agent_id: str) -> AgentInfo:
    """Validate that agent exists and is alive"""
    agent = agent_cache.get(agent_id)
    if not agent or not agent.alive:
        raise HTTPException(status_code=400, detail="Agent is not alive")
    return agent

@DBOS.step()
async def validate_module_schema(
    agent: AgentInfo,
    module_name: str,
    module_request: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate module request against agent's schema"""
    module_specs = agent.config.get("agent", {}).get("modules", {}).get("spec", {})
    
    if module_name not in module_specs:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")
    
    module_spec = module_specs[module_name]
    
    if not isinstance(module_spec, dict):
        raise HTTPException(status_code=500, detail="Invalid module specification")
    
    try:
        input_schema = module_spec['input_schema']
        if isinstance(input_schema, str):
            input_schema = json.loads(input_schema)
        validate(module_request, input_schema)
    except ValidationError as ex:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(ex)}")
    except json.JSONDecodeError as ex:
        raise HTTPException(status_code=500, detail=f"Invalid schema format: {str(ex)}")
    
    return module_spec

@DBOS.step(retries_allowed=True, max_attempts=3)
async def publish_to_nats(subject: str, message: str) -> None:
    """Publish message to NATS with retries"""
    await nats_client.publish(subject, message.encode())

@DBOS.step(retries_allowed=True, max_attempts=5, backoff_rate=2.0)
async def subscribe_to_nats(subject: str, callback) -> None:
    """Subscribe to NATS subject with retries"""
    await nats_client.subscribe(subject, cb=callback)

# ============================================================================
# DBOS WORKFLOWS
# ============================================================================

@DBOS.workflow()
async def execute_module_workflow(
    agent_id: str,
    module_name: str,
    module_request: Dict[str, Any],
    untracked: bool = False
) -> Dict[str, Any]:
    """
    Durable workflow for module execution coordination.
    Uses workflow_id as the primary identifier throughout.
    States: RUNNING → COMPLETED or FAILED
    """
    workflow_id = getattr(DBOS, 'current_workflow_id', None) or str(uuid.uuid4())
    
    try:
        # Add workflow_id to the request
        module_request["workflow_id"] = workflow_id
        
        # Initialize workflow state (RUNNING)
        workflow_state.create_workflow(
            workflow_id=workflow_id,
            agent_id=agent_id,
            module_name=module_name,
            request=module_request
        )
        
        # Step 1: Validate agent
        agent = await validate_agent(agent_id)
        
        # Step 2: Validate module request
        module_spec = await validate_module_schema(agent, module_name, module_request)
        
        # Step 3: Publish to NATS
        input_subject = module_spec['input_subject']
        if not isinstance(input_subject, str):
            raise HTTPException(status_code=500, detail="Invalid input subject")
        
        await publish_to_nats(input_subject, json.dumps(module_request))
        
        print(f"[Workflow] {workflow_id}: Published to {input_subject}")
        
        return {
            "status": "success",
            "workflow_id": workflow_id,
            "message": "Module execution initiated"
        }
        
    except HTTPException:
        workflow_state.set_state(workflow_id, "FAILED", error="HTTP error")
        raise
    except Exception as ex:
        workflow_state.set_state(workflow_id, "FAILED", error=str(ex))
        raise HTTPException(status_code=500, detail=f"Workflow error: {str(ex)}")

@DBOS.workflow()
async def setup_agent_subscriptions_workflow(
    agent_id: str,
    module_specs: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Durable workflow for setting up agent result subscriptions.
    Ensures reliable subscription to all agent output topics.
    """
    topics = set()
    
    # Generic output topic
    generic_topic = f"agent.{agent_id}.out"
    topics.add(generic_topic)
    
    # Module-specific output topics
    for module_name, module_config in module_specs.items():
        if "output_subject" in module_config:
            output_topic = module_config["output_subject"]
            if output_topic:
                topics.add(output_topic)
    
    # Subscribe to all topics
    async def result_handler(msg: Msg):
        """Handler for module results - updates workflow state"""
        try:
            data = json.loads(msg.data.decode())
            workflow_id = data.get("workflow_id")
            
            if not workflow_id:
                print(f"[Result] Received result without workflow_id, skipping")
                return
            
            # Check if workflow exists
            if workflow_id not in workflow_state.workflows:
                print(f"[Result] Unknown workflow: {workflow_id}")
                return
            
            # Update workflow state based on success
            success = data.get("success", True)
            final_state = "COMPLETED" if success else "FAILED"
            workflow_state.set_state(workflow_id, final_state, result_received=True)
            
        except Exception as e:
            print(f"[Result] Error processing result: {e}")
    
    for topic in topics:
        await subscribe_to_nats(topic, result_handler)
    
    print(f"[Subscription] Agent {agent_id}: {list(topics)}")
    return {"agent_id": agent_id, "subscribed_topics": list(topics)}

# ============================================================================
# NATS HANDLERS
# ============================================================================

async def handle_heartbeat(msg: Msg) -> None:
    """Process agent heartbeat messages"""
    try:
        data = json.loads(msg.data.decode())
        agent_id = data["agent"]["id"]
        hostname = data["agent"]["hostname"]
        
        # Update agent cache
        previous_config = None
        if agent_id in agent_cache.agents:
            previous_config = agent_cache.agents[agent_id].config
        
        agent = agent_cache.update_heartbeat(agent_id, hostname, data)
        
        # If config changed or new agent, resubscribe
        if previous_config != data:
            print(f"[Subscription] Config changed for {agent_id}, resubscribing...")
            try:
                module_specs = data.get("agent", {}).get("modules", {}).get("spec", {})
                await setup_agent_subscriptions_workflow(agent_id, module_specs)
            except Exception as e:
                print(f"[Subscription] Error resubscribing for {agent_id}: {e}")
                
    except Exception as e:
        print(f"[Heartbeat] Error processing heartbeat: {e}")

async def handle_module_state(msg: Msg) -> None:
    """
    Process module state change messages from agents.
    Maps agent states to workflow states: RUNNING, COMPLETED, FAILED
    """
    try:
        data = json.loads(msg.data.decode())
        agent_id = data["agent_id"]
        module_name = data["module_name"]
        state = data["state"]
        workflow_id = data.get("workflow_id")
        
        if not workflow_id:
            print(f"[ModuleState] No workflow_id in state message, skipping")
            return
        
        # Check if workflow exists
        if workflow_id not in workflow_state.workflows:
            print(f"[ModuleState] Unknown workflow: {workflow_id}")
            return
        
        # Map agent states to our 3 workflow states
        state_mapping = {
            "STARTED": "RUNNING",
            "RUNNING": "RUNNING",
            "COMPLETED": "COMPLETED",
            "ERROR": "FAILED",
            "FAILED": "FAILED"
        }
        
        mapped_state = state_mapping.get(state.upper())
        if not mapped_state:
            print(f"[ModuleState] Unknown state '{state}', ignoring")
            return
        
        # Update workflow state
        workflow_state.set_state(
            workflow_id,
            mapped_state,
            agent_id=agent_id,
            module_name=module_name,
            agent_state=state,
            error_message=data.get("error_message")
        )
        
    except Exception as e:
        print(f"[ModuleState] Error processing state: {e}")

# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def nats_connect_task():
    """Connect to NATS and set up subscriptions"""
    await nats_client.connect(
        nats_settings.servers,
        name="server",
        verbose=True,
        reconnect_time_wait=0
    )
    print(f"[NATS] Connected to {config.NATS_URL}")
    
    # Subscribe to heartbeats and module states
    await nats_client.subscribe(config.HEARTBEAT_SUBJECT, cb=handle_heartbeat)
    await nats_client.subscribe("agent.module.state", cb=handle_module_state)
    print(f"[NATS] Subscribed to control topics")
    
    # Wait for initial heartbeats, then subscribe to existing agents
    await asyncio.sleep(2)
    print(f"[Startup] Subscribing to {len(agent_cache.agents)} existing agents...")
    
    for agent_id, agent in agent_cache.agents.items():
        try:
            module_specs = agent.config.get("agent", {}).get("modules", {}).get("spec", {})
            await setup_agent_subscriptions_workflow(agent_id, module_specs)
            print(f"[Startup] Subscribed to agent: {agent_id}")
        except Exception as e:
            print(f"[Startup] Error subscribing to {agent_id}: {e}")

async def agent_cleanup_task():
    """Periodically mark dead agents"""
    while True:
        agent_cache.mark_dead_agents(config.HEARTBEAT_TIMEOUT)
        await asyncio.sleep(config.HEARTBEAT_INTERVAL)

async def workflow_cleanup_task():
    """Periodically check for stale workflows assigned to dead agents"""
    while True:
        # Check every 30 seconds
        await asyncio.sleep(30)
        try:
            workflow_state.check_stale_workflows(agent_cache)
        except Exception as e:
            print(f"[WorkflowCleanup] Error: {e}")

async def cache_sync_task():
    """Periodically synchronize in-memory cache with database"""
    while True:
        # Sync every 30 seconds
        await asyncio.sleep(30)
        try:
            # Only proceed if we have persistence managers
            if not agent_cache.persistence or not workflow_state.persistence:
                await asyncio.sleep(30)
                continue
                
            # Synchronize agents
            db_agents = agent_cache.persistence.load_agents()
            
            # Update in-memory cache with any new/changed records from database
            for agent_id, db_agent in db_agents.items():
                # If agent doesn't exist in memory or database record is newer
                if agent_id not in agent_cache.agents:
                    agent_cache.agents[agent_id] = db_agent
                    print(f"[CacheSync] Added agent {agent_id} from database")
                else:
                    # Conflict resolution: use the more recent record
                    mem_agent = agent_cache.agents[agent_id]
                    # Compare timestamps to determine which is more recent
                    # Ensure both timestamps have the same timezone awareness
                    db_last_seen = db_agent.last_seen
                    mem_last_seen = mem_agent.last_seen
                    
                    # Convert naive datetime to timezone-aware if needed
                    if db_last_seen.tzinfo is None and mem_last_seen.tzinfo is not None:
                        # Database timestamp is naive, memory timestamp is timezone-aware
                        db_last_seen = db_last_seen.replace(tzinfo=timezone.utc)
                    elif db_last_seen.tzinfo is not None and mem_last_seen.tzinfo is None:
                        # Memory timestamp is naive, database timestamp is timezone-aware
                        mem_last_seen = mem_last_seen.replace(tzinfo=timezone.utc)
                    
                    if db_last_seen > mem_last_seen:
                        # Database record is newer, update memory
                        agent_cache.agents[agent_id] = db_agent
                        print(f"[CacheSync] Updated agent {agent_id} from database (newer timestamp)")
                    elif db_agent.total_heartbeats > mem_agent.total_heartbeats:
                        # Database has more heartbeats, likely more accurate
                        agent_cache.agents[agent_id] = db_agent
                        print(f"[CacheSync] Updated agent {agent_id} from database (more heartbeats)")
            
            # Remove agents from memory that no longer exist in database
            mem_agent_ids = set(agent_cache.agents.keys())
            db_agent_ids = set(db_agents.keys())
            removed_agents = mem_agent_ids - db_agent_ids
            
            for agent_id in removed_agents:
                # Only remove if it's not a recently active agent
                agent = agent_cache.agents[agent_id]
                # Ensure agent.last_seen has timezone info for comparison
                agent_last_seen = agent.last_seen
                if agent_last_seen.tzinfo is None:
                    agent_last_seen = agent_last_seen.replace(tzinfo=timezone.utc)
                
                if not agent.alive or (datetime.now(timezone.utc) - agent_last_seen).total_seconds() > 300:  # 5 minutes
                    del agent_cache.agents[agent_id]
                    print(f"[CacheSync] Removed agent {agent_id} (no longer in database)")
            
            # Synchronize workflows
            db_workflows = workflow_state.persistence.load_workflows()
            db_workflow_states = workflow_state.persistence.load_workflow_states()
            
            # Update in-memory workflows with any new/changed records from database
            for workflow_id, db_workflow in db_workflows.items():
                # If workflow doesn't exist in memory
                if workflow_id not in workflow_state.workflows:
                    workflow_state.workflows[workflow_id] = db_workflow
                    print(f"[CacheSync] Added workflow {workflow_id} from database")
                else:
                    # Conflict resolution: use the more recent record
                    mem_workflow = workflow_state.workflows[workflow_id]
                    # Compare creation timestamps to determine which is more recent
                    try:
                        mem_created_raw = mem_workflow.get("created_at")
                        db_created_raw = db_workflow.get("created_at")
                        
                        if mem_created_raw and db_created_raw:
                            # Convert to datetime objects if they're strings
                            if isinstance(mem_created_raw, str):
                                mem_created = datetime.fromisoformat(mem_created_raw)
                            elif isinstance(mem_created_raw, datetime):
                                mem_created = mem_created_raw
                            else:
                                print(f"[CacheSync] Warning: Unexpected type for mem_created: {type(mem_created_raw)}")
                                continue
                            
                            if isinstance(db_created_raw, str):
                                db_created = datetime.fromisoformat(db_created_raw)
                            elif isinstance(db_created_raw, datetime):
                                db_created = db_created_raw
                            else:
                                print(f"[CacheSync] Warning: Unexpected type for db_created: {type(db_created_raw)}")
                                continue
                            
                            # Ensure both timestamps have the same timezone awareness
                            if db_created.tzinfo is None and mem_created.tzinfo is not None:
                                # Database timestamp is naive, memory timestamp is timezone-aware
                                db_created = db_created.replace(tzinfo=timezone.utc)
                            elif db_created.tzinfo is not None and mem_created.tzinfo is None:
                                # Memory timestamp is naive, database timestamp is timezone-aware
                                mem_created = mem_created.replace(tzinfo=timezone.utc)
                            
                            if db_created > mem_created:
                                # Database record is newer, update memory
                                workflow_state.workflows[workflow_id] = db_workflow
                                print(f"[CacheSync] Updated workflow {workflow_id} from database (newer timestamp)")
                    except (ValueError, TypeError) as e:
                        # If parsing fails, skip this comparison
                        print(f"[CacheSync] Warning: Could not compare timestamps for workflow {workflow_id}: {e}")
            
            # Update in-memory workflow states with any new/changed records from database
            for workflow_id, db_states in db_workflow_states.items():
                # If workflow states don't exist in memory or database has more states
                if workflow_id not in workflow_state.state_history:
                    workflow_state.state_history[workflow_id] = db_states
                    print(f"[CacheSync] Added workflow states for {workflow_id} from database")
                else:
                    # Merge states, keeping the most complete history
                    mem_states = workflow_state.state_history[workflow_id]
                    # If database has more recent states, update
                    try:
                        if db_states and mem_states:
                            # Get last timestamps from both sources
                            db_last_ts_raw = db_states[-1]["timestamp"]
                            mem_last_ts_raw = mem_states[-1]["timestamp"]
                            
                            # Convert to datetime objects if they're strings
                            if isinstance(db_last_ts_raw, str):
                                db_last_timestamp = datetime.fromisoformat(db_last_ts_raw)
                            elif isinstance(db_last_ts_raw, datetime):
                                db_last_timestamp = db_last_ts_raw
                            else:
                                print(f"[CacheSync] Warning: Unexpected type for db timestamp: {type(db_last_ts_raw)}")
                                continue
                            
                            if isinstance(mem_last_ts_raw, str):
                                mem_last_timestamp = datetime.fromisoformat(mem_last_ts_raw)
                            elif isinstance(mem_last_ts_raw, datetime):
                                mem_last_timestamp = mem_last_ts_raw
                            else:
                                print(f"[CacheSync] Warning: Unexpected type for mem timestamp: {type(mem_last_ts_raw)}")
                                continue
                            
                            # Ensure both timestamps have the same timezone awareness
                            if db_last_timestamp.tzinfo is None and mem_last_timestamp.tzinfo is not None:
                                # Database timestamp is naive, memory timestamp is timezone-aware
                                db_last_timestamp = db_last_timestamp.replace(tzinfo=timezone.utc)
                            elif db_last_timestamp.tzinfo is not None and mem_last_timestamp.tzinfo is None:
                                # Memory timestamp is naive, database timestamp is timezone-aware
                                mem_last_timestamp = mem_last_timestamp.replace(tzinfo=timezone.utc)
                            
                            if db_last_timestamp > mem_last_timestamp:
                                workflow_state.state_history[workflow_id] = db_states
                                print(f"[CacheSync] Updated workflow states for {workflow_id} from database")
                    except (ValueError, TypeError, KeyError) as e:
                        # If parsing fails, skip this comparison
                        print(f"[CacheSync] Warning: Could not compare state timestamps for workflow {workflow_id}: {e}")
            
            print(f"[CacheSync] Completed sync - Agents: {len(agent_cache.agents)}, Workflows: {len(workflow_state.workflows)}")

        except Exception as e:
            print(f"[CacheSync] Error during synchronization: {e}")

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Agent Server",
    version="2.0",
    description="Workflow-focused agent coordination server"
)

# Execution queue for async workflows
execution_queue = Queue("module_execution", worker_concurrency=10)

@app.on_event("startup")
async def startup_event():
    """Initialize DBOS and background tasks"""
    DBOS.launch()
    print("[DBOS] Launched")
    asyncio.create_task(nats_connect_task())
    asyncio.create_task(agent_cleanup_task())
    asyncio.create_task(workflow_cleanup_task())
    asyncio.create_task(cache_sync_task())

# ============================================================================
# API ROUTES - HEALTH & AGENTS
# ============================================================================

@app.get("/")
async def root():
    """Health check and basic stats"""
    return {
        "status": "ok",
        "total_agents": len(agent_cache.agents),
        "alive_agents": len(agent_cache.get_alive()),
        "total_workflows": len(workflow_state.workflows)
    }

@app.get("/agents")
async def list_all_agents():
    """Get all agents (alive and dead)"""
    return agent_cache.agents

@app.get("/agents/alive")
async def list_alive_agents():
    """Get only alive agents"""
    return agent_cache.get_alive()

@app.get("/agents/dead")
async def list_dead_agents():
    """Get only dead agents"""
    return agent_cache.get_dead()

@app.get("/agents/{agent_id}")
async def get_agent_info(agent_id: str):
    """Get detailed info about specific agent"""
    agent = agent_cache.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

# ============================================================================
# API ROUTES - MODULE EXECUTION
# ============================================================================

@app.post("/agent/{agent_id}/{module_name}")
async def execute_module(
    agent_id: str,
    module_name: str,
    module_request: Dict[str, Any],
    untracked: bool = Query(False)
):
    """Execute module synchronously via durable workflow"""
    result = await execute_module_workflow(
        agent_id,
        module_name,
        module_request,
        untracked
    )
    return result

@app.post("/agent/{agent_id}/{module_name}/async")
async def execute_module_async(
    agent_id: str,
    module_name: str,
    module_request: Dict[str, Any]
):
    """Enqueue module execution for async processing"""
    handle = execution_queue.enqueue(
        execute_module_workflow,
        agent_id,
        module_name,
        module_request,
        False
    )
    
    return {
        "status": "enqueued",
        "workflow_id": handle.workflow_id
    }

# ============================================================================
# API ROUTES - WORKFLOW MANAGEMENT
# ============================================================================

@app.get("/workflows")
async def list_workflows(
    status: Optional[str] = None,
    limit: int = Query(100, le=1000)
):
    """
    List workflows with optional status filter.
    Status must be one of: RUNNING, COMPLETED, FAILED
    """
    if status and status not in ["RUNNING", "COMPLETED", "FAILED"]:
        raise HTTPException(
            status_code=400, 
            detail="Status must be RUNNING, COMPLETED, or FAILED"
        )
    
    workflows = []
    
    # Get workflows from our cache
    workflow_items = list(workflow_state.workflows.items())
    if len(workflow_items) > limit:
        workflow_items = workflow_items[-limit:]
    
    for workflow_id, workflow_data in workflow_items:
        current_state = workflow_state.get_current_state(workflow_id)
        
        # Apply status filter
        if status and current_state != status:
            continue
        
        state_history = workflow_state.state_history.get(workflow_id, [])
        
        workflows.append({
            "workflow_id": workflow_id,
            "agent_id": workflow_data.get("agent_id"),
            "module_name": workflow_data.get("module_name"),
            "current_state": current_state,
            "created_at": workflow_data.get("created_at"),
            "state_transitions": len(state_history)
        })
    
    # Also try to get DBOS workflows
    dbos_workflows = []
    try:
        dbos_wf_list = DBOS.list_workflows(limit=limit)
        if status:
            dbos_wf_list = [w for w in dbos_wf_list if w.status == status]
        
        dbos_workflows = [
            {
                "workflow_id": w.workflow_id,
                "status": w.status,
                "workflow_name": getattr(w, 'workflow_name', 'unknown'),
                "started_at": getattr(w, 'started_at', None)
            }
            for w in dbos_wf_list
        ]
    except Exception as e:
        print(f"[Workflows] Error listing DBOS workflows: {e}")
    
    return {
        "workflows": workflows,
        "dbos_workflows": dbos_workflows,
        "total": len(workflow_state.workflows)
    }

@app.get("/workflows/{workflow_id}")
async def get_workflow_status(workflow_id: str):
    """Get detailed status of a specific workflow"""
    # Check our cache first
    if workflow_id not in workflow_state.workflows:
        # Try DBOS
        try:
            dbos_status = DBOS.retrieve_workflow(workflow_id)
            return {
                "workflow_id": workflow_id,
                "source": "dbos",
                "status": dbos_status.status,
                "result": dbos_status.get_result() if dbos_status.status == "SUCCESS" else None
            }
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Workflow not found: {str(e)}")
    
    # Get from our cache
    workflow_data = workflow_state.workflows[workflow_id]
    state_history = workflow_state.state_history.get(workflow_id, [])
    current_state = workflow_state.get_current_state(workflow_id)
    
    # Also try to get DBOS status
    dbos_status = None
    try:
        status = DBOS.retrieve_workflow(workflow_id)
        dbos_status = {
            "status": status.status,
            "result": status.get_result() if status.status == "SUCCESS" else None
        }
    except Exception:
        pass
    
    return {
        "workflow_id": workflow_id,
        "agent_id": workflow_data.get("agent_id"),
        "module_name": workflow_data.get("module_name"),
        "current_state": current_state,
        "created_at": workflow_data.get("created_at"),
        "state_history": state_history,
        "request": workflow_data.get("request"),
        "dbos_status": dbos_status
    }

@app.post("/workflows/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """Cancel a running workflow"""
    # Update our cache
    if workflow_id in workflow_state.workflows:
        workflow_state.set_state(workflow_id, "FAILED", cancelled=True)
    
    # Try to cancel in DBOS
    try:
        DBOS.cancel_workflow(workflow_id)
        return {
            "workflow_id": workflow_id,
            "status": "FAILED",
            "message": "Workflow cancelled successfully"
        }
    except Exception as e:
        return {
            "workflow_id": workflow_id,
            "status": "FAILED",
            "message": f"Cancelled in cache. DBOS error: {str(e)}"
        }

# ============================================================================
# DEBUG ENDPOINTS
# ============================================================================

@app.get("/debug/state")
async def debug_state():
    """Debug endpoint to inspect internal state"""
    return {
        "agents": {
            "total": len(agent_cache.agents),
            "alive": len(agent_cache.get_alive()),
            "agent_ids": list(agent_cache.agents.keys())
        },
        "workflows": {
            "total": len(workflow_state.workflows),
            "workflow_ids": list(workflow_state.workflows.keys())[-10:],  # Last 10
            "states": {
                "RUNNING": len([w for w in workflow_state.workflows.keys() 
                               if workflow_state.get_current_state(w) == "RUNNING"]),
                "COMPLETED": len([w for w in workflow_state.workflows.keys() 
                                 if workflow_state.get_current_state(w) == "COMPLETED"]),
                "FAILED": len([w for w in workflow_state.workflows.keys() 
                              if workflow_state.get_current_state(w) == "FAILED"])
            }
        }
    }