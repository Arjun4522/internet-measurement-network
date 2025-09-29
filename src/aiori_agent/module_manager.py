import os
import sys
import asyncio
import traceback
import json
import importlib.util
from pathlib import Path
from types import ModuleType

from typing import Dict, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .config import settings
from .base import logger, BaseWorker


class EventLoopException(Exception):
    pass


class ModuleManager(FileSystemEventHandler):
    """
    Manages dynamic loading, execution, hot-reloading and crash handling of worker modules.
    """

    def __init__(self, agent, nc):
        self.agent = agent
        self.nc = nc
        self.loop = asyncio.get_event_loop()
        self.modules_dir = settings.modules_path
        self.running_workers: Dict[str, BaseWorker] = {}
        self.loaded_modules: Dict[str, ModuleType] = {}

    async def start_all(self):
        """
        Load and run all initial modules and start file watcher.
        """
        await self._load_all_modules()
        self._start_watcher()

    def _start_watcher(self):
        """
        Launch watchdog observer for hot-reloading modules.
        """
        observer = Observer()
        observer.schedule(self, str(self.modules_dir.resolve()), recursive=False)
        observer.start()
        logger.info("👀 Watchdog started on modules directory")

    def on_modified(self, event):
        """
        Watchdog event handler: on .py file modification, trigger reload.
        """
        if event.is_directory or not event.src_path.endswith(".py"):
            return

        module_path = Path(event.src_path)
        module_name = module_path.stem
        logger.debug(f"📦 File modified: {module_name}")
        self.loop.create_task(self._reload_module(module_name, module_path))

    async def _load_all_modules(self):
        """
        Load and run all modules in the directory.
        """
        for file in self.modules_dir.glob("*.py"):
            if not file.name.startswith("__"):
                await self._reload_module(file.stem, file)

    async def _reload_module(self, module_name: str, path: Path):
        """
        Cancel existing worker, reload the module, and restart the worker.
        """
        try:
            # BUGS: The old worker might not stop immediately
            # Cancel and remove old task
            if module_name in self.running_workers:
                worker = self.running_workers[module_name]
                if worker.running or worker.task:
                    await worker.stop("Reloading the module.")
                del self.running_workers[module_name]
                logger.info(f"⛔ Stopped previous worker: {module_name}")
                await self.nc.publish(
                    "agent", f"Worker `{module_name}` stopped".encode()
                )

            # Unload previous module
            if module_name in sys.modules:
                del sys.modules[module_name]

            # Reload module from disk
            spec = importlib.util.spec_from_file_location(module_name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.loaded_modules[module_name] = mod

            # Instantiate valid BaseWorker subclass
            worker_class = next(
                (
                    cls
                    for cls in mod.__dict__.values()
                    if isinstance(cls, type)
                    and issubclass(cls, BaseWorker)
                    and cls is not BaseWorker
                ),
                None,
            )

            if not worker_class:
                logger.warning(f"⚠️ No valid BaseWorker found in {module_name}")
                return

            shared = {"metadata": {"module": module_name}}
            worker = worker_class(
                name=module_name,
                agent=self.agent,
                nc=self.nc,
                logger=logger,
                shared=shared,
            )
            if await worker.setup():
                worker.start(self._on_crash)  # Presumed to spawn internal task
                self.running_workers[module_name] = worker
                logger.info(f"✅ Worker started: {module_name}")
                await self.nc.publish(
                    "agent", f"Worker `{module_name}` loaded".encode()
                )

        except Exception as e:
            logger.error(f"❌ Error loading module `{module_name}`: {e}")
            traceback.print_exc()
            await self._on_crash(module_name, e)

    async def _on_crash(self, module_name: str, exception: Exception):
        """
        Handle worker crash: logs, snapshot, and error NATS publish.
        """
        tb = traceback.format_exc()
        error_data = {"module": module_name, "traceback": tb, "error": str(exception)}

        error_path = settings.error_log_dir / f"{module_name}_error.json"
        settings.error_log_dir.mkdir(exist_ok=True)
        with open(error_path, "w") as f:
            json.dump(error_data, f, indent=2)

        await self.nc.publish("agent.error", json.dumps(error_data).encode())
