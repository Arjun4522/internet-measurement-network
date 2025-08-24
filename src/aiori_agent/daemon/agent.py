import asyncio
from typing import List
from aiori_agent.config import settings
from aiori_agent.module.base import logger, BaseWorker
from aiori_agent.module.module_manager import ModuleManager
from nats.aio.client import Client as NATS


class NatsClient:
    """
    Manages a shared NATS connection using async context management.
    """

    def __init__(self, name:str, url: List[str] = settings.nats_url,):
        self.url = url
        self.name = name
        self.nc = NATS()

    async def __aenter__(self):
        await self.nc.connect(
            servers = self.url,
            name = self.name,
            pedantic = True,
            verbose = True,

            # Reconnect
            allow_reconnect = True,
            connect_timeout = 5,
            reconnect_time_wait = 3,
            max_reconnect_attempts = 10,

            # Authentication & Authorization
            # user = ,
            # password = ,
            # user_credentials = ,

            # Callbacks
            error_cb = self.error_cb,
            closed_cb = self.closed_cb,
            disconnected_cb = self.disconnected_cb,
            discovered_server_cb = self.disconnected_server_cb,
            reconnected_cb = self.reconnected_cb,
            # user_jwt_cb = ,
            # signature_cb=
        )
        return self.nc

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.nc.is_connected:
            await self.nc.drain()

    async def close(self):
        if self.nc.is_connected:
            await self.nc.close()

    async def disconnected_cb(self, ):
        logger.warning('Got disconnected!')

    async def disconnected_server_cb(self, ):
        logger.warning('Got disconnected server!')

    async def reconnected_cb(self, ):
        logger.warning(f'Got reconnected to {self.nc.connected_url.netloc}')

    async def error_cb(self, e):
        logger.error(f'There was an error: {e}')

    async def closed_cb(self, ):
        logger.warning('Connection is closed')


class Agent:
    """
    Main controller of the system: coordinates NATS, modules, recovery.
    """

    def __init__(self):
        self.agent_id : str = settings.agent_id
        self.agent_name : str = settings.agent_name
        self.manager : ModuleManager = None
        self.nc : NATS = None

    def alive_and_active(self, ):
        if self.nc:
            return self.nc.is_connected
        return False

    async def start(self, ):
        """
        Start NATS and load modules.
        """
        async with NatsClient(name = self.agent_name) as nc:
            self.nc = nc
            self.manager = ModuleManager(self, nc)
            await self.manager.start_all()
            await self._keep_running()

    async def stop(self, ):
        for module_name, module in self.manager.running_workers.items():
            module.stop(msg="Agent stopped", timeout=5)
        await self.nc.close()
        self._keep_running().close()

    async def _keep_running(self):
        """
        Keeps the agent running.
        """
        while True:
            # Wait 1 minute
            await asyncio.sleep(60)
