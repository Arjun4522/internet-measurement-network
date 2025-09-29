from pathlib import Path
from typing import Annotated
import typer
import asyncio

from .agent import Agent


def cli():
    """
    Start the agent and load all modules.
    """
    typer.echo("🚀 Starting agent...")
    asyncio.run(Agent().start())
