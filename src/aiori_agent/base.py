import os
import sys
import time
import asyncio
import logging
import traceback
import importlib.util
from typing import Optional, Type, override
from pathlib import Path
import uuid

from pydantic import BaseModel, Field, computed_field

from nats.aio.client import Client as NATS

from aiori_agent.utils import get_model_name


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("agent")


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
            await self.run()
        except Exception as ex:
            self.running = False
            await crash_handler(self.name, ex)

    def start(self, crash_handler):
        self.task = asyncio.create_task(self.__run__(crash_handler=crash_handler))

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

class MeasurementQuery(BaseModel):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4)
    # type: Optional[str] = Field(default_factory=get_model_name)

    # @computed_field
    # @property
    @classmethod
    def model_type(cls) -> str:
        return get_model_name(cls)