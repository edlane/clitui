# CLI to TUI (clitui) — Architectural Context & Specification

## Overview

**Goal:** Develop a Linux tool that parses the `--help` (or `man`) output of an arbitrary CLI command and dynamically generates an equivalent Text User Interface (TUI).

While modern TUI frameworks make rendering interactive interfaces straightforward, building a universal CLI-to-TUI generator requires handling unstructured, non-standard help outputs across disparate command ecosystems.

---

## 1. Existing Solutions & Prior Art

| Project | Approach | Capabilities & Limitations |
| :--- | :--- | :--- |
| **Gooey** (Python) | Code-level inspection | Automatically turns standard Python `argparse` scripts into a GUI/TUI without rewriting code. Requires access to Python source, not arbitrary compiled binaries. |
| **Clig / Tui-ify** | Shell expansion wrappers | Experimental utilities attempting to parse standard Unix `man` pages or standard `--help` outputs into recursive dialog or `ncurses` layouts. |
| **fzf / gum** (Charmbracelet) | Manual scaffolding | Dynamic menus for selecting flags/arguments; requires manual piping rather than automated schema extraction. |

---

## 2. Structural Challenges with "Arbitrary" CLI Commands

1. **Varying Layout Engines:**
   - GNU tools (`tar`, `grep`), modern Rust CLIs (`ripgrep`, `bat`), Go CLIs (`kubectl`), and classic BSD utilities format flags, positional arguments, and line breaks differently.
2. **Context-Dependent Subcommands:**
   - Tools like `git` or `docker` have deep command hierarchies (e.g., `git remote add ...`). A universal parser must recursively inspect `--help` branches to map the full configuration tree.
3. **Missing Typing Meta-information:**
   - Help text rarely declares strict types (integer vs. string vs. filepath vs. predefined enum/choice list).

---

## 3. Recommended Hybrid Architecture

A hybrid architecture pairing a deterministic regex/rule parser with a lightweight local LLM provides the most resilient approach.

```
+--------------------+      +-------------------------------------------+
|  Target CLI Tool   | ---> |             Schema Generator              |
|  (e.g. `rg --help`)|      |  - Deterministic Layer (Regex / Docopt)   |
+--------------------+      |  - Semantic Layer (Local LLM via Ollama)  |
                            +-------------------------------------------+
                                                  |
                                                  v
                                     +-------------------------+
                                     | Intermediate JSON Schema|
                                     +-------------------------+
                                                  |
                                                  v
                            +-------------------------------------------+
                            |          Dynamic TUI Engine               |
                            |  (Textual [Python] or Bubbletea [Go])     |
                            |  - Checkboxes for boolean flags           |
                            |  - Text/File pickers for paths            |
                            |  - Dropdowns for enum choices             |
                            +-------------------------------------------+
                                                  |
                                                  v
                            +-------------------------------------------+
                            |            Execution Wrapper              |
                            |  - Assembles flags & arguments            |
                            |  - Executes subprocess & streams stdout   |
                            +-------------------------------------------+
```

### Step 1: The Schema Generator (The Parser)
Convert raw help text into a standardized intermediate JSON schema:
- **Deterministic Layer:** Use `docopt` or regex heuristics to capture standard flag syntaxes (`-f`, `--file=VALUE`, `--file <path>`).
- **Semantic Layer (Local LLM):** For ambiguous flags, subcommands, or complex descriptions, pipe the help block to a fast local model running in strict JSON mode to infer types and argument constraints.

#### Target Intermediate Schema:
```json
{
  "command": "sample-tool",
  "subcommands": [],
  "arguments": [
    {
      "switches": ["-v", "--verbose"],
      "expects_value": false,
      "type": "boolean",
      "description": "Enable debug logging"
    },
    {
      "switches": ["-o", "--output"],
      "expects_value": true,
      "type": "file_path",
      "description": "Destination file"
    },
    {
      "switches": ["--format"],
      "expects_value": true,
      "type": "choice_enum",
      "choices": ["json", "yaml", "text"],
      "description": "Output formatting style"
    }
  ]
}
```

### Step 2: The Dynamic TUI Engine
A component-driven TUI framework (e.g., Python Textual, Go Bubbletea, or Rust Ratatui) ingests the schema and mounts widgets dynamically at runtime:
- `boolean` flags -> Checkboxes / Toggle switches
- `file_path` / `directory_path` -> File/Directory picker input modal
- `choice_enum` -> Dropdown select menu
- `integer` / `string` -> Validated text inputs

### Step 3: Execution Wrapper
Once the user configures the command parameters and triggers "Run":
1. Assemble the command string and flag arguments safely (preventing shell injection).
2. Execute via `execv` / subprocess.
3. Stream `stdout` and `stderr` back into a dedicated output viewport inside the TUI.

---

## 4. Local LLM Recommendations for CLI Semantics

When running local models to extract structured schemas from raw CLI `--help` or `man` pages:

| Model Size Tier | Best Pick | Key Strengths | Typical Hardware |
| :--- | :--- | :--- | :--- |
| **Small & Fast** (3B – 7B) | **Qwen2.5-Coder-7B-Instruct** (or 3B variant) | 130k token context window (handles long man pages); top-tier structured token adherence. | 8GB – 16GB RAM / VRAM |
| **The Sweet Spot** (14B – 24B) | **Codestral 2** or **Mistral Small 3.1** | Strong function-calling and JSON schema adherence; accurate detection of flag value expectations. | 16GB – 24GB VRAM |
| **Flagship / Max Capability** (32B+) | **Qwen2.5-Coder-32B-Instruct** | Frontier-level multi-step code execution and complex subcommand tree extraction. | 32GB+ RAM / VRAM |

### Recommended System Prompt for Schema Extraction:
```text
You are a deterministic system compiler. Your task is to ingest raw shell utility `--help` outputs or `man` pages and output a strict JSON structure following this EXACT schema, without markdown formatting or conversational filler:

{
  "command_name": "string",
  "subcommands": ["array_of_strings"],
  "options": [
    {
      "switches": ["-v", "--verbose"],
      "expects_value": false,
      "type": "boolean",
      "description": "Short explanation"
    },
    {
      "switches": ["-f", "--file"],
      "expects_value": true,
      "type": "file_path",
      "description": "Target folder path"
    }
  ]
}

Ensure types are normalized exclusively to: [boolean, string, integer, file_path, directory_path, choice_enum].
If any switch expects specific choices, add a "choices" array parameter to that option dictionary. Do not hypothesize parameters.
```

---

## 5. Machine-Readable Context Manifest

```json
{
  "session_topic": "Dynamic CLI to TUI Generation",
  "architectural_approach": "Hybrid Deterministic Regex + Semantic LLM Layer",
  "target_tui_frameworks": [
    "Textual (Python)",
    "Bubbletea (Go)",
    "Ratatui (Rust)"
  ],
  "recommended_local_models": [
    {
      "model": "qwen2.5-coder:7b",
      "tier": "Resource-light / High Speed",
      "best_for": "Terminal parsing and 130k token context management"
    },
    {
      "model": "codestral",
      "tier": "The Sweet Spot (14B-24B)",
      "best_for": "Logical function routing and JSON schema compliance"
    }
  ],
  "parser_output_target": "Strict JSON map resolving boolean, string, integer, file_path, directory_path, and choice_enum types"
}
```
