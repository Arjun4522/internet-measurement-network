import json
import time
import random
import asyncio
from typing import Optional, Type
from aiori_agent.base import BaseWorker
from nats.aio.msg import Msg
from aiori_agent.model import MeasurementQuery
from pydantic import BaseModel, Field


class FaultyQuery(MeasurementQuery):
    message: str = Field(title="Message", description="The message to process")
    delay: Optional[int] = Field(default=None, title="Delay", description="Simulated processing delay in seconds")
    crash: Optional[bool] = Field(default=False, title="Crash", description="Whether to simulate a crash")


class FaultyModule(BaseWorker):
    """
    A test module to simulate failure, crash, or delay based on input.
    """

    def __init__(self, name: str, agent, nc, logger, shared):
        super().__init__(name, agent, nc, logger, shared)

        self.sub_in = f"agent.{self.agent.agent_id}.{self.name}.in"
        self.sub_out = f"agent.{self.agent.agent_id}.{self.name}.out"
        self.sub_err = f"agent.{self.agent.agent_id}.{self.name}.error"
        self.processed_ids = set()

    def serializer(self) -> Type[MeasurementQuery]:
        return FaultyQuery

    async def setup(self):
        return True

    async def run(self):
        await self.nc.subscribe(self.sub_in, cb=self.handle)
        self.logger.info(f"{self.name}: Listening on {self.sub_in}")

    async def handle(self, msg: Msg):
        request_id = None
        try:
            payload = json.loads(msg.data.decode())
            self.logger.info(f"{self.name}: Received {payload}")
            request_id = payload.get("id")  # Extract request ID for state tracking
            
            # Extract trace context if present
            trace_context = payload.pop('_trace_context', None)
            if trace_context:
                try:
                    from opentelemetry.propagate import extract
                    # Extract trace context to continue the trace
                    context = extract(trace_context)
                    # Set the current context (this would normally be done with a span)
                except Exception as e:
                    self.logger.debug(f"Could not extract trace context: {e}")

            # Report that we're running this specific request
            if request_id:
                await self._report_state("running", details={"action": "processing_request"}, request_id=request_id)

            # Simulate delay
            if payload.get("delay"):
                await asyncio.sleep(payload["delay"])
                self.logger.debug(f"{self.name}: Finished simulated delay")

            # Simulate crash
            if payload.get("crash"):
                raise RuntimeError("Intentional crash triggered.")

            # Simulate duplicate processing (ACID)
            message_id = payload.get("id")
            if message_id and message_id in self.processed_ids:
                self.logger.warning(
                    f"{self.name}: Duplicate message ignored: {message_id}"
                )
                # Report error with request ID
                if request_id:
                    await self._report_state("error", "Duplicate message", details={"action": "duplicate_ignored"}, request_id=request_id)
                return
            if message_id:
                self.processed_ids.add(message_id)

            # Echo back
            response = {
                "from_module": self.name,
                "processed_at": time.time(),
                "input": payload,
            }
            await self.nc.publish(self.sub_out, json.dumps(response).encode())
            
            # Report completion with request ID
            if request_id:
                await self._report_state("completed", details={"action": "request_completed"}, request_id=request_id)

        except Exception as e:
            self.logger.exception(f"{self.name}: Failed during handle")
            await self.nc.publish(self.sub_err, str(e).encode())
            
            # Report error with request ID
            if request_id:
                await self._report_state("error", str(e), details={"action": "request_failed"}, request_id=request_id)
