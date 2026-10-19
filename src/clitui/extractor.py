"""Command help extractor for clitui.

Extracts --help, -h, or man pages safely via non-shell subprocess execution.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import List, Optional, Tuple


def get_command_help(command_parts: List[str]) -> Tuple[str, str]:
    """Retrieves the help text for a given command.

    Args:
        command_parts: Command as list, e.g. ["rg"] or ["git", "commit"]

    Returns:
        Tuple of (help_text, source_description)

    Raises:
        RuntimeError if command cannot be found or help cannot be extracted.
    """
    if not command_parts:
        raise ValueError("No command specified.")

    base_binary = command_parts[0]
    binary_path = shutil.which(base_binary)
    if not binary_path:
        raise RuntimeError(f"Command not found on system: '{base_binary}'")

    # Strategy 1: <cmd> --help
    output = _run_command(command_parts + ["--help"])
    if output and len(output.strip()) > 50:
        return output, "--help"

    # Strategy 2: <cmd> -h
    output = _run_command(command_parts + ["-h"])
    if output and len(output.strip()) > 50:
        return output, "-h"

    # Strategy 3: man <cmd> (only for base command)
    if shutil.which("man"):
        man_cmd = ["man", "--pager=cat", base_binary]
        output = _run_command(man_cmd)
        if output and len(output.strip()) > 50:
            return output, "man"

    raise RuntimeError(
        f"Unable to extract help output for '{' '.join(command_parts)}'. "
        "Neither --help, -h, nor man yielded usable documentation."
    )


def _run_command(args: List[str], timeout_sec: float = 8.0) -> Optional[str]:
    """Runs a command via non-shell subprocess with a timeout."""
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        return proc.stdout
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        return None
