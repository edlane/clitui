# Project clitui — Antigravity Agent Guidelines

`clitui` is a Linux tool that parses the `--help` (or `man`) output of arbitrary CLI commands and dynamically generates an equivalent Text User Interface (TUI).

## Architectural Guidelines
1. **Hybrid Parsing Pipeline:**
   - Deterministic Regex/Heuristic layer for standard flags (`-f`, `--flag`, `--key=val`).
   - Semantic LLM layer (via local Ollama, e.g. `qwen2.5-coder:7b`) for ambiguous parameters and subcommand trees.
2. **Intermediate Representation:**
   - Always translate parsed CLI flags into the standardized JSON schema defined in `cli-tui-context.md`.
3. **Dynamic TUI Rendering:**
   - Render form controls dynamically based on argument types (`boolean` -> checkbox, `file_path` -> file picker, `choice_enum` -> select dropdown).
4. **Subprocess Isolation:**
   - Execute commands safely via non-shell subprocess / `execv` to prevent injection and stream real-time output.

## Project Rules
- All CLI commands executed by agents must be preceded by a space to prevent `.bash_history` pollution.
