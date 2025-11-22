import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict
import uuid

from fastapi import FastAPI, Query, HTTPException

from nats_observe.config import NATSotelSettings
from nats_observe.client import Client as NATSotel

from nats.aio.msg import Msg

from models import AgentHeartbeat, AgentInfo, ModuleState

from openapi_schema_validator import validate
from jsonschema.exceptions import ValidationError

# ======== CONFIG ============
import os
NATS_URL = [os.environ.get("NATS_URL", "nats://localhost:4222")]
HEARTBEAT_SUBJECT = "agent.heartbeat_module"
HEARTBEAT_INTERVAL = 5                      # Agents send heartbeat every 5s
HEARTBEAT_TIMEOUT = HEARTBEAT_INTERVAL * 2  # If no heartbeat in 10s => dead

# OTel configuration
OTLP_TRACE_ENDPOINT = os.environ.get("OTLP_TRACE_ENDPOINT", "otel-collector:4317")
OTLP_METRICS_ENDPOINT = os.environ.get("OTLP_METRICS_ENDPOINT", "otel-collector:4317")
OTLP_LOGS_ENDPOINT = os.environ.get("OTLP_LOGS_ENDPOINT", "otel-collector:4317")
# ============================

# 🧠 In-memory cache (fallback when DBOS is unavailable)
agent_cache: Dict[str, AgentInfo] = {}
# 📊 Results cache (fallback when DBOS is unavailable)
results_cache: Dict[str, Dict[str, Any]] = {}  # {agent_id: {request_id: result}}
# 🆔 Request ID to module state mapping (fallback when DBOS is unavailable)
request_id_states_cache: Dict[str, ModuleState] = {}  # {request_id: ModuleState}

# DBOS client
from dbos_client import dbos_client, initialize_dbos_client, shutdown_dbos_client
settings = NATSotelSettings(
    service_name="server", 
    servers=NATS_URL,
    otlp_trace_endpoint=OTLP_TRACE_ENDPOINT,
    otlp_logs_endpoint=OTLP_LOGS_ENDPOINT
)
nc: NATSotel = NATSotel(settings)

app = FastAPI(title="Agent Server", version="1.0")


# 📡 NATS connection & subscription
async def nats_connect():
    await nc.connect(settings.servers, name="server", verbose=True, reconnect_time_wait=0)
    print(f"[Cache] Connected to NATS: {NATS_URL}")

    async def heartbeat_handler(msg: Msg):
        try:
            data = json.loads(msg.data.decode())
            hb = AgentHeartbeat(agent_id=data["agent"]["id"], hostname=data["agent"]["hostname"])

            existing = agent_cache.get(hb.agent_id)
            now = datetime.now(timezone.utc)

            # Create agent info object
            agent_info = AgentInfo(
                agent_id=hb.agent_id,
                alive=True,
                hostname=hb.hostname,
                last_seen=hb.timestamp,
                config=data,
                first_seen=now if not existing else existing.first_seen,
                total_heartbeats=(existing.total_heartbeats + 1) if existing else 1
            )

            # Register/update agent in DBOS if enabled
            if os.environ.get("USE_DBOS", "false").lower() == "true":
                try:
                    from dbos_client import dbos_client
                    if dbos_client:
                        success = await dbos_client.register_agent(agent_info)
                        if success:
                            print(f"[DBOS] Registered agent: {hb.agent_id}")
                        else:
                            print(f"[DBOS] Failed to register agent: {hb.agent_id}")
                except Exception as e:
                    print(f"[DBOS] Error registering agent {hb.agent_id}: {e}")

            if existing:
                existing.last_seen = hb.timestamp
                existing.alive = True
                # Check if config has changed and resubscribe if needed
                if existing.config != data:
                    print(f"[Subscription] Agent {hb.agent_id} config updated, resubscribing to results...")
                    try:
                        await subscribe_to_agent_results(hb.agent_id)
                        print(f"[Subscription] Successfully resubscribed to results for agent: {hb.agent_id}")
                    except Exception as e:
                        print(f"[Subscription] Error resubscribing to results for agent {hb.agent_id}: {e}")
                existing.config = data
                existing.total_heartbeats += 1
                print(f"[Cache] Updated heartbeat: {hb.agent_id} @ {hb.timestamp}")
            else:
                agent_cache[hb.agent_id] = agent_info
                
                # Subscribe to result topics for this new agent
                print(f"[Subscription] New agent detected: {hb.agent_id}, subscribing to results...")
                try:
                    await subscribe_to_agent_results(hb.agent_id)
                    print(f"[Subscription] Successfully subscribed to results for agent: {hb.agent_id}")
                except Exception as e:
                    print(f"[Subscription] Error subscribing to results for agent {hb.agent_id}: {e}")
                
            print(f"[Cache] Updated heartbeat: {hb.agent_id} @ {hb.timestamp}")

        except Exception as e:
            print("[Cache] Error parsing heartbeat:", e)

    async def module_state_handler(msg: Msg):
        try:
            data = json.loads(msg.data.decode())
            agent_id = data["agent_id"]
            module_name = data["module_name"]
            state = data["state"]
            request_id = data.get("request_id")  # Get request_id if available
            
            # Create module state object
            module_state = ModuleState(
                agent_id=agent_id,
                module_name=module_name,
                state=state,
                error_message=data.get("error_message"),
                details=data.get("details")
            )
            
            # Store in DBOS if enabled
            if os.environ.get("USE_DBOS", "false").lower() == "true":
                try:
                    from dbos_client import dbos_client
                    if dbos_client:
                        # Add request_id to module_state for DBOS storage
                        setattr(module_state, 'request_id', request_id or '')
                        success = await dbos_client.set_module_state(module_state)
                        if success:
                            print(f"[DBOS] Stored module state for {agent_id}.{module_name}")
                        else:
                            print(f"[DBOS] Failed to store module state for {agent_id}.{module_name}")
                except Exception as e:
                    print(f"[DBOS] Error storing module state for {agent_id}.{module_name}: {e}")
            
            # Store in cache by request ID if available
            if request_id:
                request_id_states_cache[request_id] = module_state
            
            print(f"[ModuleState] Updated state for {agent_id}.{module_name}: {state}")
            if request_id:
                print(f"[ModuleState] Also stored state for request_id: {request_id}")
        except Exception as e:
            print("[ModuleState] Error parsing module state:", e)

    await nc.subscribe(HEARTBEAT_SUBJECT, cb=heartbeat_handler)
    await nc.subscribe("agent.module.state", cb=module_state_handler)
    print(f"[Cache] Subscribed to {HEARTBEAT_SUBJECT} and agent.module.state")
    
    # Also subscribe to existing agents after a delay
    print("[Startup] Scheduling subscription to existing agents...")
    asyncio.create_task(subscribe_existing_agents())


# 📥 Subscribe to agent result topics
async def subscribe_to_agent_results(agent_id: str):
    """Subscribe to result topics for a specific agent"""
    print(f"[Subscription] Attempting to subscribe to results for agent: {agent_id}")
    
    async def result_handler(msg: Msg):
        try:
            print(f"[Results] Received message on result topic for agent {agent_id}")
            data = json.loads(msg.data.decode())
            request_id = data.get("id")
            
            if request_id:
                # Store result in DBOS if enabled
                if os.environ.get("USE_DBOS", "false").lower() == "true":
                    try:
                        from dbos_client import dbos_client
                        if dbos_client:
                            # Convert data to JSON bytes for DBOS storage
                            result_data = json.dumps(data).encode('utf-8')
                            success = await dbos_client.store_result(agent_id, request_id, "unknown", result_data)
                            if success:
                                print(f"[DBOS] Stored result for agent {agent_id}, request {request_id}")
                            else:
                                print(f"[DBOS] Failed to store result for agent {agent_id}, request {request_id}")
                    except Exception as e:
                        print(f"[DBOS] Error storing result for agent {agent_id}, request {request_id}: {e}")
                
                # Store result in cache
                if agent_id not in results_cache:
                    results_cache[agent_id] = {}
                results_cache[agent_id][request_id] = data
                print(f"[Results] Stored result for agent {agent_id}, request {request_id}")
            else:
                print(f"[Results] Received message without ID from agent {agent_id}")
                
        except Exception as e:
            print(f"[Results] Error handling result from agent {agent_id}: {e}")
    
    # Subscribe to the agent's generic output topic (for ping module)
    generic_out_topic = f"agent.{agent_id}.out"
    try:
        await nc.subscribe(generic_out_topic, cb=result_handler)
        print(f"[Results] Successfully subscribed to {generic_out_topic}")
    except Exception as e:
        print(f"[Results] Error subscribing to {generic_out_topic}: {e}")
        raise
    
    # Subscribe to module-specific output topics (for echo and faulty modules)
    # Get agent config to determine which modules exist
    agent_info = agent_cache.get(agent_id)
    if agent_info and agent_info.config and "agent" in agent_info.config and "modules" in agent_info.config["agent"]:
        modules_spec = agent_info.config["agent"]["modules"].get("spec", {})
        for module_name, module_config in modules_spec.items():
            if "output_subject" in module_config:
                module_out_topic = module_config["output_subject"]
                # Only subscribe to module-specific topics (not the generic one we already subscribed to)
                if module_out_topic != generic_out_topic:
                    try:
                        await nc.subscribe(module_out_topic, cb=result_handler)
                        print(f"[Results] Successfully subscribed to {module_out_topic}")
                    except Exception as e:
                        print(f"[Results] Error subscribing to {module_out_topic}: {e}")


# 🧹 Background cleanup task (mark dead)
async def cleanup_agents():
    while True:
        now = datetime.now(timezone.utc)
        for agent_id, info in agent_cache.items():
            if (now - info.last_seen) > timedelta(seconds=HEARTBEAT_TIMEOUT):
                if info.alive:
                    info.alive = False
                    print(f"[Cache] Agent {agent_id} marked DEAD (last seen {info.last_seen}")
        await asyncio.sleep(HEARTBEAT_INTERVAL)


# 🔌 Startup
@app.on_event("startup")
async def startup_event():
    # Initialize DBOS client if enabled
    if os.environ.get("USE_DBOS", "false").lower() == "true":
        try:
            from dbos_client import initialize_dbos_client
            await initialize_dbos_client()
            print("DBOS integration enabled")
        except Exception as e:
            print(f"Failed to initialize DBOS client: {e}")
    else:
        print("DBOS integration disabled")
        
    asyncio.create_task(nats_connect())
    asyncio.create_task(cleanup_agents())

# 🔌 Shutdown
@app.on_event("shutdown")
async def shutdown_event():
    # Shutdown DBOS client if enabled
    if os.environ.get("USE_DBOS", "false").lower() == "true":
        try:
            from dbos_client import shutdown_dbos_client
            await shutdown_dbos_client()
            print("DBOS client shutdown")
        except Exception as e:
            print(f"Error shutting down DBOS client: {e}")
    
    
async def subscribe_existing_agents():
    """Subscribe to result topics for existing agents"""
    print("[Startup] Waiting for initial heartbeats...")
    # Wait a bit for initial heartbeats to come in
    await asyncio.sleep(2)
    
    print(f"[Startup] Found {len(agent_cache)} agents in cache, subscribing to results...")
    # Subscribe to existing agents
    for agent_id in list(agent_cache.keys()):  # Use list() to avoid "dictionary changed size during iteration"
        print(f"[Startup] Subscribing to results for existing agent: {agent_id}")
        try:
            await subscribe_to_agent_results(agent_id)
            print(f"[Startup] Successfully subscribed to results for agent: {agent_id}")
        except Exception as e:
            print(f"[Startup] Error subscribing to results for agent {agent_id}: {e}")


# ======================
#       API ROUTES
# ======================

@app.get("/")
async def root():
    return {
        "status": "ok",
        "total_agents": len(agent_cache),
        "alive_agents": len([a for a in agent_cache.values() if a.alive]),
    }


@app.get("/agents", response_model=Dict[str, AgentInfo])
async def get_all_agents():
    """
    Get all agents (alive and dead) with metadata.
    """
    return agent_cache


@app.get("/agents/alive", response_model=Dict[str, AgentInfo])
async def get_alive_agents():
    """
    Get only currently alive agents.
    """
    return {aid: info for aid, info in agent_cache.items() if info.alive}


@app.get("/agents/dead", response_model=Dict[str, AgentInfo])
async def get_dead_agents():
    """
    Get only agents considered dead (missed heartbeat).
    """
    return {aid: info for aid, info in agent_cache.items() if not info.alive}


@app.get("/agents/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str):
    """
    Get detailed info about a specific agent.
    """
    # Try to get from DBOS if enabled
    if os.environ.get("USE_DBOS", "false").lower() == "true":
        try:
            from dbos_client import dbos_client
            if dbos_client:
                dbos_agent = await dbos_client.get_agent(agent_id)
                if dbos_agent:
                    return dbos_agent
        except Exception as e:
            print(f"[DBOS] Error getting agent {agent_id}: {e}")
    
    # Fallback to cache
    agent = agent_cache.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.get("/agents/{agent_id}/results/{request_id}")
async def get_agent_result(agent_id: str, request_id: str):
    """
    Get result for a specific agent and request ID.
    """
    # Try to get from DBOS if enabled
    if os.environ.get("USE_DBOS", "false").lower() == "true":
        try:
            from dbos_client import dbos_client
            if dbos_client:
                result_data = await dbos_client.get_result(agent_id, request_id)
                if result_data:
                    # Convert bytes back to JSON
                    try:
                        result = json.loads(result_data.decode('utf-8'))
                        return result
                    except Exception as e:
                        print(f"[DBOS] Error decoding result for agent {agent_id}, request {request_id}: {e}")
        except Exception as e:
            print(f"[DBOS] Error getting result for agent {agent_id}, request {request_id}: {e}")
    
    # Fallback to cache
    agent_results = results_cache.get(agent_id, {})
    result = agent_results.get(request_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
        
    return result


@app.get("/agents/{agent_id}/results")
async def get_agent_results(agent_id: str):
    """
    Get all results for a specific agent.
    """
    return results_cache.get(agent_id, {})


@app.delete("/agents/{agent_id}/results/{request_id}")
async def delete_agent_result(agent_id: str, request_id: str):
    """
    Delete a specific result for an agent.
    """
    agent_results = results_cache.get(agent_id, {})
    if request_id in agent_results:
        del agent_results[request_id]
        return {"message": "Result deleted"}
    else:
        raise HTTPException(status_code=404, detail="Result not found")


@app.post("/agent/{agent_id}/{module_name}")
async def run_module(
        agent_id: str, 
        module_name: str, 
        module_request: Dict[str, Any], 
        untracked: bool = Query(False) # Query parameter with default and alias
    ):
    try:
        agent = agent_cache.get(agent_id)
        
        if not agent or not agent.alive:
            return {"error": "Agent is not alive"}
        
        if not untracked:
            if "id" not in module_request:
                module_request["id"] = str(uuid.uuid4())
        
        # Validation
        all_spec = agent.config["agent"]["modules"]["spec"]
    
        if module_name in all_spec:
            try:
                validate(module_request, all_spec[module_name]['input_schema'])
            except ValidationError as ex:
                return {"error": "Validation Error", "message": str(ex)}
            except Exception as ex:
                return {"error": "Unknown Error", "message": str(ex)}

            await nc.publish(all_spec[module_name]['input_subject'], json.dumps(module_request).encode())

        return {
            "message": "success",
            "id": module_request.get("id")
        }
    except Exception as ex:
        return {"error": "..."}


# ======================
#    MODULE STATE ROUTES
# ======================

# @app.get("/agents/{agent_id}/modules")
# async def get_agent_modules_states(agent_id: str):
#     """
#     Get all module states for a specific agent.
#     """
#     # Return empty dict since we're no longer tracking module states
#     return {}


# @app.get("/agents/{agent_id}/modules/{module_name}")
# async def get_module_state(agent_id: str, module_name: str):
#     """
#     Get the state of a specific module for an agent.
#     """
#     # Return 404 since we're no longer tracking module states
#     raise HTTPException(status_code=404, detail="Module state tracking disabled")


@app.get("/modules/states")
async def get_all_module_states():
    """
    Get all module states across all agents.
    """
    # Return empty dict since we're no longer tracking module states
    return {}


@app.get("/modules/states/{request_id}")
async def get_module_state_by_request_id(request_id: str):
    """
    Get module state by request ID.
    """
    # Try to get from DBOS if enabled
    if os.environ.get("USE_DBOS", "false").lower() == "true":
        try:
            from dbos_client import dbos_client
            if dbos_client:
                dbos_state = await dbos_client.get_module_state(request_id)
                if dbos_state:
                    return dbos_state
        except Exception as e:
            print(f"[DBOS] Error getting module state for request {request_id}: {e}")
    
    # Fallback to cache
    module_state = request_id_states_cache.get(request_id)
    
    if not module_state:
        raise HTTPException(status_code=404, detail="Module state not found for this request ID")
        
    return module_state.dict()