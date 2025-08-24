import typer
import asyncio
from aiori_agent.daemon.agent import Agent
from aiori_agent.shell.plugins import EchoPlugin, AgentPlugin
from aiori_agent.shell.shell import Shell

cli = typer.Typer(help="NATS Modular Agent CLI")

@cli.command()
def start():
    """
    Start the agent and load all modules.
    """
    typer.echo("🚀 Starting agent...")
    asyncio.run(Agent().start())

@cli.command()
def shell():
    """
    Launch interactive shell for live commands.
    """
    try:
        shell = Shell(Agent())
        shell.load_plugin(EchoPlugin)
        shell.load_plugin(AgentPlugin)
        shell.cmdloop()
    except KeyboardInterrupt:
        exit(0)
    except Exception as e:
        typer.echo(f"Error: {e}")
