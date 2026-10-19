"""Data models and schemas for clitui."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, List, Optional


VALID_TYPES = {
    "boolean",
    "string",
    "integer",
    "file_path",
    "directory_path",
    "choice_enum",
}


@dataclass
class CliArgument:
    """Represents a positional argument (e.g. PATTERN or [PATH...])."""

    name: str
    required: bool = False
    description: str = ""
    default: Optional[str] = None
    value: Optional[str] = None


@dataclass
class CliOption:
    """Represents a CLI switch or flag (e.g. -v, --verbose, --output <file>)."""

    switches: List[str] = field(default_factory=list)
    expects_value: bool = False
    type: str = "boolean"  # boolean, string, integer, file_path, directory_path, choice_enum
    description: str = ""
    choices: List[str] = field(default_factory=list)
    default: Optional[Any] = None
    value: Any = None

    def primary_switch(self) -> str:
        """Returns the preferred switch name (long switch if available, else first switch)."""
        long_switches = [s for s in self.switches if s.startswith("--")]
        if long_switches:
            return long_switches[0]
        return self.switches[0] if self.switches else ""

    def display_name(self) -> str:
        """Returns a readable label for UI controls."""
        return ", ".join(self.switches)


@dataclass
class CliSchema:
    """Normalized schema representing a parsed CLI command."""

    command: str
    subcommands: List[str] = field(default_factory=list)
    arguments: List[CliArgument] = field(default_factory=list)
    options: List[CliOption] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CliSchema:
        args = [
            CliArgument(
                name=arg.get("name", "arg"),
                required=arg.get("required", False),
                description=arg.get("description", ""),
                default=arg.get("default"),
                value=arg.get("value"),
            )
            for arg in data.get("arguments", [])
        ]

        options = []
        # Support both 'options' and 'arguments' for flags depending on JSON input
        raw_options = data.get("options")
        if raw_options is None:
            # Fallback if intermediate schema labeled options under arguments
            raw_options = [
                opt for opt in data.get("arguments", []) if "switches" in opt
            ]

        for opt in raw_options:
            opt_type = opt.get("type", "boolean")
            if opt_type not in VALID_TYPES:
                opt_type = "string" if opt.get("expects_value", False) else "boolean"

            options.append(
                CliOption(
                    switches=opt.get("switches", []),
                    expects_value=opt.get("expects_value", False),
                    type=opt_type,
                    description=opt.get("description", ""),
                    choices=opt.get("choices", []),
                    default=opt.get("default"),
                    value=opt.get("value"),
                )
            )

        return cls(
            command=data.get("command", data.get("command_name", "")),
            subcommands=data.get("subcommands", []),
            arguments=args,
            options=options,
            description=data.get("description", ""),
        )
