import sys
import time
import asyncio
import logging
import json
from typing import Annotated, Optional, Type
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("agent")


class ModuleStateEnum(str, Enum):
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    FAILED = "failed"


# Abstract class that each module must inherit
class BaseWorker:
    def __init__(self, name, agent, nc, logger, shared):
        self.name = name
        self.agent: "Agent" = agent
        self.nc = nc
        self.running = False
        self.logger = logger.getChild(name)
        self.shared = shared
        self.task = None

        self.sub_in = None
        self.sub_out = None
        self.sub_err = None
        
    async def _report_state(self, state, error_message=None, details=None, request_id=None):
        """Report module state to NATS"""
        state_data = {
            "agent_id": self.agent.agent_id,
            "module_name": self.name,
            "state": state,
            "error_message": error_message,
            "details": details,
            "request_id": request_id  # Include request_id if available
        }
        try:
            # Add trace context to the state message
            try:
                from opentelemetry.propagate import inject
                trace_data = {}
                inject(trace_data)
                state_data['_trace_context'] = trace_data
            except Exception as e:
                self.logger.debug(f"Could not inject trace context: {e}")
                
            await self.nc.publish("agent.module.state", json.dumps(state_data).encode())
        except Exception as e:
            self.logger.error(f"Failed to report state: {e}")

    def serializer(self, ) -> Optional[Type["MeasurementQuery"]]:
        # raise NotImplementedError("Worker must implement serializer()")
        return None

    async def setup(self):
        raise NotImplementedError("Worker must implement setup()")

    async def run(self):
        raise NotImplementedError("Worker must implement run()")

    async def __run__(self, crash_handler):
        try:
            self.running = True
            await self._report_state("started")
            await self.run()
            await self._report_state("completed")
        except Exception as ex:
            self.running = False
            await self._report_state("error", str(ex))
            await crash_handler(self.name, ex)

    def start(self, crash_handler):
        self.task = asyncio.create_task(self.__run__(crash_handler=crash_handler))
        # Report that the module is now running (task created)
        asyncio.create_task(self._report_state("running"))

    async def stop(self, msg="Exclusive stop", timeout=20):
        self.task.cancel(msg=msg)
        ct = time.perf_counter() + timeout
        while self.task and not self.task.done():
            if ct < time.perf_counter():
                raise asyncio.exceptions.TimeoutError()
            await asyncio.sleep(0.1)
        self.running = False
        self.task = None
        return True