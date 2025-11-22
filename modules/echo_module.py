import json
import time
from typing import Optional, Type
from aiori_agent.base import BaseWorker
from nats.aio.msg import Msg
from aiori_agent.model import MeasurementQuery
from pydantic import BaseModel, Field


class EchoQuery(MeasurementQuery):
    message: str = Field(title="Message", description="The message to echo back")


class WorkingModule(BaseWorker):
    """
    A minimal working module that echoes back received messages.
    """

    def __init__(self, name: str, agent, nc, logger, shared):
        super().__init__(name, agent, nc, logger, shared)

        self.sub_in = f"agent.{self.agent.agent_id}.{self.name}.in"
        self.sub_out = f"agent.{self.agent.agent_id}.{self.name}.out"
        self.sub_err = f"agent.{self.agent.agent_id}.{self.name}.error"

    def serializer(self) -> Type[MeasurementQuery]:
        return EchoQuery

    async def setup(self):
        return True

    async def run(self):
        """
        Subscribes to the input subject and echoes data to output.
        """
        await self.nc.subscribe(self.sub_in, cb=self.handle)
        self.logger.info(f"{self.name}: Listening on {self.sub_in}")

    async def handle(self, msg: Msg):
        """
        Processes incoming message and sends output.
        """
        request_id = None
        try:
            data = msg.data.decode()
            self.logger.debug(f"{self.name}: Received {data}")
            payload = json.loads(data)
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
            
            payload["processed_at"] = time.time()
            payload["from_module"] = self.name

            await self.nc.publish(self.sub_out, json.dumps(payload).encode())
            self.logger.debug(f"{self.name}: Published to {self.sub_out}")
            
            # Report completion with request ID
            if request_id:
                await self._report_state("completed", details={"action": "request_completed"}, request_id=request_id)
        except Exception as e:
            self.logger.exception(f"{self.name}: Error during handle")
            await self.nc.publish(self.sub_err, str(e).encode())
            
            # Report error with request ID
            if request_id:
                await self._report_state("error", str(e), details={"action": "request_failed"}, request_id=request_id)
