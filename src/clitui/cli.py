"""CLI entry point for clitui."""

from __future__ import annotations

import os
import sys
from typing import List
from rich.console import Console

from clitui.cache import clear_cache, load_cached_schema, save_cached_schema
from clitui.extractor import get_command_help
from clitui.parser.hybrid_parser import parse_cli_help
from clitui.ui.urwid_app import UrwidCliApp

console = Console()


def print_usage():
    console.print(
        "[bold cyan]clitui[/bold cyan] — Dynamic TUI generator for arbitrary Linux CLI tools\n\n"
        "[bold]Usage:[/bold]\n"
        "  clitui <command> [subcommand...] [flags...]\n\n"
        "[bold]Examples:[/bold]\n"
        "  clitui curl\n"
        "  clitui tar\n"
        "  clitui git commit\n"
        "  clitui find\n\n"
        "[bold]Options:[/bold]\n"
        "  --no-cache      Disable schema caching (always parse freshly)\n"
        "  --refresh       Force re-parsing and overwrite existing cache\n"
        "  --clear-cache   Clear all cached schemas and exit\n"
        "  --no-llm        Skip semantic Ollama analysis (deterministic regex only)\n"
        "  --model <name>  Specify Ollama model (default: qwen2.5-coder:7b)\n"
        "  --help, -h      Show this help message\n\n"
        "[bold]Environment Variables:[/bold]\n"
        "  CLITUI_NO_CACHE=1   Globally disable schema caching\n"
    )


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print_usage()
        sys.exit(0)

    if "--clear-cache" in args:
        cleared = clear_cache()
        console.print(f"[green]Cleared {cleared} cached schema file(s).[/green]")
        sys.exit(0)

    use_llm = True
    model_name = "qwen2.5-coder:7b"
    use_cache = os.environ.get("CLITUI_NO_CACHE") != "1"
    refresh_cache = False

    # Separate clitui flags from target command
    target_cmd: List[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--no-llm":
            use_llm = False
            i += 1
        elif arg == "--no-cache":
            use_cache = False
            i += 1
        elif arg == "--refresh":
            refresh_cache = True
            i += 1
        elif arg == "--model" and i + 1 < len(args):
            model_name = args[i + 1]
            i += 2
        elif arg == "--":
            target_cmd.extend(args[i + 1 :])
            break
        else:
            target_cmd.append(arg)
            i += 1

    if not target_cmd:
        console.print("[bold red]Error:[/] No target command provided.")
        print_usage()
        sys.exit(1)

    cmd_display = " ".join(target_cmd)

    try:
        with console.status(f"[cyan]Extracting help output for '{cmd_display}'...[/]"):
            help_text, source = get_command_help(target_cmd)

        schema = None

        # 1. Attempt to load from persistent cache
        if use_cache and not refresh_cache:
            schema = load_cached_schema(cmd_display, help_text)

        # 2. Parse if not found in cache
        if schema is None:
            status_msg = f"[cyan]Analyzing schema for '{cmd_display}'[/]"
            if use_llm:
                status_msg += f" [dim](consulting {model_name})...[/dim]"
            else:
                status_msg += " [dim](deterministic mode)...[/dim]"

            with console.status(status_msg):
                schema = parse_cli_help(
                    command_name=cmd_display,
                    help_text=help_text,
                    use_llm=use_llm,
                    model=model_name,
                )

            # Persist to cache
            if use_cache:
                save_cached_schema(schema, help_text)

        if not schema.options and not schema.arguments:
            console.print(
                f"[yellow]Warning:[/] No options or arguments could be extracted for '{cmd_display}'."
            )

        # Launch Urwid App
        app = UrwidCliApp(schema=schema)
        app.run()

    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]Error running clitui:[/] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
