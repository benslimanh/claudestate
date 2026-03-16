"""
Offline template for STATE.md — used when no API key is set or AI call fails.
"""

from __future__ import annotations
from datetime import datetime


def render_default_state(project_name: str, goal: str, language: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""\
# {project_name} — State File

> Maintained by [ClaudeState](https://github.com/benslimanh/claudestate).
> Do not edit manually — update via `claudestate checkpoint` and `claudestate blocker`.

| Field | Value |
|---|---|
| **Goal** | {goal} |
| **Language** | {language} |
| **Created** | {today} |
| **Last Updated** | {now} |

---

## Current Status

**Active Phase:** Phase 1 — Project Setup

---

## Roadmap

### Phase 1 — Project Setup
- [ ] Initialise repository structure
- [ ] Set up development environment
- [ ] Configure linting and formatting
- [ ] Write initial tests scaffold
- [ ] Document architecture decisions

### Phase 2 — Core Implementation
- [ ] Implement core business logic
- [ ] Add error handling and logging
- [ ] Write unit tests (target: >=80% coverage)
- [ ] Performance profiling

### Phase 3 — Integration & Polish
- [ ] Integration tests
- [ ] CI/CD pipeline
- [ ] Documentation (README + API docs)
- [ ] Release v1.0.0

---

## Architecture

```mermaid
graph TD
    A[Entry Point] --> B[Core Logic]
    B --> C[Data Layer]
    B --> D[External APIs]
    C --> E[(Storage)]
```

*Update with `claudestate arch-update` after each significant structural change.*

---

## Token Budget

| Session | Tokens Used | Task |
|---|---|---|
| Init | ~500 | ClaudeState setup |

---

## Blockers

*(none yet)*

---

## Changelog

- [{today}] Project initialised with ClaudeState
"""
