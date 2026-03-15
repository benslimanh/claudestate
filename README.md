# ClaudeState

**Persistent memory layer for vibe coding with Claude Code.**

[![PyPI](https://img.shields.io/pypi/v/claudestate)](https://pypi.org/project/claudestate/)
[![Python](https://img.shields.io/pypi/pyversions/claudestate)](https://pypi.org/project/claudestate/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://github.com/benslimanh/claudestate/actions/workflows/test.yml/badge.svg)](https://github.com/benslimanh/claudestate/actions)

---

## Why ClaudeState

ClaudeState keeps your project plan outside the model's short-term context so Claude can resume work without losing direction.

- Keep one source of truth in `STATE.md`
- Reduce wasted context loading each session
- Track blockers and progress in a way AI can reliably follow

## 30-Second Demo

```bash
pipx install claudestate
cd my-project
claudestate init --name "my-project" --goal "Ship MVP fast"
claudestate sync
claudestate checkpoint "Initialise repository structure"
```

## Vibe Coding Workflow

Use this loop every session:

1. `claudestate sync` to get the current briefing.
2. Ask Claude to continue from `STATE.md`.
3. Implement the task in small chunks.
4. `claudestate checkpoint "task"` when done.
5. Repeat.

This keeps coding momentum high while preventing context drift.

---

## The Problem

When using AI coding assistants (Claude Code, Cursor, Aider) on real projects, three failure modes appear consistently:

- **Token exhaustion** — the model rereads thousands of lines of code each session just to reconstruct where work left off
- **Context loss** — after a long session, the model loses awareness of the original architecture and makes conflicting changes
- **Development loops** — the model rewrites the same function repeatedly without converging on a solution

Each session starts from zero. There is no memory of what was decided, what was completed, or what failed.

## The Solution

ClaudeState introduces a single structured file — `STATE.md` — maintained at the project root. It acts as the project's external long-term memory: a phase-by-phase roadmap with task checklists, an architecture diagram, a token budget log, and a blocker registry.

Instead of reloading the entire codebase, the model reads this one file and knows exactly where to begin.

```
claudestate sync        # session briefing: what was done, what is next
claudestate context     # which files to load for the current task
claudestate checkpoint  # mark a task complete and commit to git
claudestate loop-check  # detect repetitive commit patterns
```

---

## Features

| Feature | Description |
|---|---|
| **Master Plan** | `STATE.md` with phases, task checklists, and current status |
| **Lazy Context Loading** | Per-task file recommendations — load only what the current task needs |
| **Auto Checkpointing** | Completing a task triggers a labelled `git commit` automatically |
| **Live Architecture** | Mermaid.js diagram updated by the AI as the project structure evolves |
| **Loop Detection** | Analyses git history for repetitive patterns and logs a blocker |
| **Session Sync** | One command produces a concise briefing of project status |
| **CLAUDE.md Integration** | Syncs a compact summary into `CLAUDE.md`, the file Claude Code reads natively at session start |

---

## Installation

```bash
pip install claudestate
```

Using [pipx](https://pipx.pypa.io/) for global installation (recommended):

```bash
pipx install claudestate
```

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

> **Offline mode:** `init`, `status`, `checkpoint`, and `blocker` work without an API key. `sync`, `context`, `loop-check`, and `arch-update` require one.

---

## Quick Start

```bash
cd my-project

# Generate STATE.md — Claude writes the initial roadmap
claudestate init --name "my-project" --goal "Build a REST API in Go"

# Print the current task checklist
claudestate status

# Get a session briefing
claudestate sync

# Ask which files to load for the next task
claudestate context

# Mark a task complete and commit
claudestate checkpoint "Initialise repository structure"

# Log a blocker
claudestate blocker "Postgres connection fails in Docker on Apple Silicon"

# Check for development loops
claudestate loop-check

# Regenerate the architecture diagram after a refactor
claudestate arch-update
```

---

## Command Reference

```
claudestate init          Generate STATE.md (AI-generated or offline template)
claudestate sync          Session briefing from Claude
claudestate status        Print task checklist — no API call required
claudestate checkpoint    Mark a task complete and create a git commit
claudestate blocker       Log a blocker to STATE.md
claudestate context       Recommend files to load for the current task
claudestate loop-check    Detect development loops from git history
claudestate arch-update   Regenerate the Architecture diagram
```

All commands accept `--api-key` or read from `ANTHROPIC_API_KEY`.
The short alias `cs` is also available (e.g. `cs sync`).

---

## STATE.md Format

```markdown
# rust-json-parser — State File

| Field        | Value                           |
|---|---|
| Goal         | Zero-copy JSON parser with SIMD |
| Language     | Rust                            |
| Last Updated | 2025-01-22 14:30                |

## Current Status
Active Phase: Phase 2 — Core Parser

## Roadmap

### Phase 1 — Setup
- [x] Initialise Cargo workspace
- [x] CI with GitHub Actions

### Phase 2 — Core Parser
- [x] Lexer: tokenise JSON bytes
- [ ] Parser: recursive descent        <- active task
- [ ] Zero-copy string slices

## Architecture
(Mermaid.js diagram — updated by `claudestate arch-update`)

## Token Budget
| Session    | Tokens | Task                     |
|---|---|---|
| 2025-01-22 | ~900   | Loaded src/lexer.rs only |

## Blockers
(none)
```

---

## How Lazy Context Loading Works

Without ClaudeState, Claude loads the entire repository each session.

With ClaudeState:

```bash
$ claudestate context
Task: Zero-copy string slices

Relevant files:
  src/parser.rs
  src/types.rs
  tests/string_tests.rs
```

Three files are loaded instead of forty. On a medium-sized project, this reduces token consumption by 60-80% per session.

---

## Language Support

ClaudeState detects the primary language from the repository structure and adjusts the initial roadmap accordingly. Detection is supported for:

| Language   | Indicators |
|---|---|
| Python     | `*.py`, `pyproject.toml`, `setup.py` |
| Rust       | `Cargo.toml`, `*.rs` |
| Go         | `go.mod`, `*.go` |
| JavaScript | `package.json`, `*.js` |
| TypeScript | `tsconfig.json`, `*.ts` |
| Solidity   | `hardhat.config.*`, `*.sol` |

Any language is supported — detection determines the initial template only.

---

## Claude Code Hook

Register the session hook to have `CLAUDE.md` updated automatically before every Claude Code tool call:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 claudestate-hook.py"
          }
        ]
      }
    ]
  }
}
```

Add this to `~/.claude/settings.json`. A ready-to-use template is at `docs/claude-settings-template.json`.

With the hook active, Claude Code reads the current task, branch, and last commit at the start of every session without any manual prompting.

---

## CLAUDE.md Integration

After each `checkpoint` or `arch-update`, ClaudeState writes a compact summary to `CLAUDE.md` — the file Claude Code loads natively at context start:

```markdown
# ClaudeState — Session Context

**Branch:** main
**Progress:** 7/12 tasks (58%)

## Start Here

- [ ] Parser: recursive descent for objects/arrays
- [ ] Zero-copy string slices
- [ ] Error types with byte-offset reporting
```

The injected context stays under approximately 400 tokens.

---

## Companion Tools

For integration with non-Python build systems:

| Tool | Language | Build |
|---|---|---|
| `claudestate` | Python CLI | `pip install claudestate` |
| `claudestate-hook.py` | Python | drop-in Claude Code hook |
| `go-companion/claudestate-go.go` | Go | `go build -o claudestate-go` |
| `rust-companion/` | Rust | `cargo build --release` |

The Go and Rust companions read `STATE.md` and output JSON, suitable for Makefiles, CI pipelines, and `cargo` build scripts.

---

## Contributing

```bash
git clone https://github.com/benslimanh/claudestate
cd claudestate
pip install -e ".[dev]"
pytest
```

Please open an issue before submitting a large pull request.

---

## License

MIT — see [LICENSE](LICENSE).
