import json
import time
import logging
import asyncio
from typing import Any, Optional, Type

from aiori_agent.agent import Agent
from aiori_agent.base import BaseWorker, MeasurementQuery

from nats.aio.client import Client as NATS
from nats.aio.msg import Msg

from aiori_agent.utils import check_package_availability, install_package

from pydantic import BaseModel


class PingQuery(MeasurementQuery):
    target: str
    count: Optional[int] = None
    port: Optional[int] = None
    request_id: Optional[int] = None

class PingModule(BaseWorker):
    """
    Ping module with direct agent targeting capability
    """

    def __init__(
        self,
        name: str,
        agent: Agent,
        nc: NATS,
        logger: logging.Logger,
        shared: dict[str, Any],
    ):
        super().__init__(name, agent, nc, logger, shared)
        # Use simple naming pattern like the working module
        self.sub_in = f"agent.{self.agent.agent_id}.in"
        self.sub_out = f"agent.{self.agent.agent_id}.out"
        self.sub_err = f"agent.{self.agent.agent_id}.error"
        self.subscription = None

    def serializer(self, ) -> Type[MeasurementQuery]:
        return PingQuery

    async def setup(self):
        if not check_package_availability("icmplib"):
            install_package("icmplib")

        if not check_package_availability("tcping"):
            install_package("tcping")

        await asyncio.sleep(5)
        return check_package_availability("icmplib") and check_package_availability(
            "tcping"
        )

    async def run(self):
        """
        Subscribes to the input subject and starts handling ping requests.
        """
        try:
            self.subscription = await self.nc.subscribe(self.sub_in, cb=self.handle)
            self.logger.info(f"{self.name}: Listening on {self.sub_in}")
        except Exception as e:
            self.logger.error(f"{self.name}: Failed to subscribe to {self.sub_in}: {e}")
            raise

    async def handle(self, msg: Msg):
        """
        Processes incoming ping requests and sends results.
        """
        try:
            # Log raw message for debugging
            self.logger.debug(f"Received raw message: {msg.data.decode()}")

            data = json.loads(msg.data.decode())
            self.logger.debug(f"{self.name}: Parsed ping request: {data}")

            query = PingQuery(**data)
            model_type = PingQuery.model_type()

            # Validate request
            target = data.get("target")
            count = data.get("count", 3)
            port = data.get("port", 80)

            if not target:
                raise ValueError("Missing 'target' in ping request")

            # Execute ping
            result = await self.pingcmd(target, count, port)

            # Add agent information to result
            result["request_id"] = data.get("request_id", None)

            self.logger.info(f"{self.name}: Ping completed with result: {result}")
            await self.nc.publish(self.sub_out, json.dumps(result).encode("utf-8"))
            self.logger.debug(f"{self.name}: Published to {self.sub_out}")

        except json.JSONDecodeError as e:
            self.logger.error(f"{self.name}: JSON decode error: {e}")
            await self.nc.publish(self.sub_err, f"Invalid JSON: {e}".encode("utf-8"))
        except Exception as e:
            self.logger.exception(f"{self.name}: Error during handle")
            await self.nc.publish(self.sub_err, str(e).encode("utf-8"))

    async def pingcmd(self, addr, count=3, port=80):
        """Perform ping with automatic fallback from ICMP to TCP"""

        from tcping import Ping
        from icmplib import async_ping

        self.logger.info(
            f"{self.name}: Starting ping to {addr} (count={count}, port={port})"
        )

        result = {
            "protocol": None,
            "address": addr,
            "is_alive": False,
            "port": port,
            "timestamp": time.time(),
        }

        try:
            # First try ICMP ping
            self.logger.debug(f"{self.name}: Attempting ICMP ping to {addr}")
            host = await async_ping(addr, count, timeout=5)

            result.update(
                {
                    "protocol": "ICMP",
                    "rtt_min": host.min_rtt,
                    "rtt_avg": host.avg_rtt,
                    "rtt_max": host.max_rtt,
                    "packets_sent": host.packets_sent,
                    "packets_received": host.packets_received,
                    "packet_loss": host.packet_loss,
                    "jitter": host.jitter,
                    "is_alive": host.is_alive,
                }
            )

            self.logger.info(
                f"{self.name}: ICMP ping result - alive: {host.is_alive}, loss: {host.packet_loss}%"
            )

            # Fallback to TCP if ICMP fails
            if not host.is_alive:
                self.logger.info(
                    f"{self.name}: ICMP failed, trying TCP ping to {addr}:{port}"
                )
                await self._tcp_ping_fallback(result, addr, port, count)

        except Exception as e:
            self.logger.error(f"{self.name}: ICMP ping failed with exception: {str(e)}")
            # Try TCP ping as fallback
            await self._tcp_ping_fallback(result, addr, port, count)

        return result

    async def _tcp_ping_fallback(self, result, addr, port, count):
        """Perform TCP ping fallback"""
        try:
            self.logger.debug(f"{self.name}: Starting TCP ping to {addr}:{port}")

            # Create TCP ping with timeout
            tcp_ping = Ping(addr, port, count)
            tcp_ping.timeout = 5  # Set timeout if supported

            # Perform the ping
            await tcp_ping.ping()

            # Extract results (tcping library interface may vary)
            tcp_result = getattr(tcp_ping, "result", {})

            result.update(
                {
                    "protocol": "TCP",
                    "rtt_min": tcp_result.get("min", 0),
                    "rtt_avg": tcp_result.get("avg", 0),
                    "rtt_max": tcp_result.get("max", 0),
                    "packets_sent": count,
                    "packets_received": tcp_result.get("received", 0),
                    "packet_loss": (count - tcp_result.get("received", 0))
                    / count
                    * 100,
                    "jitter": None,  # TCP ping doesn't typically provide jitter
                    "is_alive": tcp_result.get("success", False),
                }
            )

            self.logger.info(
                f"{self.name}: TCP ping result - alive: {result['is_alive']}"
            )

        except Exception as tcp_e:
            self.logger.error(f"{self.name}: TCP ping also failed: {str(tcp_e)}")
            result.update({"protocol": "TCP", "error": str(tcp_e), "is_alive": False})
