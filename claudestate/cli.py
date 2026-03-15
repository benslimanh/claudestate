"""
ClaudeState CLI — entry point for all commands.

Commands
--------
  init        Initialise STATE.md in a project (with optional AI generation)
  sync        Morning sync: read STATE.md and get an AI briefing
  checkpoint  Mark a task done and create a git commit
  blocker     Log a blocker to STATE.md
  context     Ask the AI which files to load for the current task
  loop-check  Analyse recent commits for development loops
  status      Print current STATE.md summary (no API call)
  arch-update Regenerate the Architecture diagram from the file tree
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from claudestate.state import StateManager, _detect_language, _now, STATE_FILENAME
from claudestate.templates import render_default_state

app = typer.Typer(
    name="claudestate",
    help="ClaudeState — AI memory and token optimizer for your projects.",
    add_completion=False,
)
console = Console()

# ── helpers ────────────────────────────────────────────────────────────────────

def _get_manager(path: Optional[Path]) -> StateManager:
    root = path or Path.cwd()
    return StateManager(root)


def _load_ai(api_key: Optional[str] = None):
    """Lazy-load the Claude client so offline commands stay fast."""
    from claudestate.ai import ClaudeClient
    return ClaudeClient(api_key=api_key)


def _file_tree(root: Path, max_depth: int = 3) -> str:
    """Simple recursive file tree as a string."""
    lines: list[str] = []
    ignore = {".git", "__pycache__", "node_modules", ".venv", "target", "dist"}

    def _walk(p: Path, depth: int):
        if depth > max_depth:
            return
        for child in sorted(p.iterdir()):
            if child.name.startswith(".") or child.name in ignore:
                continue
            prefix = "  " * depth + ("[dir] " if child.is_dir() else "      ")
            lines.append(prefix + child.name)
            if child.is_dir():
                _walk(child, depth + 1)

    _walk(root, 0)
    return "\n".join(lines)


# ── commands ───────────────────────────────────────────────────────────────────

@app.command()
def init(
    project_root: Optional[Path] = typer.Argument(None, help="Project root (default: cwd)"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Project name"),
    goal: Optional[str] = typer.Option(None, "--goal", "-g", help="One-line project goal"),
    ai: bool = typer.Option(True, "--ai/--no-ai", help="Use Claude API to generate STATE.md"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="ANTHROPIC_API_KEY"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing STATE.md"),
):
    """Initialise STATE.md (and optionally CLAUDE.md) in a project."""
    manager = _get_manager(project_root)

    if manager.exists() and not force:
        rprint("[yellow]Warning: STATE.md already exists. Use --force to overwrite.[/yellow]")
        raise typer.Exit(1)

    proj_name = name or manager.root.name
    proj_goal = goal or typer.prompt("One-line project goal")
    language = _detect_language(manager.root)

    rprint(f"\n[bold cyan]Detected language:[/bold cyan] {language}")

    if ai:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task("Asking Claude to generate your STATE.md…", total=None)
            try:
                client = _load_ai(api_key)
                content = client.generate_initial_state(proj_name, proj_goal, language)
            except Exception as e:
                rprint(f"[yellow]Warning: AI generation failed ({e}). Using default template.[/yellow]")
                content = render_default_state(proj_name, proj_goal, language)
    else:
        content = render_default_state(proj_name, proj_goal, language)

    manager.write(content)
    rprint(f"[green]Created: STATE.md at {manager.state_path}[/green]")

    # Sync summary into CLAUDE.md (native Anthropic memory file)
    manager.sync_to_claude_md()
    rprint(f"[green]Created: CLAUDE.md at {manager.claude_path}[/green]")

    if manager.is_git_repo():
        ok, msg = manager.git_checkpoint(f"Init ClaudeState for {proj_name}")
        status = "[green]committed[/green]" if ok else f"[red]git error:[/red] {msg}"
        rprint(f"[bold]Git:[/bold] {status}")
    else:
        rprint("[dim]Tip: run `git init` and `claudestate init` for auto-checkpoints.[/dim]")

    rprint("\n[bold]Next step:[/bold] run [cyan]claudestate sync[/cyan] for your morning briefing!")


@app.command()
def sync(
    project_root: Optional[Path] = typer.Argument(None),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="ANTHROPIC_API_KEY"),
):
    """Morning sync — get an AI briefing from STATE.md."""
    manager = _get_manager(project_root)
    state = manager.read()

    next_task = manager.next_task()
    tasks = manager.get_tasks()
    done = sum(1 for t in tasks if t["done"])
    total = len(tasks)

    # Local summary (no API needed)
    table = Table(title="Project Status", show_header=False, box=None)
    table.add_row("[bold]Tasks[/bold]", f"{done}/{total} done ({int(done/total*100) if total else 0}%)")
    table.add_row("[bold]Next[/bold]", next_task["text"] if next_task else "All tasks complete.")
    console.print(table)

    # AI briefing
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if key:
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
            p.add_task("Generating AI briefing…", total=None)
            client = _load_ai(key)
            briefing = client.morning_sync(state)
        rprint(Panel(briefing, title="[bold cyan]Session Briefing[/bold cyan]", border_style="cyan"))
    else:
        rprint("[dim]Tip: set ANTHROPIC_API_KEY for an AI morning briefing.[/dim]")


@app.command()
def checkpoint(
    task: str = typer.Argument(..., help="Task text to mark as done (partial match OK)"),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Custom git commit message"),
    project_root: Optional[Path] = typer.Argument(None),
):
    """Mark a task complete and create a git checkpoint."""
    manager = _get_manager(project_root)

    matched = False
    for t in manager.get_tasks():
        if task.lower() in t["text"].lower() and not t["done"]:
            manager.complete_task(t["text"])
            manager.bump_last_updated()
            manager.sync_to_claude_md()
            rprint(f"[green]Done:[/green] {t['text']}")
            matched = True

            commit_msg = message or f"Completed: {t['text']}"
            if manager.is_git_repo():
                ok, out = manager.git_checkpoint(commit_msg)
                if ok:
                    rprint(f"[green]Git checkpoint:[/green] {out[:80]}")
                else:
                    rprint(f"[yellow]Git warning: {out}[/yellow]")
            break

    if not matched:
        rprint(f"[red]No open task matching:[/red] '{task}'")
        rprint("[dim]Run `claudestate status` to see all tasks.[/dim]")
        raise typer.Exit(1)


@app.command()
def blocker(
    description: str = typer.Argument(..., help="Describe the blocker"),
    project_root: Optional[Path] = typer.Argument(None),
):
    """Log a blocker to STATE.md and create a git checkpoint."""
    manager = _get_manager(project_root)
    manager.add_blocker(description)
    manager.bump_last_updated()
    rprint(f"[yellow]Blocker logged:[/yellow] {description}")

    if manager.is_git_repo():
        ok, out = manager.git_checkpoint(f"BLOCKER: {description[:60]}")
        if ok:
            rprint(f"[green]Saved in git[/green]")


@app.command()
def context(
    task: Optional[str] = typer.Argument(None, help="Describe the task (default: next open task)"),
    project_root: Optional[Path] = typer.Argument(None),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="ANTHROPIC_API_KEY"),
):
    """Ask the AI which files to load for the current task."""
    manager = _get_manager(project_root)
    state = manager.read()

    task_desc = task
    if not task_desc:
        next_t = manager.next_task()
        if not next_t:
            rprint("[green]All tasks complete! Nothing to context-load.[/green]")
            raise typer.Exit()
        task_desc = next_t["text"]

    rprint(f"[bold]Task:[/bold] {task_desc}")

    client = _load_ai(api_key)
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Finding relevant files…", total=None)
        result = client.smart_context(state, task_desc)

    rprint(Panel(result, title="[bold]Relevant files[/bold]", border_style="green"))


@app.command(name="loop-check")
def loop_check(
    project_root: Optional[Path] = typer.Argument(None),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="ANTHROPIC_API_KEY"),
    last: int = typer.Option(20, "--last", "-n", help="Number of recent commits to analyse"),
):
    """Detect development loops from recent git commits."""
    manager = _get_manager(project_root)

    if not manager.is_git_repo():
        rprint("[red]Not a git repository.[/red]")
        raise typer.Exit(1)

    result = subprocess.run(
        ["git", "log", f"-{last}", "--pretty=format:%s"],
        cwd=manager.root, capture_output=True, text=True,
    )
    commits = [l.strip() for l in result.stdout.splitlines() if l.strip()]

    if not commits:
        rprint("[yellow]No commits found.[/yellow]")
        raise typer.Exit()

    state = manager.read()
    client = _load_ai(api_key)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Analysing commit history…", total=None)
        diagnosis = client.detect_loop(commits, state)

    if diagnosis.strip() == "NO_LOOP":
        rprint("[green]No development loop detected.[/green]")
    else:
        rprint(Panel(diagnosis, title="[bold red]Loop Detected[/bold red]", border_style="red"))
        manager.add_blocker(f"Loop detected: {diagnosis[:120]}")
        rprint("[yellow]Blocker logged to STATE.md[/yellow]")


@app.command(name="arch-update")
def arch_update(
    project_root: Optional[Path] = typer.Argument(None),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="ANTHROPIC_API_KEY"),
):
    """Regenerate the Architecture diagram in STATE.md from the file tree."""
    manager = _get_manager(project_root)
    state = manager.read()
    tree = _file_tree(manager.root)

    client = _load_ai(api_key)
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Updating architecture diagram…", total=None)
        new_arch = client.update_architecture(state, tree)

    manager.update_section("Architecture", new_arch)
    manager.bump_last_updated()
    manager.sync_to_claude_md()
    rprint("[green]Architecture section updated in STATE.md[/green]")

    if manager.is_git_repo():
        manager.git_checkpoint("Update architecture diagram")


@app.command()
def status(
    project_root: Optional[Path] = typer.Argument(None),
    full: bool = typer.Option(False, "--full", "-f", help="Print the full STATE.md"),
):
    """Print current STATE.md summary (no API call required)."""
    manager = _get_manager(project_root)

    if full:
        console.print(Markdown(manager.read()))
        return

    tasks = manager.get_tasks()
    done = sum(1 for t in tasks if t["done"])
    total = len(tasks)

    table = Table(title=f"{manager.root.name} — ClaudeState", show_lines=True)
    table.add_column("Status", style="bold", width=6)
    table.add_column("Task")

    for t in tasks:
        icon = "[green]done[/green]" if t["done"] else "[yellow]open[/yellow]"
        table.add_row(icon, t["text"])

    console.print(table)
    rprint(f"\n[bold]{done}/{total}[/bold] tasks complete — "
           f"[cyan]{int(done/total*100) if total else 0}%[/cyan]")

    next_t = manager.next_task()
    if next_t:
        rprint(f"\n[bold]Next:[/bold] {next_t['text']}")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    app()


if __name__ == "__main__":
    main()
