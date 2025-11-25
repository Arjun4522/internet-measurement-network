import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict, Optional

from fastapi import FastAPI, Query, HTTPException
from dbos import DBOS, DBOSConfig, Queue

from nats_observe.config import NATSotelSettings
from nats_observe.client import Client as NATSotel
from nats.aio.msg import Msg

from models import AgentHeartbeat, AgentInfo, ModuleState, ModuleStateEnum

from openapi_schema_validator import validate
from jsonschema.exceptions import ValidationError

# ======== CONFIG ============
NATS_URL = [os.environ.get("NATS_URL", "nats://localhost:4222")]
HEARTBEAT_SUBJECT = "agent.heartbeat_module"
HEARTBEAT_INTERVAL = 5
HEARTBEAT_TIMEOUT = HEARTBEAT_INTERVAL * 2

# OTel configuration
OTLP_TRACE_ENDPOINT = os.environ.get("OTLP_TRACE_ENDPOINT", "otel-collector:4317")
OTLP_METRICS_ENDPOINT = os.environ.get("OTLP_METRICS_ENDPOINT", "otel-collector:4317")
OTLP_LOGS_ENDPOINT = os.environ.get("OTLP_LOGS_ENDPOINT", "otel-collector:4317")

# DBOS configuration
DBOS_SYSTEM_DATABASE_URL = os.environ.get("DBOS_SYSTEM_DATABASE_URL", "sqlite:///db/data.db")
# ============================

# 🧠 In-memory cache
agent_cache: Dict[str, AgentInfo] = {}
results_cache: Dict[str, Dict[str, Any]] = {}
request_id_states_cache: Dict[str, ModuleState] = {}

# Initialize DBOS
dbos_config: DBOSConfig = {
    "name": "agent-server",
    "system_database_url": DBOS_SYSTEM_DATABASE_URL,
}
DBOS(config=dbos_config)

# NATS settings
settings = NATSotelSettings(
    service_name="server", 
    servers=NATS_URL,
    otlp_trace_endpoint=OTLP_TRACE_ENDPOINT,
    otlp_logs_endpoint=OTLP_LOGS_ENDPOINT
)
nc: NATSotel = NATSotel(settings)

app = FastAPI(title="Agent Server", version="1.0")

# Queue for async module execution
module_execution_queue = Queue("module_execution", worker_concurrency=10)


# ======== DBOS WORKFLOW STEPS ========

@DBOS.step()
async def validate_agent(agent_id: str) -> AgentInfo:
    """Step 1: Validate agent is alive"""
    agent = agent_cache.get(agent_id)
    if not agent or not agent.alive:
        raise HTTPException(status_code=400, detail="Agent is not alive")
    return agent


@DBOS.step()
async def validate_module_request(
    agent: AgentInfo, 
    module_name: str, 
    module_request: Dict[str, Any]
) -> Dict[str, Any]:
    """Step 2: Validate request against schema"""
    all_spec = agent.config.get("agent", {}).get("modules", {}).get("spec", {})
    
    if module_name not in all_spec:
        raise HTTPException(status_code=404, detail="Module not found")
    
    module_spec = all_spec[module_name]
    
    # Ensure module_spec is a dictionary
    if not isinstance(module_spec, dict):
        raise HTTPException(status_code=500, detail="Invalid module specification format")
    
    try:
        # Ensure input_schema is a dictionary, not a string
        input_schema = module_spec['input_schema']
        if isinstance(input_schema, str):
            input_schema = json.loads(input_schema)
        validate(module_request, input_schema)
    except ValidationError as ex:
        raise HTTPException(status_code=400, detail=f"Validation Error: {str(ex)}")
    except json.JSONDecodeError as ex:
        raise HTTPException(status_code=500, detail=f"Invalid input_schema format: {str(ex)}")
    except json.JSONDecodeError as ex:
        raise HTTPException(status_code=500, detail=f"Invalid input_schema format: {str(ex)}")
    
    return module_spec


@DBOS.step(retries_allowed=True, max_attempts=3)
async def publish_to_nats(subject: str, message: str):
    """Step 3: Publish to NATS with retries"""
    await nc.publish(subject, message.encode())


@DBOS.step()
async def store_request_tracking(agent_id: str, request_id: str, module_name: str):
    """Step 4: Store request for tracking"""
    if agent_id not in results_cache:
        results_cache[agent_id] = {}
    
    # Store with proper structure
    results_cache[agent_id][request_id] = {
        "status": "pending",
        "module": module_name,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "id": request_id  # Ensure ID is included
    }
    print(f"[Tracking] Stored pending request {request_id} for agent {agent_id}")


@DBOS.step()
async def parse_result(msg_data: bytes) -> Dict[str, Any]:
    """Parse and validate result message"""
    return json.loads(msg_data.decode())


@DBOS.step()
async def store_result(agent_id: str, request_id: str, result: Dict[str, Any]):
    """Store result in cache - merge with existing pending data"""
    if agent_id not in results_cache:
        results_cache[agent_id] = {}
    
    current = results_cache[agent_id].get(request_id, {})
    
    if current.get("status") == "pending":
        # Merge the actual result into the pending structure
        merged_result = {**current, **result}
        # Remove pending status since we now have actual results
        if "status" in merged_result and merged_result["status"] == "pending":
            del merged_result["status"]
        results_cache[agent_id][request_id] = merged_result
        print(f"[Store] Merged actual data into pending result for {request_id}")
    else:
        # No pending entry, store directly
        results_cache[agent_id][request_id] = result
        print(f"[Store] Stored new result for {request_id}")


@DBOS.step()
async def update_module_state(request_id: str, state: ModuleStateEnum):
    """Update module state for request"""
    if request_id in request_id_states_cache:
        request_id_states_cache[request_id].state = state
        request_id_states_cache[request_id].timestamp = datetime.now(timezone.utc)


@DBOS.step(retries_allowed=True, max_attempts=5, backoff_rate=2.0)
async def subscribe_to_topic(topic: str, agent_id: str):
    """Subscribe to NATS topic with retries"""
    async def result_handler(msg: Msg):
        try:
            await process_agent_result(agent_id, msg.data)
        except Exception as e:
            print(f"[Results] Error in result handler for {agent_id}: {e}")
    
    await nc.subscribe(topic, cb=result_handler)
    print(f"[Subscription] Subscribed to {topic}")


# ======== DBOS WORKFLOWS ========

@DBOS.workflow()
async def run_module(
    agent_id: str, 
    module_name: str, 
    module_request: Dict[str, Any], 
    untracked: bool = False
):
    """Durable workflow for module execution"""
    try:
        # Step 1: Validate agent
        agent = await validate_agent(agent_id)
        
        # Generate request ID if not untracked
        if not untracked and "id" not in module_request:
            module_request["id"] = str(uuid.uuid4())
        
        request_id = module_request.get("id")
        
        # Step 2: Validate module request
        module_spec = await validate_module_request(agent, module_name, module_request)
        
        # Step 3: Publish to NATS (with retries)
        input_subject = module_spec['input_subject']
        if not isinstance(input_subject, str):
            raise HTTPException(status_code=500, detail="Invalid input subject type")
        await publish_to_nats(input_subject, json.dumps(module_request))
        
        # Step 4: Track request
        if request_id:
            await store_request_tracking(agent_id, request_id, module_name)
        
        # Get workflow ID - FIXED: Use context or available method
        workflow_id = getattr(DBOS, 'current_workflow_id', None) or str(uuid.uuid4())
        
        return {
            "message": "success",
            "id": request_id,
            "workflow_id": workflow_id
        }
        
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Workflow error: {str(ex)}")


@DBOS.workflow()
async def process_agent_result(agent_id: str, msg_data: bytes):
    """Durable workflow for processing agent results"""
    try:
        # Step 1: Parse result
        result = await parse_result(msg_data)
        request_id = result.get("id")
        
        if not request_id:
            print(f"[Results] Skipping untracked result from agent {agent_id}")
            return
        
        # Step 2: Check if we already processed this result (more robust check)
        agent_results = results_cache.get(agent_id, {})
        existing_result = agent_results.get(request_id)
        
        # If result exists and is not pending, skip processing
        if existing_result and existing_result.get("status") != "pending":
            print(f"[Results] Already processed result for request {request_id}, skipping")
            return
        
        print(f"[DEBUG] Processing new result for request {request_id}: {result}")
        
        # Step 3: Store result
        await store_result(agent_id, request_id, result)
        
        # Step 4: Update state - handle missing success field
        success = result.get("success")
        if success is None:
            # For ping results, consider it successful if we have the result data
            success = "rtts" in result or "address" in result
        
        state = ModuleStateEnum.COMPLETED if success else ModuleStateEnum.ERROR
        await update_module_state(request_id, state)
        
        print(f"[Results] Successfully processed result for agent {agent_id}, request {request_id}")
        
    except Exception as e:
        print(f"[ERROR] Failed to process agent result: {e}")

@DBOS.workflow()
async def setup_agent_subscriptions(agent_id: str, module_specs: Dict[str, Any]):
    """Durable workflow for setting up agent subscriptions"""
    topics = []
    
    # Generic output topic
    generic_topic = f"agent.{agent_id}.out"
    topics.append(generic_topic)
    
    # Module-specific topics
    for module_name, module_config in module_specs.items():
        if "output_subject" in module_config:
            output_topic = module_config["output_subject"]
            if output_topic != generic_topic:
                topics.append(output_topic)
    
    # Subscribe to all topics with retry
    for topic in topics:
        await subscribe_to_topic(topic, agent_id)
    
    print(f"[Subscription] Setup complete for agent {agent_id}: {topics}")
    return {"subscribed_topics": topics}


# ======== NATS CONNECTION & HANDLERS ========

async def nats_connect():
    await nc.connect(settings.servers, name="server", verbose=True, reconnect_time_wait=0)
    print(f"[Cache] Connected to NATS: {NATS_URL}")

    async def heartbeat_handler(msg: Msg):
        try:
            data = json.loads(msg.data.decode())
            hb = AgentHeartbeat(agent_id=data["agent"]["id"], hostname=data["agent"]["hostname"])

            existing = agent_cache.get(hb.agent_id)
            now = datetime.now(timezone.utc)

            if existing:
                existing.last_seen = hb.timestamp
                existing.alive = True
                
                # Check if config has changed and resubscribe if needed
                if existing.config != data:
                    print(f"[Subscription] Agent {hb.agent_id} config updated, resubscribing...")
                    try:
                        await subscribe_to_agent_results(hb.agent_id)
                        print(f"[Subscription] Successfully resubscribed for agent: {hb.agent_id}")
                    except Exception as e:
                        print(f"[Subscription] Error resubscribing for agent {hb.agent_id}: {e}")
                
                existing.config = data
                existing.total_heartbeats += 1
                print(f"[Cache] Updated heartbeat: {hb.agent_id} @ {hb.timestamp}")
            else:
                agent_cache[hb.agent_id] = AgentInfo(
                    agent_id=hb.agent_id,
                    alive=True,
                    hostname=hb.hostname,
                    last_seen=hb.timestamp,
                    config=data,
                    first_seen=now,
                    total_heartbeats=1
                )
                
                # Subscribe to result topics for new agent
                print(f"[Subscription] New agent detected: {hb.agent_id}, subscribing...")
                try:
                    await subscribe_to_agent_results(hb.agent_id)
                    print(f"[Subscription] Successfully subscribed for agent: {hb.agent_id}")
                except Exception as e:
                    print(f"[Subscription] Error subscribing for agent {hb.agent_id}: {e}")
                
                print(f"[Cache] New agent registered: {hb.agent_id}")

        except Exception as e:
            print("[Cache] Error parsing heartbeat:", e)

    async def module_state_handler(msg: Msg):
        try:
            data = json.loads(msg.data.decode())
            agent_id = data["agent_id"]
            module_name = data["module_name"]
            state = data["state"]
            request_id = data.get("request_id")
            
            module_state = ModuleState(
                agent_id=agent_id,
                module_name=module_name,
                state=state,
                error_message=data.get("error_message"),
                details=data.get("details")
            )
            
            if request_id:
                request_id_states_cache[request_id] = module_state
                print(f"[ModuleState] Stored state for request_id: {request_id}")
            
            print(f"[ModuleState] Updated state for {agent_id}.{module_name}: {state}")
            
        except Exception as e:
            print("[ModuleState] Error parsing module state:", e)

    await nc.subscribe(HEARTBEAT_SUBJECT, cb=heartbeat_handler)
    await nc.subscribe("agent.module.state", cb=module_state_handler)
    print(f"[Cache] Subscribed to {HEARTBEAT_SUBJECT} and agent.module.state")
    
    # Subscribe to existing agents after delay
    print("[Startup] Scheduling subscription to existing agents...")
    asyncio.create_task(subscribe_existing_agents())


async def subscribe_to_agent_results(agent_id: str):
    """Subscribe to result topics for a specific agent using DBOS workflow"""
    agent_info = agent_cache.get(agent_id)
    if agent_info and agent_info.config:
        modules_spec = agent_info.config.get("agent", {}).get("modules", {}).get("spec", {})
        await setup_agent_subscriptions(agent_id, modules_spec)


async def cleanup_agents():
    """Background cleanup task to mark dead agents"""
    while True:
        now = datetime.now(timezone.utc)
        for agent_id, info in agent_cache.items():
            if (now - info.last_seen) > timedelta(seconds=HEARTBEAT_TIMEOUT):
                if info.alive:
                    info.alive = False
                    print(f"[Cache] Agent {agent_id} marked DEAD (last seen {info.last_seen})")
        await asyncio.sleep(HEARTBEAT_INTERVAL)


async def subscribe_existing_agents():
    """Subscribe to result topics for existing agents"""
    print("[Startup] Waiting for initial heartbeats...")
    await asyncio.sleep(2)
    
    print(f"[Startup] Found {len(agent_cache)} agents in cache, subscribing...")
    for agent_id in list(agent_cache.keys()):
        print(f"[Startup] Subscribing to results for existing agent: {agent_id}")
        try:
            await subscribe_to_agent_results(agent_id)
            print(f"[Startup] Successfully subscribed for agent: {agent_id}")
        except Exception as e:
            print(f"[Startup] Error subscribing for agent {agent_id}: {e}")


# ======== FASTAPI STARTUP ========

@app.on_event("startup")
async def startup_event():
    DBOS.launch()
    print("[DBOS] Launched successfully")
    asyncio.create_task(nats_connect())
    asyncio.create_task(cleanup_agents())


# ======== API ROUTES ========

@app.get("/")
async def root():
    return {
        "status": "ok",
        "total_agents": len(agent_cache),
        "alive_agents": len([a for a in agent_cache.values() if a.alive]),
    }


@app.get("/agents", response_model=Dict[str, AgentInfo])
async def get_all_agents():
    """Get all agents (alive and dead) with metadata."""
    return agent_cache


@app.get("/agents/alive", response_model=Dict[str, AgentInfo])
async def get_alive_agents():
    """Get only currently alive agents."""
    return {aid: info for aid, info in agent_cache.items() if info.alive}


@app.get("/agents/dead", response_model=Dict[str, AgentInfo])
async def get_dead_agents():
    """Get only agents considered dead (missed heartbeat)."""
    return {aid: info for aid, info in agent_cache.items() if not info.alive}


@app.get("/agents/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str):
    """Get detailed info about a specific agent."""
    agent = agent_cache.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.get("/agents/{agent_id}/results/{request_id}")
async def get_agent_result(agent_id: str, request_id: str):
    """Get result for a specific agent and request ID."""
    agent_results = results_cache.get(agent_id, {})
    result = agent_results.get(request_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
        
    return result


@app.get("/agents/{agent_id}/results")
async def get_agent_results(agent_id: str):
    """Get all results for a specific agent."""
    return results_cache.get(agent_id, {})


@app.delete("/agents/{agent_id}/results/{request_id}")
async def delete_agent_result(agent_id: str, request_id: str):
    """Delete a specific result for an agent."""
    agent_results = results_cache.get(agent_id, {})
    if request_id in agent_results:
        del agent_results[request_id]
        return {"message": "Result deleted"}
    else:
        raise HTTPException(status_code=404, detail="Result not found")


# ======== MODULE EXECUTION ROUTES ========

@app.post("/agent/{agent_id}/{module_name}")
async def run_module_sync(
    agent_id: str, 
    module_name: str, 
    module_request: Dict[str, Any], 
    untracked: bool = Query(False)
):
    """Execute module synchronously using durable workflow"""
    result = await run_module(agent_id, module_name, module_request, untracked)
    return result


@app.post("/agent/{agent_id}/{module_name}/async")
async def run_module_async(
    agent_id: str, 
    module_name: str, 
    module_request: Dict[str, Any]
):
    """Enqueue module execution for async processing"""
    if "id" not in module_request:
        module_request["id"] = str(uuid.uuid4())
    
    # Enqueue the workflow
    handle = module_execution_queue.enqueue(
        run_module, 
        agent_id, 
        module_name, 
        module_request,
        False  # untracked
    )
    
    return {
        "message": "Module execution enqueued",
        "id": module_request["id"],
        "workflow_id": handle.workflow_id
    }


# ======== MODULE STATE ROUTES ========

@app.get("/modules/states")
async def get_all_module_states():
    """Get all module states across all agents."""
    return request_id_states_cache


@app.get("/modules/states/{request_id}")
async def get_module_state_by_request_id(request_id: str):
    """Get module state by request ID."""
    module_state = request_id_states_cache.get(request_id)
    
    if not module_state:
        raise HTTPException(status_code=404, detail="Module state not found for this request ID")
        
    return module_state.dict()


# ======== WORKFLOW MANAGEMENT ROUTES ========

@app.get("/workflows")
async def list_workflows(
    status: Optional[str] = None,
    limit: int = Query(100, le=1000)
):
    """List recent workflows"""
    try:
        workflows = DBOS.list_workflows(limit=limit)
        
        if status:
            workflows = [w for w in workflows if w.status == status]
        
        return {
            "workflows": [
                {
                    "workflow_id": w.workflow_id,
                    "status": w.status,
                    "workflow_name": getattr(w, 'workflow_name', 'unknown'),
                    "started_at": getattr(w, 'started_at', None),
                    "execution_id": getattr(w, 'execution_id', None)
                }
                for w in workflows
            ]
        }
    except Exception as e:
        print(f"[Workflows] Error listing workflows: {e}")
        return {"workflows": [], "error": str(e)}


@app.get("/workflows/{workflow_id}/status")
async def get_workflow_status(workflow_id: str):
    """Check status of a workflow execution"""
    try:
        status = DBOS.retrieve_workflow(workflow_id)
        return {
            "workflow_id": workflow_id,
            "status": status.status,
            "result": status.get_result() if status.status == "SUCCESS" else None
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {str(e)}")


@app.post("/workflows/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """Cancel a running workflow"""
    try:
        DBOS.cancel_workflow(workflow_id)
        return {"message": "Workflow cancelled", "workflow_id": workflow_id}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/debug/cache")
async def debug_cache():
    """Debug endpoint to see current cache state"""
    return {
        "agent_cache_keys": list(agent_cache.keys()),
        "results_cache_keys": {
            agent_id: list(results.keys()) 
            for agent_id, results in results_cache.items()
        },
        "results_cache_full": results_cache,
        "module_states_keys": list(request_id_states_cache.keys())
    }