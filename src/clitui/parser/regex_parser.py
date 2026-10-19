"""Deterministic regex and heuristic parser for CLI help output."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple
from clitui.models import CliArgument, CliOption, CliSchema


# Regex pattern to match option switch lines, e.g.:
# -v, --verbose
# -o, --output <FILE>
# --format=<FORMAT>
# -p, --port=NUM
# -n <COUNT>
OPTION_LINE_RE = re.compile(
    r"^\s{0,8}(?:(-[a-zA-Z0-9])(?:,\s*|\s+))?(--[a-zA-Z0-9][a-zA-Z0-9-_]*)(?:[=\s]+(<[^>]+>|\[[^\]]+\]|[A-Z0-9_-]{2,}))?(.*)$"
)

SINGLE_OPTION_RE = re.compile(
    r"^\s{0,8}(-[a-zA-Z0-9]|--[a-zA-Z0-9][a-zA-Z0-9-_]*)(?:[=\s]+(<[^>]+>|\[[^\]]+\]|[A-Z0-9_-]{2,}))?(.*)$"
)

USAGE_RE = re.compile(r"^\s*(?:Usage|Synopsis):\s*([^\n]+)", re.IGNORECASE | re.MULTILINE)


def parse_regex(command_name: str, help_text: str) -> CliSchema:
    """Extracts CLI options, arguments, and subcommands using deterministic heuristics."""
    options: List[CliOption] = []
    seen_switches = set()

    lines = help_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        match = OPTION_LINE_RE.match(line)
        single_match = SINGLE_OPTION_RE.match(line) if not match else None

        short_opt = None
        long_opt = None
        val_hint = None
        desc_tail = ""

        if match:
            short_opt = match.group(1)
            long_opt = match.group(2)
            val_hint = match.group(3)
            desc_tail = match.group(4) or ""
        elif single_match:
            cand = single_match.group(1)
            if cand.startswith("--"):
                long_opt = cand
            else:
                short_opt = cand
            val_hint = single_match.group(2)
            desc_tail = single_match.group(3) or ""

        if short_opt or long_opt:
            switches = []
            if short_opt:
                switches.append(short_opt)
            if long_opt:
                switches.append(long_opt)

            # Avoid duplicate switches
            primary = long_opt or short_opt
            if primary not in seen_switches:
                seen_switches.add(primary)

                # Gather multiline description
                desc_parts = [desc_tail.strip()] if desc_tail.strip() else []
                # Check next lines for indent continuation
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    if not next_line.strip():
                        j += 1
                        continue
                    # If next line starts with option or is a new section, stop
                    if (
                        OPTION_LINE_RE.match(next_line)
                        or SINGLE_OPTION_RE.match(next_line)
                        or next_line.strip().endswith(":")
                    ):
                        break
                    # If indented more than 6 spaces, treat as description continuation
                    if re.match(r"^\s{6,}", next_line):
                        desc_parts.append(next_line.strip())
                        j += 1
                    else:
                        break

                full_desc = " ".join(desc_parts)
                opt_type, expects_val, choices = _infer_type_and_constraints(
                    val_hint, full_desc
                )

                options.append(
                    CliOption(
                        switches=switches,
                        expects_value=expects_val,
                        type=opt_type,
                        description=full_desc,
                        choices=choices,
                    )
                )

        i += 1

    # Extract positional arguments from usage line
    arguments = _extract_positional_args(help_text, command_name)

    # Extract subcommands
    subcommands = _extract_subcommands(help_text)

    return CliSchema(
        command=command_name,
        subcommands=subcommands,
        arguments=arguments,
        options=options,
        description=_extract_description(help_text),
    )


def _infer_type_and_constraints(
    val_hint: Optional[str], description: str
) -> Tuple[str, bool, List[str]]:
    """Infers type, expects_value, and enum choices from the value placeholder and description."""
    if not val_hint:
        # Check description if it mentions [default: ...] or choices
        choice_match = re.search(r"\[(?:possible values|values|choices):\s*([^\]]+)\]", description, re.IGNORECASE)
        if choice_match:
            raw_choices = [c.strip(" '\"") for c in re.split(r"[,|\s]+", choice_match.group(1)) if c.strip()]
            return "choice_enum", True, raw_choices

        return "boolean", False, []

    val_upper = val_hint.strip("<>[]=").upper()

    # Enum choices detection in hint e.g. [json|yaml|text]
    if "|" in val_hint:
        choices = [c.strip(" '\"<>[]") for c in val_hint.split("|") if c.strip()]
        return "choice_enum", True, choices

    # Check description for enum choices
    choice_match = re.search(r"\[(?:possible values|values|choices):\s*([^\]]+)\]", description, re.IGNORECASE)
    if choice_match:
        raw_choices = [c.strip(" '\"") for c in re.split(r"[,|\s]+", choice_match.group(1)) if c.strip()]
        return "choice_enum", True, raw_choices

    if any(k in val_upper for k in ("DIR", "DIRECTORY", "FOLDER")):
        return "directory_path", True, []

    if any(k in val_upper for k in ("PATH", "FILE", "FILENAME", "OUT", "DEST", "SRC")):
        return "file_path", True, []

    if any(k in val_upper for k in ("NUM", "INT", "COUNT", "PORT", "LIMIT", "LINES")):
        return "integer", True, []

    return "string", True, []


def _extract_positional_args(help_text: str, command_name: str) -> List[CliArgument]:
    """Extracts positional arguments from Usage line or arguments section."""
    args: List[CliArgument] = []
    seen = set()

    usage_match = USAGE_RE.search(help_text)
    if usage_match:
        usage_str = usage_match.group(1).strip()
        tokens = usage_str.split()
        # Skip leading command tokens
        cmd_words = command_name.split()
        idx = 0
        while idx < len(tokens) and idx < len(cmd_words) and tokens[idx] == cmd_words[idx]:
            idx += 1

        for token in tokens[idx:]:
            if token.startswith("-"):
                continue
            norm = token.strip("[]<>.").rstrip(".").upper()
            if norm in ("OPTION", "OPTIONS", "FLAG", "FLAGS", "PARAM", "PARAMS", "ARG", "ARGS"):
                continue
            is_optional = token.startswith("[") and token.endswith("]")
            cleaned = token.strip("[]<>.")
            if cleaned and cleaned not in seen and not cleaned.startswith("-"):
                seen.add(cleaned)
                args.append(
                    CliArgument(
                        name=cleaned,
                        required=not is_optional,
                        description=f"Positional parameter: {cleaned}",
                    )
                )

    return args


def _extract_subcommands(help_text: str) -> List[str]:
    """Detects listed subcommands if a Commands/Subcommands section is present."""
    subcommands: List[str] = []
    in_subcmd_section = False

    subcmd_header_re = re.compile(
        r"(?:common.*commands|available commands|^commands:?$|subcommands|management commands)",
        re.IGNORECASE,
    )

    for line in help_text.splitlines():
        trimmed = line.strip()
        if subcmd_header_re.search(trimmed):
            in_subcmd_section = True
            continue

        if in_subcmd_section:
            # Check for section separator or end of block
            if not line.strip():
                continue
            if re.match(r"^[A-Z][a-zA-Z0-9\s_-]+:\s*$", trimmed):
                # New major section header
                if not any(k in trimmed.lower() for k in ("commands", "help", "tutorial", "everyday")):
                    break
            parts = trimmed.split()
            # Indented subcommand entries e.g. "   clone      Clone a repository"
            if (line.startswith("  ") or line.startswith("\t")) and parts:
                if re.match(r"^[a-z][a-z0-9_-]+$", parts[0]) and len(parts) > 1:
                    subcommands.append(parts[0])

    return list(dict.fromkeys(subcommands))


def _extract_description(help_text: str) -> str:
    """Extracts short introductory summary from help text."""
    lines = [l.strip() for l in help_text.splitlines() if l.strip()]
    desc_lines = []
    for line in lines[:8]:
        if re.match(r"^(Usage|Synopsis|Options|Flags|Commands):", line, re.IGNORECASE):
            break
        desc_lines.append(line)
    return " ".join(desc_lines)
