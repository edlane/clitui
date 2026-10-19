"""Semantic LLM parser using local Ollama (qwen2.5-coder:7b) in strict JSON mode."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional
import requests

from clitui.models import CliSchema

logger = logging.getLogger("clitui.parser.llm")

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5-coder:7b"

SYSTEM_PROMPT = """You are a CLI command analyzer. Given a CLI utility help summary and a list of detected flags, identify:
1. Positional arguments (name, whether required, description)
2. Subcommands (if any)
3. For any flags that take specific enum choices, special path types, or integers, return their enriched details.

Output strict JSON only adhering to this structure:
{
  "command": "cmd_name",
  "subcommands": ["subcmd1", "subcmd2"],
  "arguments": [
    {
      "name": "ARG_NAME",
      "required": true,
      "description": "Short explanation"
    }
  ],
  "options": [
    {
      "switches": ["--format"],
      "type": "choice_enum",
      "choices": ["json", "yaml", "text"],
      "description": "Output format"
    }
  ]
}

Only return options where you are specifying enum choices, specific types (file_path, directory_path, integer, choice_enum), or cleaner descriptions. Do not output plain boolean flags. Return valid JSON only.
"""



def parse_with_llm(
    command_name: str,
    help_text: str,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    timeout_sec: float = 60.0,
) -> Optional[CliSchema]:
    """Invokes local Ollama with strict JSON formatting to extract a complete CliSchema."""
    endpoint = f"{ollama_url.rstrip('/')}/api/generate"

    # Keep prompt focused for fast semantic extraction
    lines = help_text.splitlines()
    truncated_help = "\n".join(lines[:120])

    prompt = (
        f"CLI Command: {command_name}\n\n"
        f"Help Output:\n{truncated_help}\n\n"
        "Return strict JSON matching the schema:"
    )

    payload = {
        "model": model,
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "num_predict": 768,
        },
    }

    try:
        response = requests.post(endpoint, json=payload, timeout=timeout_sec)
        response.raise_for_status()
        data = response.json()
        raw_output = data.get("response", "").strip()

        parsed_json = _clean_and_parse_json(raw_output)
        if not parsed_json:
            return None

        # Ensure command is set
        if not parsed_json.get("command"):
            parsed_json["command"] = command_name

        return CliSchema.from_dict(parsed_json)

    except requests.exceptions.RequestException as e:
        logger.warning(f"Ollama request failed: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error parsing Ollama output: {e}")
        return None


def _clean_and_parse_json(raw: str) -> Optional[Dict[str, Any]]:
    """Cleans markdown fences or surrounding junk to parse valid JSON."""
    if not raw:
        return None

    # Strip markdown fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```\s*$", "", cleaned.strip(), flags=re.MULTILINE).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try finding outermost JSON object { ... }
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    return None
