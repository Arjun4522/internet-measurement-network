import cmd
import shlex
import asyncio
import inspect

from typing import Any, Callable, get_type_hints

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

class Shell(cmd.Cmd):
    def __init__(self, obj: Any, prompt_name: str = None, aliases: dict = None):
        super().__init__()
        self.obj = obj
        self.console = Console()
        self.prompt = f"{prompt_name or obj.__class__.__name__}> "
        self.aliases = aliases or {}
        self.methods = {}
        self.completions = {}
        self._register_methods()
        self._register_aliases()

    def _register_methods(self):
        for name, method in inspect.getmembers(self.obj, predicate=inspect.ismethod):
            if name.startswith("_"): continue
            self.methods[name] = method
            setattr(self, f"do_{name}", self._create_command(name, method))
            setattr(self, f"complete_{name}", self._create_completer(method))

    def _create_command(self, name: str, method: Callable):
        async def async_cmd(args):
            try:
                parsed = shlex.split(args)
                sig = inspect.signature(method)
                bound = sig.bind(*parsed)
                bound.apply_defaults()
                result = await method(*bound.args, **bound.kwargs)
                if result is not None:
                    self.console.print(result)
            except Exception as e:
                self.console.print(f"[red]Error:[/red] {e}")

        def sync_cmd(args):
            try:
                parsed = shlex.split(args)
                sig = inspect.signature(method)
                bound = sig.bind(*parsed)
                bound.apply_defaults()
                result = method(*bound.args, **bound.kwargs)
                if inspect.isawaitable(result):
                    result = asyncio.run(result)
                if result is not None:
                    self.console.print(result)
            except Exception as e:
                self.console.print(f"[red]Error:[/red] {e}")

        return lambda args: asyncio.run(async_cmd(args)) if inspect.iscoroutinefunction(method) else sync_cmd(args)

    def _create_completer(self, method: Callable):
        def complete(arg, line, begidx, endidx):
            params = list(inspect.signature(method).parameters.values())
            if not params:
                return []
            already = shlex.split(line)[1:]
            if len(already) >= len(params):
                return []
            param = params[len(already)]
            hints = get_type_hints(method)
            if param.name in hints and hints[param.name] == bool:
                return [s for s in ['true', 'false'] if s.startswith(arg.lower())]
            return []
        return complete

    def _register_aliases(self):
        for alias, target in self.aliases.items():
            if hasattr(self, f"do_{target}"):
                setattr(self, f"do_{alias}", getattr(self, f"do_{target}"))
                setattr(self, f"complete_{alias}", getattr(self, f"complete_{target}", None))

    def do_exit(self, _): self.console.print("[green]Exiting...[/green]"); return True
    def do_quit(self, _): return self.do_exit(_)

    def do_set(self, args):
        """Set an attribute: set <attr> <value>"""
        try:
            attr, val = shlex.split(args)
            cur = getattr(self.obj, attr)
            cast = type(cur)
            setattr(self.obj, attr, cast(val))
            self.console.print(f"[cyan]Set {attr} = {val}[/cyan]")
        except Exception as e:
            self.console.print(f"[red]Failed to set:[/red] {e}")

    def complete_set(self, text, line, *_):
        attrs = list(vars(self.obj).keys())
        return [a for a in attrs if a.startswith(text)]

    def do_show(self, arg):
        """Show an attribute: show [<attr>]"""
        try:
            if arg:
                val = getattr(self.obj, arg)
                self.console.print(f"{arg} = {val}")
            else:
                table = Table(title="Object State")
                table.add_column("Attribute")
                table.add_column("Value")
                for k, v in vars(self.obj).items():
                    table.add_row(k, repr(v))
                self.console.print(table)
        except Exception as e:
            self.console.print(f"[red]Error:[/red] {e}")

    def complete_show(self, text, *_):
        return [a for a in vars(self.obj) if a.startswith(text)]

    def do_help(self, arg):
        """Help: show commands or help <cmd>"""
        if arg:
            func = getattr(self, f"help_{arg}", None)
            if func: func()
            else: self.console.print(f"[yellow]No help for {arg}[/yellow]")
        else:
            cmds = [attr[3:] for attr in dir(self) if attr.startswith("do_")]
            self.console.print("[bold underline]Commands:[/bold underline]")
            for c in sorted(cmds): self.console.print(f"• {c}")

    def emptyline(self): pass
    def default(self, line): self.console.print(f"[red]Unknown command:[/red] {line}")

    def load_plugin(self, plugin_cls):
        plugin = plugin_cls(self)
        for name in dir(plugin):
            if name.startswith("do_"):
                setattr(self, name, getattr(plugin, name))
            if name.startswith("complete_"):
                setattr(self, name, getattr(plugin, name))