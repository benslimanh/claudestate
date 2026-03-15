"""
Claude API integration — uses Anthropic SDK to intelligently update STATE.md.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    import anthropic
    HAS_SDK = True
except ImportError:
    HAS_SDK = False


SYSTEM_PROMPT = """\
You are ClaudeState, an AI project memory manager.
Your ONLY job is to maintain the STATE.md file for a software project.

Rules:
1. Always respond with valid Markdown that can be written directly to STATE.md.
2. Never remove completed [x] tasks — history matters.
3. Keep the architecture diagram up to date.
4. Be concise — every token counts.
5. When updating tasks, preserve the exact format: `- [ ] task` / `- [x] task`.
6. Flag blockers clearly under the ## Blockers section.
"""


class ClaudeClient:
    """Thin wrapper around the Anthropic SDK for STATE.md operations."""

    def __init__(self, api_key: Optional[str] = None):
        if not HAS_SDK:
            raise ImportError(
                "anthropic SDK not installed. Run: pip install anthropic"
            )
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY not set. Export it or pass --api-key."
            )
        self.client = anthropic.Anthropic(api_key=key)

    # ── Core call ──────────────────────────────

    def _ask(self, user_message: str, max_tokens: int = 2048) -> str:
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

    # ── Public helpers ─────────────────────────

    def generate_initial_state(
        self,
        project_name: str,
        goal: str,
        language: str,
        extra_context: str = "",
    ) -> str:
        """Generate a fresh STATE.md from project metadata."""
        prompt = f"""
Create a STATE.md for this project:

**Project name:** {project_name}
**Goal:** {goal}
**Primary language:** {language}
{f"**Extra context:** {extra_context}" if extra_context else ""}

The file must include:
1. A header with project name, goal, language, creation date, and last updated.
2. ## Current Status section with the active phase name.
3. ## Roadmap section with phases, each containing 3–6 checkbox tasks.
4. ## Architecture section with a simple Mermaid.js graph.
5. ## Token Budget section tracking estimated tokens used (start at 0).
6. ## Blockers section (empty initially).
7. ## Changelog section (empty initially).

Use today's date. Return ONLY the Markdown file content.
"""
        return self._ask(prompt, max_tokens=3000)

    def morning_sync(self, state_content: str) -> str:
        """Return a concise morning briefing based on STATE.md."""
        prompt = f"""
Read this STATE.md and give a SHORT morning briefing (max 120 words).
Format:
- What was completed last session
- The single next task to start
- Any blockers to be aware of
- A motivating one-liner

STATE.md:
---
{state_content}
---

Respond in plain text, no Markdown headers.
"""
        return self._ask(prompt, max_tokens=300)

    def smart_context(self, state_content: str, task_description: str) -> str:
        """
        Given the current task, return ONLY the file paths / modules
        the AI should load — avoiding irrelevant context.
        """
        prompt = f"""
The current task is: "{task_description}"

Based on the STATE.md below, list ONLY the file paths or module names
that are relevant to this task. One per line, no explanations.
If you need more info, ask one clarifying question.

STATE.md:
---
{state_content}
---
"""
        return self._ask(prompt, max_tokens=400)

    def detect_loop(self, recent_commits: list[str], state_content: str) -> str:
        """
        Analyze recent commit messages for repetitive patterns (loop detection).
        Returns a diagnosis string.
        """
        commits_str = "\n".join(f"- {c}" for c in recent_commits[-20:])
        prompt = f"""
Analyze these recent git commits for signs of a development loop
(the same area being modified repeatedly without progress):

{commits_str}

STATE.md context:
---
{state_content}
---

If a loop is detected: explain the likely root cause in 2 sentences and suggest ONE concrete fix.
If no loop: respond with "NO_LOOP".
"""
        return self._ask(prompt, max_tokens=300)

    def update_architecture(self, state_content: str, file_tree: str) -> str:
        """Regenerate the Architecture section Mermaid diagram from the file tree."""
        prompt = f"""
Update ONLY the ## Architecture section of this STATE.md.
Use the file tree below to generate an accurate Mermaid.js graph (graph TD).
Return ONLY the updated ## Architecture section content (not the full file).

File tree:
{file_tree}

Current STATE.md:
---
{state_content}
---
"""
        return self._ask(prompt, max_tokens=600)
