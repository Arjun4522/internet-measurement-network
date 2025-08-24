import asyncio
from time import sleep
from typing import Awaitable
from rich.table import Table
from rich.progress import Progress
from rich import box
from asyncio.tasks import Task
from threading import Thread
from aiori_agent.daemon.agent import Agent

def run_in_background(coro):
    asyncio.run(coro())

class AgentPlugin:
    def __init__(self, shell):
        self.agent: Agent = shell.obj
        self.agent_awaitable: Awaitable = None
        self.agent_thread: Thread = None

        self.console = shell.console
    
    def do_agent(self, args):
        try:
            match args:
                case "start":
                    with Progress(transient=True, console=self.console) as progress:
                        # Start thread
                        self.agent_thread : Thread = Thread(target=run_in_background, args=(self.agent.start, ))
                        self.agent_thread.start()

                        # Wait for 3 seconds
                        sleep(3)

                    # The show status
                    if self.agent.alive_and_active():
                        self.console.print(f"[bold green]Agent:[/bold green] Started")
                    else:
                        self.console.print(f"[bold red]Agent:[/bold red] Unable to start")

                case "stop":
                    if self.agent_thread:
                        asyncio.run(self.agent.stop())
                    pass

                case "modules":
                    table = Table(title="Modules", box=box.SIMPLE_HEAD)
                    table.add_column("Module")
                    table.add_column("Description")
                    for name, module_object in self.agent.manager.running_workers.items():
                        module_name = module_object.__class__.__name__
                        metadata = module_object.__class__.Meta
                        table.add_row(
                            f"[bold]{module_name}[/bold]\n[grey23]v{metadata.version}[/grey23]\n", 
                            f"{metadata.description}\n[italic grey23]- by {metadata.author}[/italic grey23]\n"
                        )
                    self.console.print(table)
                    pass

        except Exception as ex:
            self.console.print(f"[red]Error:[/red] {str(ex)}")
    
    def complete_agent(self, text, *_):
        return ["start", "stop", "modules"]

class EchoPlugin:
    def __init__(self, shell): self.console = shell.console
    def do_echo(self, args): self.console.print(f"[bold green]Echo:[/bold green] {args}")
    def complete_echo(self, text, *_): return ["hello", "world", "plugin"]
