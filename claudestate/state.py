"""
Core STATE.md manager — reads, writes, and updates the AI memory file.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

STATE_FILENAME = "STATE.md"
CLAUDE_FILENAME = "CLAUDE.md"          # native Anthropic file Claude Code reads
GITIGNORE_MARKER = "# claudestate"


# ──────────────────────────────────────────────
#  Data helpers
# ──────────────────────────────────────────────

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _detect_language(project_root: Path) -> str:
    """Heuristic: detect primary language from files present."""
    checks = {
        "Python":     ["*.py", "pyproject.toml", "setup.py"],
        "Rust":       ["Cargo.toml", "*.rs"],
        "Go":         ["go.mod", "*.go"],
        "JavaScript": ["package.json", "*.js"],
        "TypeScript": ["tsconfig.json", "*.ts"],
        "Solidity":   ["hardhat.config.*", "*.sol"],
    }
    scores: dict[str, int] = {}
    for lang, patterns in checks.items():
        for pat in patterns:
            if list(project_root.glob(pat)):
                scores[lang] = scores.get(lang, 0) + 1
    if not scores:
        return "Unknown"
    return max(scores, key=lambda k: scores[k])


# ──────────────────────────────────────────────
#  State file I/O
# ──────────────────────────────────────────────

class StateManager:
    """Reads and mutates the STATE.md / CLAUDE.md file."""

    def __init__(self, project_root: Path):
        self.root = project_root
        self.state_path = project_root / STATE_FILENAME
        self.claude_path = project_root / CLAUDE_FILENAME

    # ── existence ──────────────────────────────

    def exists(self) -> bool:
        return self.state_path.exists()

    def claude_exists(self) -> bool:
        return self.claude_path.exists()

    # ── read ───────────────────────────────────

    def read(self) -> str:
        if not self.exists():
            raise FileNotFoundError(
                f"No STATE.md found in {self.root}. Run `claudestate init` first."
            )
        return self.state_path.read_text(encoding="utf-8")

    def read_section(self, heading: str) -> str:
        """Extract the text under a specific ## heading."""
        content = self.read()
        pattern = rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)"
        m = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        return m.group(1).strip() if m else ""

    # ── write ──────────────────────────────────

    def write(self, content: str) -> None:
        self.state_path.write_text(content, encoding="utf-8")

    def update_section(self, heading: str, new_body: str) -> None:
        """Replace a ## section body in-place."""
        content = self.read()
        pattern = rf"(^## {re.escape(heading)}\s*$)(.*?)(?=^## |\Z)"
        replacement = rf"\g<1>\n{new_body}\n\n"
        updated = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
        self.write(updated)

    # ── task checklist helpers ──────────────────

    def get_tasks(self) -> list[dict]:
        """Parse all [ ] / [x] lines into structured dicts."""
        content = self.read()
        tasks = []
        for i, line in enumerate(content.splitlines()):
            m = re.match(r"^\s*-\s+\[( |x)\]\s+(.+)$", line, re.IGNORECASE)
            if m:
                tasks.append({
                    "line": i,
                    "done": m.group(1).lower() == "x",
                    "text": m.group(2).strip(),
                    "raw": line,
                })
        return tasks

    def next_task(self) -> Optional[dict]:
        for t in self.get_tasks():
            if not t["done"]:
                return t
        return None

    def complete_task(self, task_text: str) -> bool:
        """Mark a task [x] by matching its text."""
        content = self.read()
        pattern = rf"(- \[ \]\s+{re.escape(task_text)})"
        new_content = re.sub(pattern, lambda m: m.group(0).replace("[ ]", "[x]"), content)
        if new_content != content:
            self.write(new_content)
            return True
        return False

    def add_blocker(self, description: str) -> None:
        """Log a blocker entry with timestamp."""
        entry = f"\n- WARNING:  [{_now()}] {description}"
        content = self.read()
        # append under Blockers section if exists
        if "## Blockers" in content:
            self.update_section(
                "Blockers",
                self.read_section("Blockers") + entry,
            )
        else:
            self.write(content + f"\n\n## Blockers\n{entry}\n")

    # ── metadata ───────────────────────────────

    def bump_last_updated(self) -> None:
        content = self.read()
        updated = re.sub(
            r"(\*\*Last Updated:\*\*\s*).*",
            rf"\g<1>{_now()}",
            content,
        )
        self.write(updated)

    # ── CLAUDE.md sync ─────────────────────────

    def sync_to_claude_md(self) -> None:
        """
        Write a compact summary into CLAUDE.md so Claude Code picks it up
        automatically at context start (Anthropic's native memory file).
        """
        state_content = self.read()
        next_t = self.next_task()
        next_str = next_t["text"] if next_t else "All tasks complete."

        snippet = (
            "<!-- AUTO-GENERATED by ClaudeState — do not edit manually -->\n\n"
            "# AI Memory Snapshot\n\n"
            f"**Next task:** {next_str}\n\n"
            "## Current Plan (condensed)\n\n"
            f"See `STATE.md` for full details.\n\n"
            "```\n"
            + _extract_checklist(state_content)
            + "\n```\n\n"
            "---\n"
            "*Load `STATE.md` for full context before coding.*\n"
        )
        self.claude_path.write_text(snippet, encoding="utf-8")

    # ── git helpers ────────────────────────────

    def git_checkpoint(self, message: str) -> tuple[bool, str]:
        """Stage all and commit with a prefixed message."""
        try:
            subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
            result = subprocess.run(
                ["git", "commit", "-m", f"AI: {message}"],
                cwd=self.root, capture_output=True, text=True,
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, result.stderr.strip()
        except FileNotFoundError:
            return False, "git not found in PATH"
        except subprocess.CalledProcessError as e:
            return False, str(e)

    def is_git_repo(self) -> bool:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=self.root, capture_output=True, text=True,
        )
        return result.returncode == 0


# ──────────────────────────────────────────────
#  Internal helpers
# ──────────────────────────────────────────────

def _extract_checklist(md: str) -> str:
    """Pull only checkbox lines from STATE.md for compact display."""
    lines = [l for l in md.splitlines() if re.match(r"^\s*-\s+\[", l)]
    return "\n".join(lines) if lines else "(no tasks found)"
