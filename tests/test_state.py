"""
Tests for ClaudeState core logic (no API calls needed).
"""

import pytest
from pathlib import Path
from claudestate.state import StateManager
from claudestate.templates import render_default_state


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temp project with a minimal STATE.md."""
    content = render_default_state("TestProject", "Test the tool", "Python")
    (tmp_path / "STATE.md").write_text(content, encoding="utf-8")
    return tmp_path


def test_state_exists(tmp_project):
    mgr = StateManager(tmp_project)
    assert mgr.exists()


def test_get_tasks_returns_list(tmp_project):
    mgr = StateManager(tmp_project)
    tasks = mgr.get_tasks()
    assert isinstance(tasks, list)
    assert len(tasks) > 0


def test_next_task_is_undone(tmp_project):
    mgr = StateManager(tmp_project)
    task = mgr.next_task()
    assert task is not None
    assert not task["done"]


def test_complete_task(tmp_project):
    mgr = StateManager(tmp_project)
    first = mgr.next_task()
    assert first is not None
    result = mgr.complete_task(first["text"])
    assert result is True
    # verify it's now marked done
    updated_tasks = mgr.get_tasks()
    done_texts = [t["text"] for t in updated_tasks if t["done"]]
    assert first["text"] in done_texts


def test_add_blocker(tmp_project):
    mgr = StateManager(tmp_project)
    mgr.add_blocker("Cannot connect to database in CI")
    content = mgr.read()
    assert "Cannot connect to database in CI" in content


def test_sync_to_claude_md(tmp_project):
    mgr = StateManager(tmp_project)
    mgr.sync_to_claude_md()
    assert mgr.claude_exists()
    claude_content = (tmp_project / "CLAUDE.md").read_text()
    assert "Next task" in claude_content


def test_bump_last_updated(tmp_project):
    mgr = StateManager(tmp_project)
    mgr.bump_last_updated()
    content = mgr.read()
    assert "Last Updated" in content


def test_render_default_template():
    out = render_default_state("MyApp", "Build something cool", "Rust")
    assert "MyApp" in out
    assert "Rust" in out
    assert "## Roadmap" in out
    assert "## Architecture" in out
    assert "mermaid" in out


def test_read_section(tmp_project):
    mgr = StateManager(tmp_project)
    roadmap = mgr.read_section("Roadmap")
    assert "Phase 1" in roadmap


def test_no_state_raises(tmp_path):
    mgr = StateManager(tmp_path)
    with pytest.raises(FileNotFoundError):
        mgr.read()
