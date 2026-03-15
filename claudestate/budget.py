"""
Token Budget Tracker — monitors per-session token usage and
writes estimates into the STATE.md Token Budget table.

Token counts are estimated (4 chars ≈ 1 token) since the
Anthropic SDK doesn't expose running totals mid-session.
For accurate counts, use the usage field from API responses.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


CHARS_PER_TOKEN = 4       # rough estimate
WARN_THRESHOLD  = 50_000  # warn if estimated tokens > this per session
LOOP_THRESHOLD  = 3       # same file edited N times → possible loop


class TokenBudget:
    """Track token usage across files loaded in a session."""

    def __init__(self, session_label: Optional[str] = None):
        self.session  = session_label or datetime.now().strftime("%Y-%m-%d")
        self.entries: list[dict] = []
        self._file_edit_counts: dict[str, int] = {}

    # ── recording ──────────────────────────────

    def record_file_load(self, filepath: str | Path, content: str, task: str = "") -> int:
        """Record that a file was loaded into context. Returns estimated tokens."""
        tokens = max(1, len(str(content)) // CHARS_PER_TOKEN)
        entry  = {
            "file":   str(filepath),
            "tokens": tokens,
            "task":   task or "—",
            "ts":     datetime.now().isoformat(timespec="seconds"),
        }
        self.entries.append(entry)
        return tokens

    def record_api_response(self, response_text: str, task: str = "") -> int:
        """Record an API response size."""
        tokens = max(1, len(response_text) // CHARS_PER_TOKEN)
        self.entries.append({
            "file":   "[api-response]",
            "tokens": tokens,
            "task":   task or "—",
            "ts":     datetime.now().isoformat(timespec="seconds"),
        })
        return tokens

    def record_file_edit(self, filepath: str | Path) -> int:
        """
        Track how many times a file has been edited this session.
        Returns the edit count — used by loop detection.
        """
        key = str(filepath)
        self._file_edit_counts[key] = self._file_edit_counts.get(key, 0) + 1
        return self._file_edit_counts[key]

    # ── analysis ───────────────────────────────

    @property
    def total_tokens(self) -> int:
        return sum(e["tokens"] for e in self.entries)

    @property
    def is_over_budget(self) -> bool:
        return self.total_tokens > WARN_THRESHOLD

    def detect_loops(self) -> list[dict]:
        """
        Return list of files edited >= LOOP_THRESHOLD times.
        Each entry: {"file": str, "edits": int}
        """
        return [
            {"file": f, "edits": n}
            for f, n in self._file_edit_counts.items()
            if n >= LOOP_THRESHOLD
        ]

    def summary(self) -> dict:
        return {
            "session":      self.session,
            "total_tokens": self.total_tokens,
            "over_budget":  self.is_over_budget,
            "loops":        self.detect_loops(),
            "top_files":    sorted(
                [e for e in self.entries if e["file"] != "[api-response]"],
                key=lambda x: x["tokens"], reverse=True
            )[:5],
        }

    # ── STATE.md integration ───────────────────

    def write_to_state(self, state_path: Path, task: str = "") -> None:
        """Append a new row to the ## Token Budget table in STATE.md."""
        if not state_path.exists():
            return

        content = state_path.read_text(encoding="utf-8")
        row = (
            f"| {self.session} "
            f"| ~{self.total_tokens:,} "
            f"| {task or self.entries[-1]['task'] if self.entries else '—'} |"
        )

        # Find the table under ## Token Budget and append a row
        pattern = r"(## Token Budget\b.*?\n(?:\|.*\n)*)"
        m = re.search(pattern, content, re.DOTALL)
        if m:
            updated = content[: m.end()] + row + "\n" + content[m.end() :]
            state_path.write_text(updated, encoding="utf-8")

    def report(self) -> str:
        """Human-readable single-line report."""
        loops = self.detect_loops()
        loop_str = ""
        if loops:
            names = ", ".join(Path(l["file"]).name for l in loops)
            loop_str = f" WARNING:  LOOP detected on: {names}"
        budget_str = " OVER BUDGET" if self.is_over_budget else ""
        return (
            f"[token-budget] Session: {self.session} | "
            f"~{self.total_tokens:,} tokens{budget_str}{loop_str}"
        )
