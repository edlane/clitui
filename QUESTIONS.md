# clitui — Architecture & Design Decisions

Please provide your answers below each question. You can reply inline, below the question, or replace the `<!-- ANSWER: ... -->` comment blocks.

---

## 1. Deterministic vs. LLM Invocation Strategy
- **Context:** Regex parsing is sub-millisecond, while Ollama inference takes 1–3+ seconds.
- **Question:** How should `clitui` decide when to invoke Ollama?
  - Option A: **Hybrid automatic** — Run regex first; automatically invoke Ollama for unparsed flags, ambiguous types, or subcommand extraction.
  - Option B: **Deterministic-first (opt-in AI)** — Run fast deterministic regex by default. Only invoke Ollama if the user passes `--ai` or if parsing yields zero usable flags.
  - Option C: **Always LLM-assisted** — Always consult Ollama to produce the richest schema possible.

<!-- ANSWER: 
-->

- **Question:** Which local Ollama model should be default?
  - Currently installed on your system: `qwen2.5:latest` (4.7 GB), `llama3.2:latest`, `mistral-small3.2:latest`.
  - Alternatively: pull `qwen2.5-coder:7b` (as recommended in the spec).

<!-- ANSWER: 
-->

---

## 2. Schema Caching
- **Context:** Extracting and parsing `--help` or `man` pages (especially with LLM inference) adds latency on initial launch.
- **Question:** Should `clitui` implement a local schema cache (e.g., in `~/.cache/clitui/<command>-<version_hash>.json`)?
  - Option A: Yes, enable caching by default with a `--no-cache` or `--refresh` flag.
  - Option B: No caching initially, keep it stateless during initial development.

<!-- ANSWER: 
-->

---

## 3. Positional Arguments Handling
- **Context:** Many commands require positional arguments (e.g., `rg <PATTERN> [PATH...]`, `tar -czvf <ARCHIVE> [FILES...]`).
- **Question:** How would you like positional arguments presented in the Textual TUI?
  - Option A: Pinned at the top of the form in a dedicated "Required / Positional Arguments" card.
  - Option B: Grouped in their own tab or accordion section alongside option categories.
  - Option C: A live command-line preview bar at the bottom with quick-edit fields.

<!-- ANSWER: 
-->

---

## 4. CLI Invocation Interface & Syntax
- **Context:** How users type the command in their shell.
- **Question:** What should the invocation syntax look like?
  - Option A: Direct transparent pass-through: `clitui <cmd> [initial_args]` (e.g., `clitui rg`, `clitui git commit`).
  - Option B: Delimited pass-through: `clitui -- <cmd> [initial_args]`.
  - Option C: Both A & B supported, plus launching `clitui` with no arguments opens an interactive command prompt / launcher.

<!-- ANSWER: 
-->

---

## 5. Subcommand Navigation
- **Context:** Hierarchical tools like `git`, `docker`, or `kubectl` have subcommands (`git remote add`, `docker compose up`).
- **Question:** How deep should subcommand parsing go initially?
  - Option A: Single-level commands first (e.g. `clitui <cmd>` or user supplies the subcommand directly like `clitui git-commit`), with nested subcommand tree browsing added next.
  - Option B: Dynamic subcommand selector screen inside the TUI if subcommands are detected.

<!-- ANSWER: 
-->

---

## 6. Python Environment & Dependency Setup
- **Context:** `textual` and `requests` need to be installed. Python 3.14 is currently on your system.
- **Question:** Where should dependencies be installed?
  - Option A: In a local project virtual environment (`.venv` in the repo root).
  - Option B: In the user environment (`pip install --user`).

<!-- ANSWER: 
-->

---

## 7. Additional Notes or Constraints
<!-- Add any specific preferences, UX desires, or non-negotiables here:

-->
