import grpc
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import os

# Import the generated gRPC client code
import dbos_pb2
import dbos_pb2_grpc

# Import OpenTelemetry for trace context propagation
OTEL_AVAILABLE = True
try:
    from opentelemetry import trace
    from opentelemetry.propagate import inject
    from opentelemetry.instrumentation.grpc import GrpcAioInstrumentorClient
except ImportError:
    OTEL_AVAILABLE = False

class DBOSClient:
    def __init__(self, dbos_address: str = "localhost:50051"):
        self.dbos_address = dbos_address
        self.channel = None
        self.stub = None
        # Initialize OpenTelemetry tracer
        self.tracer = trace.get_tracer(__name__) if OTEL_AVAILABLE else None
        
    async def connect(self):
        """Establish connection to DBOS service"""
        if self.channel is None:
            self.channel = grpc.aio.insecure_channel(self.dbos_address)
            self.stub = dbos_pb2_grpc.DBOSStub(self.channel)
            
    async def disconnect(self):
        """Close connection to DBOS service"""
        if self.channel:
            await self.channel.close()
            self.channel = None
            self.stub = None
            
    async def register_agent(self, agent_info) -> bool:
        """Register an agent with DBOS"""
        if not self.stub:
            await self.connect()
            
        try:
            # Convert AgentInfo to DBOS Agent protobuf message
            # Convert config values to strings to match protobuf map<string, string> type
            config_str_values = {k: str(v) for k, v in agent_info.config.items()}
            
            agent_proto = dbos_pb2.Agent(
                id=agent_info.agent_id,
                hostname=agent_info.hostname,
                alive=agent_info.alive,
                last_seen=int(agent_info.last_seen.timestamp()),
                first_seen=int(agent_info.first_seen.timestamp()),
                config=config_str_values,
                total_heartbeats=agent_info.total_heartbeats
            )
            
            request = dbos_pb2.RegisterAgentRequest(agent=agent_proto)
            # Add trace context propagation
            metadata = []
            if OTEL_AVAILABLE:
                try:
                    # Create a carrier dict for trace context
                    carrier = {}
                    inject(carrier)
                    # Convert carrier to gRPC metadata format (list of tuples)
                    metadata = [(key, value) for key, value in carrier.items()]
                except Exception as e:
                    print(f"Warning: Could not inject trace context: {e}")
                    metadata = []  # Use empty metadata if injection fails
            
            response = await self.stub.RegisterAgent(request, metadata=metadata)
            return response.success
        except Exception as e:
            print(f"Error registering agent with DBOS: {e}")
            return False
            
    async def get_agent(self, agent_id: str):
        """Get agent information from DBOS"""
        if not self.stub:
            await self.connect()
            
        try:
            request = dbos_pb2.GetAgentRequest(agent_id=agent_id)
            # Add trace context propagation
            metadata = []
            if OTEL_AVAILABLE:
                try:
                    # Create a carrier dict for trace context
                    carrier = {}
                    inject(carrier)
                    # Convert carrier to gRPC metadata format (list of tuples)
                    metadata = [(key, value) for key, value in carrier.items()]
                except Exception as e:
                    print(f"Warning: Could not inject trace context: {e}")
                    metadata = []  # Use empty metadata if injection fails
            
            response = await self.stub.GetAgent(request, metadata=metadata)
            
            if response.found:
                agent_proto = response.agent
                # Return a dictionary similar to AgentInfo
                return {
                    'agent_id': agent_proto.id,
                    'hostname': agent_proto.hostname,
                    'alive': agent_proto.alive,
                    'last_seen': datetime.fromtimestamp(agent_proto.last_seen),
                    'first_seen': datetime.fromtimestamp(agent_proto.first_seen),
                    'config': dict(agent_proto.config),
                    'total_heartbeats': agent_proto.total_heartbeats
                }
            return None
        except Exception as e:
            print(f"Error getting agent from DBOS: {e}")
            return None
            
    async def list_agents(self):
        """List all agents from DBOS"""
        if not self.stub:
            await self.connect()
            
        try:
            request = dbos_pb2.ListAgentsRequest()
            # Add trace context propagation
            metadata = []
            if OTEL_AVAILABLE:
                try:
                    # Create a carrier dict for trace context
                    carrier = {}
                    inject(carrier)
                    # Convert carrier to gRPC metadata format (list of tuples)
                    metadata = [(key, value) for key, value in carrier.items()]
                except Exception as e:
                    print(f"Warning: Could not inject trace context: {e}")
                    metadata = []  # Use empty metadata if injection fails
            
            response = await self.stub.ListAgents(request, metadata=metadata)
            
            agents = []
            for agent_proto in response.agents:
                agents.append({
                    'agent_id': agent_proto.id,
                    'hostname': agent_proto.hostname,
                    'alive': agent_proto.alive,
                    'last_seen': datetime.fromtimestamp(agent_proto.last_seen),
                    'first_seen': datetime.fromtimestamp(agent_proto.first_seen),
                    'config': dict(agent_proto.config),
                    'total_heartbeats': agent_proto.total_heartbeats
                })
            return agents
        except Exception as e:
            print(f"Error listing agents from DBOS: {e}")
            return []
            
    async def set_module_state(self, module_state) -> bool:
        """Set module state in DBOS"""
        if not self.stub:
            await self.connect()
            
        try:
            # Convert ModuleState to DBOS ModuleState protobuf message
            state_proto = dbos_pb2.ModuleState(
                agent_id=module_state.agent_id,
                module_name=module_state.module_name,
                state=module_state.state,
                error_message=module_state.error_message or "",
                details=module_state.details or {},
                timestamp=int(module_state.timestamp.timestamp()),
                request_id=getattr(module_state, 'request_id', '')
            )
            
            request = dbos_pb2.SetModuleStateRequest(state=state_proto)
            # Add trace context propagation
            metadata = []
            if OTEL_AVAILABLE:
                try:
                    # Create a carrier dict for trace context
                    carrier = {}
                    inject(carrier)
                    # Convert carrier to gRPC metadata format (list of tuples)
                    metadata = [(key, value) for key, value in carrier.items()]
                except Exception as e:
                    print(f"Warning: Could not inject trace context: {e}")
                    metadata = []  # Use empty metadata if injection fails
            
            response = await self.stub.SetModuleState(request, metadata=metadata)
            return response.success
        except Exception as e:
            print(f"Error setting module state in DBOS: {e}")
            return False
            
    async def get_module_state(self, request_id: str):
        """Get module state from DBOS by request ID"""
        if not self.stub:
            await self.connect()
            
        try:
            request = dbos_pb2.GetModuleStateRequest(request_id=request_id)
            # Add trace context propagation
            metadata = []
            if OTEL_AVAILABLE:
                try:
                    # Create a carrier dict for trace context
                    carrier = {}
                    inject(carrier)
                    # Convert carrier to gRPC metadata format (list of tuples)
                    metadata = [(key, value) for key, value in carrier.items()]
                except Exception as e:
                    print(f"Warning: Could not inject trace context: {e}")
                    metadata = []  # Use empty metadata if injection fails
            
            response = await self.stub.GetModuleState(request, metadata=metadata)
            
            if response.found:
                state_proto = response.state
                # Return a dictionary similar to ModuleState
                return {
                    'agent_id': state_proto.agent_id,
                    'module_name': state_proto.module_name,
                    'state': state_proto.state,
                    'timestamp': datetime.fromtimestamp(state_proto.timestamp),
                    'error_message': state_proto.error_message if state_proto.error_message else None,
                    'details': dict(state_proto.details) if state_proto.details else None
                }
            return None
        except Exception as e:
            print(f"Error getting module state from DBOS: {e}")
            return None
            
    async def store_result(self, agent_id: str, request_id: str, module_name: str, data: bytes) -> bool:
        """Store measurement result in DBOS"""
        if not self.stub:
            await self.connect()
            
        try:
            result_proto = dbos_pb2.MeasurementResult(
                id=request_id,
                agent_id=agent_id,
                module_name=module_name,
                data=data,
                timestamp=int(datetime.now().timestamp())
            )
            
            request = dbos_pb2.StoreResultRequest(result=result_proto)
            # Add trace context propagation
            metadata = []
            if OTEL_AVAILABLE:
                try:
                    # Create a carrier dict for trace context
                    carrier = {}
                    inject(carrier)
                    # Convert carrier to gRPC metadata format (list of tuples)
                    metadata = [(key, value) for key, value in carrier.items()]
                except Exception as e:
                    print(f"Warning: Could not inject trace context: {e}")
                    metadata = []  # Use empty metadata if injection fails
            
            response = await self.stub.StoreResult(request, metadata=metadata)
            return response.success
        except Exception as e:
            print(f"Error storing result in DBOS: {e}")
            return False
            
    async def get_result(self, agent_id: str, request_id: str) -> Optional[bytes]:
        """Get measurement result from DBOS"""
        if not self.stub:
            await self.connect()
            
        try:
            request = dbos_pb2.GetResultRequest(agent_id=agent_id, request_id=request_id)
            # Add trace context propagation
            metadata = []
            if OTEL_AVAILABLE:
                try:
                    # Create a carrier dict for trace context
                    carrier = {}
                    inject(carrier)
                    # Convert carrier to gRPC metadata format (list of tuples)
                    metadata = [(key, value) for key, value in carrier.items()]
                except Exception as e:
                    print(f"Warning: Could not inject trace context: {e}")
                    metadata = []  # Use empty metadata if injection fails
            
            response = await self.stub.GetResult(request, metadata=metadata)
            
            if response.found:
                return response.result.data
            return None
        except Exception as e:
            print(f"Error getting result from DBOS: {e}")
            return None

# Global DBOS client instance
dbos_client: Optional[DBOSClient] = None

async def initialize_dbos_client():
    """Initialize the global DBOS client"""
    global dbos_client
    dbos_address = os.environ.get("DBOS_ADDRESS", "localhost:50051")
    dbos_client = DBOSClient(dbos_address)
    await dbos_client.connect()
    print(f"DBOS client initialized with address: {dbos_address}")
    
async def shutdown_dbos_client():
    """Shutdown the global DBOS client"""
    global dbos_client
    if dbos_client:
        await dbos_client.disconnect()
        dbos_client = None
        print("DBOS client disconnected")