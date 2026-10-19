"""Persistent schema cache manager for clitui.

Stores parsed CLI schemas in ~/.cache/clitui/<slug>.json keyed by command and help content hash.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Optional

from clitui.models import CliSchema


def get_cache_dir() -> Path:
    """Returns the XDG cache directory for clitui."""
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        base_dir = Path(xdg_cache)
    else:
        base_dir = Path.home() / ".cache"
    cache_dir = base_dir / "clitui"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _command_to_slug(command_name: str) -> str:
    """Converts a command string (e.g. 'git commit') to a safe filename slug."""
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", command_name.strip()).strip("_")
    return slug or "unknown"


def _calculate_hash(content: str) -> str:
    """Calculates SHA256 digest of help text."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_cached_schema(command_name: str, help_text: str) -> Optional[CliSchema]:
    """Loads cached CliSchema if it exists and matches the current help text hash.

    Args:
        command_name: Command string, e.g. 'ls' or 'git commit'
        help_text: The current raw help text extracted for the command

    Returns:
        Cached CliSchema if valid, None otherwise.
    """
    slug = _command_to_slug(command_name)
    cache_file = get_cache_dir() / f"{slug}.json"
    if not cache_file.exists():
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            payload = json.load(f)

        cached_hash = payload.get("help_hash")
        current_hash = _calculate_hash(help_text)

        # Invalidate cache if help output changed (e.g. tool updated)
        if cached_hash != current_hash:
            return None

        schema_data = payload.get("schema")
        if not schema_data:
            return None

        return CliSchema.from_dict(schema_data)
    except Exception:
        # If cache file is corrupt or unreadable, safely ignore
        return None


def save_cached_schema(schema: CliSchema, help_text: str) -> bool:
    """Persists a parsed CliSchema to disk with its content hash."""
    slug = _command_to_slug(schema.command)
    cache_file = get_cache_dir() / f"{slug}.json"

    try:
        payload = {
            "command": schema.command,
            "help_hash": _calculate_hash(help_text),
            "schema": schema.to_dict(),
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return True
    except Exception:
        return False


def clear_cache(command_name: Optional[str] = None) -> int:
    """Deletes cached schema files.

    Args:
        command_name: Specific command to clear, or None to clear all.

    Returns:
        Number of cache files removed.
    """
    cache_dir = get_cache_dir()
    count = 0
    if command_name:
        slug = _command_to_slug(command_name)
        target = cache_dir / f"{slug}.json"
        if target.exists():
            target.unlink(missing_ok=True)
            count += 1
    else:
        for f in cache_dir.glob("*.json"):
            f.unlink(missing_ok=True)
            count += 1
    return count
