import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict
import uuid

from fastapi import FastAPI, Query, HTTPException

from nats_observe.config import NATSotelSettings
from nats_observe.client import Client as NATSotel

from nats.aio.msg import Msg

from models import AgentHeartbeat, AgentInfo

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

# 🧠 In-memory cache
agent_cache: Dict[str, AgentInfo] = {}
# 📊 Results cache
results_cache: Dict[str, Dict[str, Any]] = {}  # {agent_id: {request_id: result}}
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

            if existing:
                existing.last_seen = hb.timestamp
                existing.alive = True
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

    await nc.subscribe(HEARTBEAT_SUBJECT, cb=heartbeat_handler)
    print(f"[Cache] Subscribed to {HEARTBEAT_SUBJECT}")
    
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
                # Store result in cache
                if agent_id not in results_cache:
                    results_cache[agent_id] = {}
                results_cache[agent_id][request_id] = data
                print(f"[Results] Stored result for agent {agent_id}, request {request_id}")
            else:
                print(f"[Results] Received message without ID from agent {agent_id}")
                
        except Exception as e:
            print(f"[Results] Error handling result from agent {agent_id}: {e}")
    
    # Subscribe to the agent's output topic
    out_topic = f"agent.{agent_id}.out"
    try:
        await nc.subscribe(out_topic, cb=result_handler)
        print(f"[Results] Successfully subscribed to {out_topic}")
    except Exception as e:
        print(f"[Results] Error subscribing to {out_topic}: {e}")
        raise


# 🧹 Background cleanup task (mark dead)
async def cleanup_agents():
    while True:
        now = datetime.now(timezone.utc)
        for agent_id, info in agent_cache.items():
            if (now - info.last_seen) > timedelta(seconds=HEARTBEAT_TIMEOUT):
                if info.alive:
                    info.alive = False
                    print(f"[Cache] Agent {agent_id} marked DEAD (last seen {info.last_seen})")
        await asyncio.sleep(HEARTBEAT_INTERVAL)


# 🔌 Startup
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(nats_connect())
    asyncio.create_task(cleanup_agents())
    
    
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
    agent = agent_cache.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.get("/agents/{agent_id}/results/{request_id}")
async def get_agent_result(agent_id: str, request_id: str):
    """
    Get result for a specific agent and request ID.
    """
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