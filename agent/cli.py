import typer
import asyncio
from agent.agent import Agent

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
    # TODO: Commands need to be added.
    typer.echo("🔧 Entering shell mode. Type `exit` to quit.")
    while True:
        try:
            cmd = input("agent> ").strip()
            if cmd in ("exit", "quit"):
                break
            elif cmd == "start":
                typer.echo("🧩 Agent start: (not yet implemented)")
            elif cmd == "stop":
                typer.echo("🧩 Agent stop: (not yet implemented)")
            elif cmd == "debug":
                typer.echo("🧩 Debug mode: (not yet implemented)")
            elif cmd == "admin":
                typer.echo("🧩 Admin: (not yet implemented)")
            elif cmd == "list":
                typer.echo("🧩 Module list: (not yet implemented)")
            else:
                typer.echo(f"❓ Unknown command: {cmd}")
        except KeyboardInterrupt:
            break
        except Exception as e:
            typer.echo(f"Error: {e}")
