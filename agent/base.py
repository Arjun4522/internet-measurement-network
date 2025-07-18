import os
import sys
import time
import asyncio
import importlib.util
import traceback
import logging
from pathlib import Path
from nats.aio.client import Client as NATS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("agent")

# Abstract class that each module must inherit
class BaseWorker:
    def __init__(self, name, agent, nc, logger, shared):
        self.name = name
        self.agent = agent
        self.nc = nc
        self.running = False
        self.logger = logger.getChild(name)
        self.shared = shared
        self.task = None

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
    
    async def stop(self, msg="Exclusive stop", timeout = 20):
        self.task.cancel(msg=msg)
        ct = time.perf_counter() + timeout
        while self.task and not self.task.done():
            if ct < time.perf_counter():
                raise asyncio.exceptions.TimeoutError()
            await asyncio.sleep(0.1)
        self.running = False
        self.task = None
        return True
