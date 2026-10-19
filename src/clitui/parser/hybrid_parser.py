"""Hybrid parser combining deterministic regex with semantic LLM inference."""

from __future__ import annotations

import logging
from typing import Optional
from clitui.models import CliOption, CliSchema
from clitui.parser.llm_parser import parse_with_llm
from clitui.parser.regex_parser import parse_regex

logger = logging.getLogger("clitui.parser.hybrid")


def parse_cli_help(
    command_name: str,
    help_text: str,
    use_llm: bool = True,
    model: str = "qwen2.5-coder:7b",
) -> CliSchema:
    """Parses CLI help text using deterministic regex and Ollama semantic analysis.

    Args:
        command_name: Name of the command being parsed (e.g. 'rg' or 'git commit')
        help_text: Raw output of --help or man page
        use_llm: Whether to invoke Ollama for semantic refinement
        model: Model name in Ollama

    Returns:
        Consolidated CliSchema
    """
    # 1. Deterministic baseline
    regex_schema = parse_regex(command_name, help_text)

    if not use_llm:
        return regex_schema

    # 2. Semantic LLM refinement
    try:
        llm_schema = parse_with_llm(command_name, help_text, model=model)
    except Exception as e:
        logger.warning(f"LLM parsing failed: {e}")
        llm_schema = None

    if not llm_schema:
        # Fall back directly to regex results
        return regex_schema

    # 3. Merge results
    return _merge_schemas(regex_schema, llm_schema)


def _merge_schemas(regex_schema: CliSchema, llm_schema: CliSchema) -> CliSchema:
    """Merges regex and LLM schemas, prioritizing semantic types while preserving full coverage."""
    # Build switch index from LLM options
    llm_opt_by_switch = {}
    for opt in llm_schema.options:
        for s in opt.switches:
            llm_opt_by_switch[s] = opt

    merged_options: list[CliOption] = []
    handled_llm_opts = set()

    # Iterate regex options (which has high syntactic recall)
    for reg_opt in regex_schema.options:
        # Check if matched by any switch in LLM
        matching_llm_opt: Optional[CliOption] = None
        for s in reg_opt.switches:
            if s in llm_opt_by_switch:
                matching_llm_opt = llm_opt_by_switch[s]
                break

        if matching_llm_opt:
            handled_llm_opts.add(id(matching_llm_opt))
            # Merge switches
            all_switches = list(dict.fromkeys(reg_opt.switches + matching_llm_opt.switches))
            # Prefer LLM's type if specific, else regex
            final_type = matching_llm_opt.type
            if final_type in ("string", "boolean") and reg_opt.type not in ("string", "boolean"):
                final_type = reg_opt.type

            choices = matching_llm_opt.choices or reg_opt.choices
            desc = matching_llm_opt.description or reg_opt.description

            merged_options.append(
                CliOption(
                    switches=all_switches,
                    expects_value=matching_llm_opt.expects_value or reg_opt.expects_value,
                    type=final_type,
                    description=desc,
                    choices=choices,
                    default=matching_llm_opt.default or reg_opt.default,
                )
            )
        else:
            merged_options.append(reg_opt)

    # Append any LLM options that regex missed
    for llm_opt in llm_schema.options:
        if id(llm_opt) not in handled_llm_opts:
            merged_options.append(llm_opt)

    # Prefer LLM's positional arguments if non-empty, else regex arguments
    arguments = llm_schema.arguments if llm_schema.arguments else regex_schema.arguments

    # Merge subcommands
    subcommands = list(dict.fromkeys(regex_schema.subcommands + llm_schema.subcommands))

    return CliSchema(
        command=regex_schema.command or llm_schema.command,
        subcommands=subcommands,
        arguments=arguments,
        options=merged_options,
        description=llm_schema.description or regex_schema.description,
    )
