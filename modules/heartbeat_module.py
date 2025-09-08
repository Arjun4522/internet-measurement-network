import asyncio
import os
import json
import time
import getpass
import pwd, grp
import random
import socket
import traceback
import platform
import netifaces
from agent.base import BaseWorker
from nats.aio.msg import Msg

class HeartbeatModule(BaseWorker):
    """
    A minimal working module that echoes heartbeat messages.
    """

    def __init__(self, name: str, agent, nc, logger, shared):
        super().__init__(name, agent, nc, logger, shared)

        self.sub_out = f"agent.{self.name}"
        self.sub_err = f"agent.{self.name}.error"

        self.interval = shared.get("interval", 5)  # seconds
        self.tags = shared.get("tags", {})

    async def run(self):
        """
        Subscribes to the input subject and echoes data to output.
        """

        self.logger.info(f"{self.name}: Broascasting on {self.sub_out}")
        await self.nc.publish('agent.notif', json.dumps({"message": f"Started module", "name": self.name}).encode())

        self.logger.info(f"{self.name}: Starting heartbeat every {self.interval}s")

        try:
            while self.running:
                await self._send_heartbeat()
                await asyncio.sleep(self.interval)
        except asyncio.CancelledError as cex:
            self.logger.warning(f"{self.name}: Cancelled")
            await self.nc.publish("agent.notif", json.dumps({"message": f"Stopped module", "name": self.name}).encode())
        except Exception as exception:
            self.logger.exception(f"{self.name}: Error in run loop")
            tb = traceback.format_exc()
            error_data = {
                "module": self.name,
                "traceback": tb,
                "error": str(exception)
            }
            await self.nc.publish(self.sub_err, json.dumps(error_data).encode())
            
    def _safe_get_user_info(self):
        """Safely collects user information."""
        try:
            user_name = getpass.getuser()
            user_pw = pwd.getpwnam(user_name)
            primary_gid = user_pw.pw_gid
            user_pw = pwd.getpwnam(user_name)
            try:
                user_groups_ids = os.getgrouplist(user_name, primary_gid)
                groups = [grp.getgrgid(gid).gr_name for gid in user_groups_ids if gid] # Filter potential None gids
            except Exception as ge:
                self.logger.warning(f"Could not get group list of user {user_name} while sending heartbeat")
                groups = ["Error"]

            return {
                "user": user_pw.pw_name,
                "working_dir": os.getcwd(),
                "home_dir": user_pw.pw_dir,
                "shell": user_pw.pw_shell,
                "uid": user_pw.pw_uid,
                "gid": primary_gid,
                "gecos": user_pw.pw_gecos,
                "groups": groups,
                "loadavg": dict(zip(["1m", "5m", "15m"], os.getloadavg())) if hasattr(os, 'getloadavg') else None,
            }
        except (KeyError, AttributeError, OSError) as e:
             self.logger.warning(f"Could not get full user info of user {getpass.getuser()} while sending heartbeat")
             return { "user": getpass.getuser(), "error": f"Partial info: {e}"}
        except Exception as e:
            self.logger.error("Unexpected error getting user info while sending heartbeat")
            return {"error": f"Unexpected: {e}"}

    def _safe_get_system_info(self):
        """Safely collects system information."""
        try:
            return {
                "system": platform.system(),
                "node_name": platform.node(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(), # Can be empty string
                "platform": platform.platform(), # Can be empty string
            }
        except Exception as e:
            self.logger.error("Error getting system info while sending heartbeat")
            return {"error": str(e)}

    def _safe_get_network_info(self):
        """Safely collects network interface information."""
        interfaces_data = {}
        try:
            available_interfaces = netifaces.interfaces()
        except Exception as e:
             self.logger.error("Could not list network interfaces while sending heartbeat")
             return {"error": f"Cannot list interfaces: {e}"}

        for interface in available_interfaces:
            try:
                addresses = netifaces.ifaddresses(interface)
                # Use dict comprehension for cleaner extraction, provide empty list default
                interfaces_data[interface] = {
                    "ipv4": [addr['addr'] for addr in addresses.get(netifaces.AF_INET, []) if 'addr' in addr],
                    "ipv6": [addr['addr'] for addr in addresses.get(netifaces.AF_INET6, []) if 'addr' in addr],
                    "mac": [addr['addr'] for addr in addresses.get(netifaces.AF_LINK, []) if 'addr' in addr],
                }
                # Handle Linux AF_PACKET explicitly if AF_LINK is not present or empty
                if netifaces.AF_PACKET in addresses and not interfaces_data[interface].get("mac"):
                     interfaces_data[interface]["mac"] = [addr['addr'] for addr in addresses.get(netifaces.AF_PACKET, []) if 'addr' in addr]

            except Exception as ie:
                self.logger.error(f"Error retrieving info for interface {interface} while sending heartbeat")
                interfaces_data[interface] = {"error": f"Retrieval failed: {ie}"}

        return interfaces_data

    def _get_agent_info(self):
        """Constructs the complete heartbeat data payload."""
        return {
            "id": self.agent.agent_id,
            "name": self.agent.agent_name,
            "timezone": time.tzname, # Tuple like ('IST', 'IST') or ('EST', 'EDT') - (Non Day Light Saving Timezone, Day Light Saving Timezone)
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "user": self._safe_get_user_info(),
            "system": self._safe_get_system_info(),
            "network": self._safe_get_network_info(),
        }

    async def _send_heartbeat(self):
        heartbeat = {
            "module": self.name,
            "timestamp": time.time(),
            "agent": self._get_agent_info(),
            "tags": self.tags,
        }
        await self.nc.publish(self.sub_out, json.dumps(heartbeat).encode())
        self.logger.debug(f"{self.name}: Published heartbeat → {self.sub_out}")
