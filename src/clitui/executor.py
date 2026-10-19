"""Command execution wrapper for clitui.

Safely constructs arguments and runs subprocess without shell injection.
"""

from __future__ import annotations

import subprocess
from typing import Callable, Dict, List, Optional
from clitui.models import CliArgument, CliOption, CliSchema


def build_command_line(
    schema: CliSchema,
    option_values: Dict[int, any],
    argument_values: Dict[str, str],
) -> List[str]:
    """Assembles the final command line token list safely for subprocess.execv.

    Args:
        schema: The CliSchema containing options and arguments definitions.
        option_values: Mapping of option id (or index) to configured value.
        argument_values: Mapping of positional argument name to value string.

    Returns:
        List of command arguments ready for execution.
    """
    cmd_tokens = schema.command.split()

    # Add configured options
    for idx, opt in enumerate(schema.options):
        val = option_values.get(idx)
        if val is None or val is False or val == "" or str(val).startswith("Select."):
            continue

        switch = opt.primary_switch()
        if not switch:
            continue

        if opt.type == "boolean":
            if val is True:
                cmd_tokens.append(switch)
        else:
            # String, integer, file_path, choice_enum
            str_val = str(val).strip()
            if str_val:
                cmd_tokens.extend([switch, str_val])

    # Add positional arguments in order
    for arg in schema.arguments:
        val = argument_values.get(arg.name, "").strip()
        if val:
            cmd_tokens.append(val)

    return cmd_tokens


def run_command_interactive(
    args: List[str],
    on_output: Callable[[str], None],
    on_complete: Optional[Callable[[int], None]] = None,
) -> subprocess.Popen:
    """Executes command asynchronously and streams output line-by-line via callback.

    Args:
        args: Command tokens list
        on_output: Callback function called with each stdout/stderr line
        on_complete: Callback function called with returncode when process terminates
    """
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    def _reader():
        try:
            if proc.stdout:
                for line in iter(proc.stdout.readline, ""):
                    on_output(line)
        finally:
            proc.wait()
            if on_complete:
                on_complete(proc.returncode)

    import threading
    t = threading.Thread(target=_reader, daemon=True)
    t.start()

    return proc
